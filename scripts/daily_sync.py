#!/usr/bin/env python3
"""
daily_sync.py —— cafeaitools.com 每日自动同步（数据驱动，全流程无人值守）

每天 18:00 由自动化任务触发。做四件事：
  1. 拉取 GitHub 全部仓库与提交数据 → 更新 src/data/projects.json
     （新仓库自动录入；pushed / days / commits / visibility / url / zip 定量字段刷新）
  2. 解析 devlog-private/revenue/progress.md → 重新生成 src/data/ledger.js（收支）
  3. 汇总全站数字 → 重新生成 src/data/stats.js
  4. 按「自上次运行以来」的窗口生成当日流水账日记（src/content/posts/YYYY-MM-DD-daily-log.mdx）
  附加：og-image 底部数据条刷新（PIL 可用时）、npm 构建验证、Git Data API 单次提交推送。

设计原则：
  - 幂等：重复跑不产生重复内容；日记按日期覆盖重建。
  - 无变化不推送：内容文件零 diff 时不提交、不惊动部署。
  - 只碰数据文件：prose 全部从数据读，脚本不刮页面文本。
  - 失败即停：构建不过不推送（CI 构建失败也不会换上新版，站点保持上一个可用版本）。

依赖：gh（已认证）或 GITHUB_TOKEN 环境变量；python3；node/npm（构建，缺失时降级警告）。
"""
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

# ── 配置 ──────────────────────────────────────────────────────────────
OWNER = "xiaomo945"
REPO = f"{OWNER}/cafe-log"
BRANCH = "main"
START_DATE = "2026-05-11"                 # 站点第 1 天
TZ = timezone(timedelta(hours=8))         # Asia/Shanghai
LEDGER_SRC = f"{OWNER}/devlog-private"    # 收益数据源仓库
STATE_PATH = "scripts/sync-state.json"
DIARY_SLUG = "daily-log"                  # 日记文件名：YYYY-MM-DD-daily-log.mdx
SKIP_DIRS = ("node_modules/", "dist/", ".astro", ".wrangler", ".vercel")
EXCLUDE_REPOS = {"cafe-log"}              # 博客自身是「记录工具」，不算做出来的项目，不进花名册

_HAS_GH = shutil.which("gh") is not None


# ── 小工具 ────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now(TZ).strftime('%H:%M:%S')}] {msg}", flush=True)


def api(path, payload=None, retries=3, ok_404=False):
    """GitHub API 调用。优先 gh，缺失时用 curl + GITHUB_TOKEN。path 不含前导 /。"""
    url = f"https://api.github.com/{path}"
    last = None
    for attempt in range(retries):
        if _HAS_GH:
            cmd = ["gh", "api", path]
            if payload is not None:
                cmd += ["--input", "-"]
            p = subprocess.run(cmd, capture_output=True, text=True,
                               input=json.dumps(payload) if payload is not None else None)
            out, err, code = p.stdout, p.stderr, p.returncode
        else:
            token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
            cmd = ["curl", "-s", "-w", "\n%{http_code}", "-X", "GET", url,
                   "-H", "Accept: application/vnd.github+json",
                   "-H", f"Authorization: token {token}"]
            if payload is not None:
                cmd = ["curl", "-s", "-w", "\n%{http_code}", "-X", "POST", url,
                       "-H", "Accept: application/vnd.github+json",
                       "-H", f"Authorization: token {token}",
                       "-H", "Content-Type: application/json",
                       "-d", json.dumps(payload)]
            p = subprocess.run(cmd, capture_output=True, text=True)
            out, err, code = p.stdout, p.stderr, p.returncode
        if code == 0:
            body = out.strip()
            if not body:
                return {}
            if not _HAS_GH:
                # curl 模式：末行是 HTTP 状态码
                lines = body.rsplit("\n", 1)
                if len(lines) == 2 and lines[1].strip().isdigit():
                    status = int(lines[1])
                    body = lines[0]
                    if status == 404 and ok_404:
                        return None
                    if status >= 400:
                        last = f"HTTP {status}: {body[:200]}"
                        time.sleep(2 * (attempt + 1))
                        continue
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {}
        last = (err or out).strip()[:200]
        time.sleep(2 * (attempt + 1))
    if ok_404:
        return None
    raise RuntimeError(f"API 失败（重试 {retries} 次）: {path[:100]} | {last}")


def api_text(path, retries=3):
    """取文件内容（自动 base64 解码）。"""
    r = api(path, retries=retries)
    if r is None:
        return None
    return base64.b64decode(r.get("content", "")).decode("utf-8")


def now_tz():
    return datetime.now(TZ)


def today_str():
    return now_tz().strftime("%Y-%m-%d")


def iso_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Step 0：下载仓库到临时目录 ─────────────────────────────────────────

def download_repo(workdir):
    log(f"下载 {REPO}@{BRANCH} → {workdir}")
    tree = api(f"repos/{REPO}/git/trees/{BRANCH}?recursive=1")
    ok = skip = 0
    for item in tree["tree"]:
        if item["type"] != "blob":
            continue
        path = item["path"]
        if path.startswith(SKIP_DIRS):
            continue
        dest = os.path.join(workdir, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            r = api(f"repos/{REPO}/contents/{path}?ref={BRANCH}")
            with open(dest, "wb") as f:
                f.write(base64.b64decode(r.get("content", "")))
            ok += 1
        except Exception as e:
            log(f"  ⚠️ 读不到 {path}，跳过（{e}）")
            skip += 1
    log(f"仓库下载完成：{ok} 个文件（跳过 {skip}）")
    return ok


# ── Step 1-3：项目数据同步 ────────────────────────────────────────────

def guess_kind(name, desc, lang):
    text = f"{name} {desc or ''}".lower()
    if any(k in text for k in ["游戏", "game", "拼图", "puzzle", "瓶子", "bottle",
                               "砖块", "breakout", "arena", "rift", "miner", "dock",
                               "rogue", "survival"]):
        return "game"
    if any(k in text for k in ["工具", "tool", "下载", "管理", "切换", "助手", "helper",
                               "manager", "switch", "refresh", "cli"]):
        return "tool"
    if any(k in text for k in ["学习", "学院", "academy", "课程", "course", "kata"]):
        return "app"
    if any(k in text for k in ["日志", "记录", "log", "journal", "devlog", "vault", "note"]):
        return "note"
    if lang == "GDScript":
        return "game"
    if any(k in text for k in ["网站", "导航", "web", "site", "tools"]):
        return "web"
    return "tool" if lang == "Python" else "web"


def guess_url(repo_full):
    """线上地址：先看 homepage 字段，再看 CNAME 文件。"""
    try:
        info = api(f"repos/{repo_full}")
        hp = (info.get("homepage") or "").strip()
        if hp.startswith("http"):
            return hp
    except Exception:
        pass
    try:
        dom = api_text(f"repos/{repo_full}/contents/CNAME")
        if dom and dom.strip():
            return f"https://{dom.strip()}"
    except Exception:
        pass
    return None


def count_commits(repo_full):
    """作者提交总数（与既有数据同源：search/commits author 过滤）。"""
    r = api(f"search/commits?q=repo:{repo_full}+author:{OWNER}&per_page=1", retries=3)
    return r.get("total_count", 0)


def sync_projects(workdir, repos, state, today):
    """更新 projects.json，返回变化描述列表。"""
    pj_path = os.path.join(workdir, "src/data/projects.json")
    with open(pj_path, encoding="utf-8") as f:
        data = json.load(f)
    projects = data["projects"]
    by_name = {p["name"]: p for p in projects}
    changes = []
    state_repos = state.get("repos", {})

    for r in repos:
        if r.get("fork"):
            continue
        name = r["name"]
        if name in EXCLUDE_REPOS:
            continue
        full = f"{OWNER}/{name}"
        vis = "private" if r.get("private") else "public"
        branch = r.get("default_branch", "main")
        pushed = (r.get("pushed_at") or "")[:10]
        created = (r.get("created_at") or "")[:10]
        days = 0
        if pushed and created:
            days = max(0, (datetime.strptime(pushed, "%Y-%m-%d")
                           - datetime.strptime(created, "%Y-%m-%d")).days)
        lang = r.get("language") or "—"

        if name not in by_name:
            # ── 新仓库：自动录入 ──
            url = guess_url(full)
            entry = {
                "name": name,
                "kind": guess_kind(name, r.get("description"), lang),
                "desc": (r.get("description") or "（待补充介绍）").strip(),
                "lang": lang,
                "visibility": vis,
                "created": created,
                "pushed": pushed,
                "days": days,
                "status": "building",
                "commits": 0,
                "url": url,
                "intro": (r.get("description") or "新仓库，介绍待补充。").strip(),
                "note": f"自动录入于 {today}（GitHub 新仓库检测）。定性内容待手写润色。",
            }
            if vis == "public":
                entry["zip"] = f"https://github.com/{full}/archive/refs/heads/{branch}.zip"
            projects.append(entry)
            by_name[name] = entry
            changes.append(f"新仓库录入：{name}（{vis}）")
            log(f"  ＋ 新仓库 {name} → 自动录入")
            try:
                entry["commits"] = count_commits(full)
                log(f"    {name} 提交数：{entry['commits']}")
            except Exception as e:
                log(f"    ⚠️ {name} 提交数获取失败：{e}")
            continue

        # ── 已有仓库：刷新定量字段 ──
        p = by_name[name]
        old_pushed = p.get("pushed")
        old_vis = p.get("visibility")
        if old_pushed != pushed:
            p["pushed"] = pushed
            changes.append(f"{name}: pushed {old_pushed} → {pushed}")
        if p.get("days") != days:
            p["days"] = days
        if old_vis != vis:
            p["visibility"] = vis
            if vis == "public" and not p.get("zip"):
                p["zip"] = f"https://github.com/{full}/archive/refs/heads/{branch}.zip"
            if vis == "private":
                p.pop("zip", None)
            changes.append(f"{name}: 可见性 {old_vis} → {vis}")
        # pushed 变了（或 state 里没有）才重数提交，省 API
        prev = state_repos.get(name, {})
        if old_pushed != pushed or "commits" not in prev:
            try:
                c = count_commits(full)
                if p.get("commits") != c:
                    changes.append(f"{name}: commits {p.get('commits')} → {c}")
                    p["commits"] = c
                log(f"  ↻ {name} 重数提交：{c}")
            except Exception as e:
                log(f"  ⚠️ {name} 提交重数失败，保留旧值：{e}")

    # 博客自身不算「项目」：万一历史上被录进去过，这里清掉
    projects = [p for p in projects if p["name"] not in EXCLUDE_REPOS]

    data["projects"] = projects
    with open(pj_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return changes


# ── Step 4：账本（revenue/progress.md → ledger.js）────────────────────

AFFILIATE_NOTE_KEEP = {
    # tool -> note（手写备注，源 md 里没有，重生时保留）
    "Rytr": "第一个拿下的联盟链接",
    "AppSumo": "被拒：新网站缺乏流量",
    "ElevenLabs": "被拒：网吧 IP 风控误判",
    "Descript": "同上",
    "Jasper": "无下文",
    "Copy.ai": "无下文",
}


def sync_ledger(workdir):
    """从 revenue/progress.md 重生 ledger.js。返回是否变化。"""
    try:
        md = api_text(f"repos/{LEDGER_SRC}/contents/revenue/progress.md")
        if md is None:
            raise RuntimeError("404")
    except Exception as e:
        log(f"  ⚠️ 读不到 revenue/progress.md，账本不更新（{e}）")
        return False

    income_rows, cost_rows, aff_rows = [], [], []
    section = None
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("## "):
            section = s
            continue
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2 or all(set(c) <= set("-: ") for c in cells):
            continue
        if "收入记录" in (section or ""):
            income_rows.append(cells)
        elif "成本明细" in (section or ""):
            cost_rows.append(cells)
        elif "联盟申请" in (section or ""):
            aff_rows.append(cells)

    def clean(v):
        return "" if v in ("—", "-", "–") else v

    income = []
    for c in income_rows:
        if len(c) < 3 or clean(c[0]) == "":
            continue
        try:
            amt = float(c[2].replace("¥", "").replace(",", ""))
        except ValueError:
            continue
        income.append({"date": c[0], "source": c[1], "amount": amt,
                       "note": clean(c[3]) if len(c) > 3 else ""})

    costs = []
    for c in cost_rows:
        if len(c) < 3 or clean(c[0]) == "":
            continue
        try:
            amt = abs(float(c[2].replace("¥", "").replace(",", "").lstrip("-")))
        except ValueError:
            continue
        costs.append({"date": c[0], "item": c[1], "amount": amt,
                      "note": clean(c[3]) if len(c) > 3 else ""})

    aff = []
    for c in aff_rows:
        # 表头行（平台/工具/佣金/申请日期/…）没有日期，挡掉
        if len(c) < 5 or not re.match(r"\d{4}-\d{2}-\d{2}", c[3]):
            continue
        status = "pending"
        if "✅" in c[4] or "已获批" in c[4]:
            status = "approved"
        elif "❌" in c[4] or "被拒" in c[4]:
            status = "rejected"
        aff.append({
            "platform": c[0], "tool": c[1], "commission": c[2],
            "date": c[3], "status": status,
            "note": AFFILIATE_NOTE_KEEP.get(c[1], clean(c[4])),
        })

    js = [
        "/**",
        " * 收支账本（本文件由 scripts/daily_sync.py 根据 devlog-private/revenue/progress.md 自动生成，勿手改）",
        " * 投入和收入分开记 —— 不合并，不互相抵消。",
        " *",
        " * 关于「跑车收入」：这是每天生活的底，不是项目的收入，所以单独记在这里做背景。",
        " * 最近两个月一天平均 30 块左右；5 月份行情好时一天能跑 100~150 块。",
        " * 下文 costs / income 只记「项目相关的钱」，跑车收入不混进去。",
        " */",
        "",
        "// 跑车日收入（背景，不参与项目盈亏计算）",
        "export const runIncome = [",
        '  { period: "2026-05", avg: "100~150 / 天", note: "行情好的月份" },',
        '  { period: "2026-08 → 10", avg: "≈30 / 天", note: "最近两个月，收入在往下走" },',
        "];",
        "",
        "export const costs = [",
    ]
    for c in costs:
        js.append(f'  {{ date: "{c["date"]}", item: {json.dumps(c["item"], ensure_ascii=False)}, '
                  f'amount: {c["amount"]}, note: {json.dumps(c["note"], ensure_ascii=False)} }},')
    js += ["];", "", "export const income = ["]
    if not income:
        js.append("  // 目前一条都没有。")
        js.append("  // 第一笔进来的时候，往这里加：")
        js.append('  // { date: "2026-XX-XX", source: "来源", amount: 12.5, note: "备注" },')
    for i in income:
        js.append(f'  {{ date: "{i["date"]}", source: {json.dumps(i["source"], ensure_ascii=False)}, '
                  f'amount: {i["amount"]}, note: {json.dumps(i["note"], ensure_ascii=False)} }},')
    js += ["];", "", "export const affiliate = ["]
    for a in aff:
        js.append(f'  {{ platform: {json.dumps(a["platform"], ensure_ascii=False)}, '
                  f'tool: {json.dumps(a["tool"], ensure_ascii=False)}, '
                  f'commission: {json.dumps(a["commission"], ensure_ascii=False)}, '
                  f'date: "{a["date"]}", status: "{a["status"]}", '
                  f'note: {json.dumps(a["note"], ensure_ascii=False)} }},')
    js += [
        "];",
        "",
        "// 自动计算，以后加数据不用改页面",
        "export const totalCost = costs.reduce((s, c) => s + c.amount, 0);",
        "export const totalIncome = income.reduce((s, c) => s + c.amount, 0);",
        "export const net = totalIncome - totalCost;",
        "",
    ]
    content = "\n".join(js)

    path = os.path.join(workdir, "src/data/ledger.js")
    with open(path, encoding="utf-8") as f:
        old = f.read()
    if old == content:
        log("  账本无变化")
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"  账本已更新：投入 ¥{round(sum(c['amount'] for c in costs), 2)} / "
        f"收入 ¥{round(sum(i['amount'] for i in income), 2)} / 联盟 {len(aff)} 条")
    return True


# ── Step 5：stats.js ──────────────────────────────────────────────────

def ledger_totals(workdir):
    """从当前 ledger.js 源码取 totalCost / totalIncome。"""
    with open(os.path.join(workdir, "src/data/ledger.js"), encoding="utf-8") as f:
        src = f.read()
    # 去掉注释行——占位示例里也有 amount: 12.5，不能算进收入
    src = re.sub(r"^\s*//.*$", "", src, flags=re.M)

    def amounts(arr):
        m = re.search(rf"export const {arr} = \[(.*?)\];", src, re.S)
        return [float(x) for x in re.findall(r"amount:\s*([0-9.]+)", m.group(1))] if m else []

    return round(sum(amounts("costs")), 2), round(sum(amounts("income")), 2)


def sync_stats(workdir, projects, repos, today):
    days = (datetime.strptime(today, "%Y-%m-%d")
            - datetime.strptime(START_DATE, "%Y-%m-%d")).days
    commits = sum(p.get("commits", 0) for p in projects)
    stats = {
        "asOf": today,
        "days": days,
        "projects": len(projects),
        "repos": len([r for r in repos if not r.get("fork")]),
        "commits": commits,
        "commitBucket": f"{commits // 100 * 100}+",
        "cost": ledger_totals(workdir)[0],
        "income": ledger_totals(workdir)[1],
        "online": len([p for p in projects if p.get("url")]),
    }
    js = ("/**\n"
          " * 全站统计数字 —— 由 scripts/daily_sync.py 每天 18:00 自动生成，勿手改。\n"
          " * 数据来源：GitHub API（仓库 / 提交）+ devlog-private/revenue/progress.md（收支）。\n"
          " * 页面一律从这里读数字，不再硬编码——脚本换数，全站跟着变。\n"
          " */\n"
          f"export const stats = {json.dumps(stats, ensure_ascii=False, indent=2)};\n")
    path = os.path.join(workdir, "src/data/stats.js")
    with open(path, encoding="utf-8") as f:
        old = f.read()
    if old == js:
        log("  stats 无变化")
        return False, stats
    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    log(f"  stats 已更新：{stats['days']} 天 / {stats['projects']} 项目 / "
        f"{stats['commits']} 提交 / ¥{stats['cost']} / ¥{stats['income']}")
    return True, stats


# ── Step 6：流水账日记 ────────────────────────────────────────────────

def fetch_repo_commits(full, since_iso):
    """窗口内本人的提交（首行消息列表）。"""
    try:
        arr = api(f"repos/{full}/commits?since={since_iso}&per_page=100")
    except Exception as e:
        log(f"  ⚠️ {full} 提交拉取失败：{e}")
        return []
    if not isinstance(arr, list):
        return []
    out = []
    for c in arr:
        login = (c.get("author") or {}).get("login")
        name = ((c.get("commit") or {}).get("author") or {}).get("name", "")
        if login == OWNER or (login is None and OWNER in name.lower()):
            first = ((c.get("commit") or {}).get("message", "") or "").splitlines()
            first = first[0].strip() if first else ""
            if first:
                if len(first) > 70:
                    cut = first[:67]
                    for sep in ("，", "、", ";", " ", ",", "(", "（"):
                        idx = cut.rfind(sep)
                        if idx >= 40:
                            cut = cut[:idx]
                            break
                    first = cut + "…"
                out.append(first)
    return out


def write_diary(workdir, repos, state, stats, today):
    """生成/覆盖当日流水账。返回 (是否写了, 窗口内提交总数)。"""
    now = now_tz()
    today_0000 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_run = None
    if state.get("last_run"):
        try:
            last_run = datetime.fromisoformat(state["last_run"])
        except ValueError:
            last_run = None
    if last_run is None:
        window_start = now - timedelta(hours=36)   # 首次运行：回溯一天半兜底
    elif last_run >= today_0000:
        window_start = today_0000                  # 当天重跑：看全天
    else:
        window_start = last_run                     # 正常每日：自上次以来

    since_iso = iso_utc(window_start)
    log(f"  日记窗口：{window_start.strftime('%m-%d %H:%M')} → {now.strftime('%m-%d %H:%M')}")

    active = [r for r in repos if not r.get("fork")
              and (r.get("pushed_at") or "") >= since_iso]
    if not active:
        log("  窗口内无仓库变动，不写日记")
        return False, 0

    sections = []
    total_commits = 0
    for r in sorted(active, key=lambda x: x["name"]):
        msgs = fetch_repo_commits(f"{OWNER}/{r['name']}", since_iso)
        sections.append((r["name"], msgs or None))
        total_commits += len(msgs)

    post_path = os.path.join(workdir, f"src/content/posts/{today}-{DIARY_SLUG}.mdx")
    if total_commits == 0:
        # 只有非提交类变动：已有今天的日记就保留，否则不写
        if os.path.exists(post_path):
            log("  窗口内只有非提交类变动，保留已有日记")
        else:
            log("  窗口内无提交，不写日记")
        return False, 0

    top_name, top_msgs = max(sections, key=lambda s: len(s[1]) if s[1] else 0)
    summary = f"{len(sections)} 个仓库动了，+{total_commits} 次提交。{top_name} +{len(top_msgs)}。"

    def fmt_window(dt):
        return f"{dt.month} 月 {dt.day} 日 {dt.strftime('%H:%M')}"

    lines = [
        "---",
        f'title: "流水账 · {today}"',
        f"date: {today}",
        f"summary: {json.dumps(summary, ensure_ascii=False)}",
        'tags: ["流水账", "自动记录"]',
        "---",
        "",
        "> 本条由脚本根据 GitHub 提交记录自动生成——仓库动了，账就记上。",
        "> 想看我当时怎么想的，去翻手写的那些篇。",
        "",
        "## 今天动了什么",
        "",
    ]
    for name, msgs in sections:
        if msgs:
            lines.append(f"**{name}**（+{len(msgs)}）")
            lines += [f"- {m}" for m in msgs]
        else:
            lines.append(f"**{name}**（有推送，无新提交）")
        lines.append("")
    lines += [
        "## 数字",
        "",
        f"- 统计窗口：{fmt_window(window_start)} → {fmt_window(now)}",
        f"- 本次提交：{total_commits} 次 · {len(sections)} 个仓库",
        f"- 累计提交：{stats['commits']} 次",
        f"- 项目：{stats['projects']} 个（{stats['online']} 个在线可访问）",
        f"- 坚持天数：第 {stats['days']} 天",
        f"- 累计收入：¥{stats['income']}",
        "",
    ]
    if stats["income"] == 0:
        lines += ["收入那一行还空着。第一笔进来的时候，这里会变。", ""]
    content = "\n".join(lines)

    old = None
    if os.path.exists(post_path):
        with open(post_path, encoding="utf-8") as f:
            old = f.read()
    if old == content:
        log("  日记内容无变化")
        return False, total_commits
    with open(post_path, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"  日记已{'更新' if old else '生成'}：{os.path.basename(post_path)}（+{total_commits} 提交）")
    return True, total_commits


# ── Step 7：og-image（best-effort）────────────────────────────────────

def sync_og_image(workdir, stats):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log("  PIL 不可用，跳过 og-image")
        return False
    W, H = 1200, 630
    BG, TEXT, DIM, AMBER = (14, 13, 17), (236, 235, 232), (164, 163, 173), (240, 180, 41)
    FB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
    FR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

    def font(path, size):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    glow = Image.new("RGB", (W, H), BG)
    gd = ImageDraw.Draw(glow)
    for r in range(320, 0, -8):
        a = int(26 * (1 - r / 320) ** 2)
        gd.ellipse([-160 - r, -160 - r, 260 + r, 260 + r],
                   fill=(BG[0] + a, BG[1] + int(a * 0.85), BG[2] + int(a * 0.4)))
    img = Image.blend(img, glow, 0.9)
    d = ImageDraw.Draw(img)
    d.rectangle([80, 150, 300, 153], fill=AMBER)
    f40, f68, f34 = font(FB, 40), font(FB, 68), font(FB, 34)
    d.text((80, 96), "cafeaitools", font=f40, fill=TEXT)
    d.text((80 + d.textlength("cafeaitools", font=f40), 96), ".com", font=f40, fill=AMBER)
    d.text((80, 210), "保定出租车司机，", font=f68, fill=TEXT)
    d.text((80, 296), "一天 30 块。", font=f68, fill=AMBER)
    d.text((80, 404), "用 AI 做产品与游戏的真实记录。", font=font(FR, 40), fill=DIM)
    parts = [f"{stats['days']} 天", f"{stats['projects']} 个项目",
             f"投入 ¥{stats['cost']}", f"收入 ¥{stats['income']}"]
    x = 80
    for i, t in enumerate(parts):
        d.text((x, 500), t, font=f34, fill=TEXT if i < 2 else DIM)
        x += d.textlength(t, font=f34) + 18
        if i < len(parts) - 1:
            d.text((x, 500), "·", font=f34, fill=DIM)
            x += d.textlength("·", font=f34) + 18

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    new_bytes = buf.getvalue()
    path = os.path.join(workdir, "public/og-image.png")
    with open(path, "rb") as f:
        old = f.read()
    if old == new_bytes:
        log("  og-image 无变化")
        return False
    with open(path, "wb") as f:
        f.write(new_bytes)
    log(f"  og-image 已刷新（{stats['days']} 天 · {stats['projects']} 个项目）")
    return True


# ── Step 8：构建 ──────────────────────────────────────────────────────

def run_build(workdir):
    if shutil.which("npm") is None:
        log("  ⚠️ 环境无 npm，跳过本地构建（CI 会构建；CI 失败则站点保持旧版，不会坏）")
        return True
    for attempt in (1, 2):
        log(f"  npm ci（第 {attempt} 次）…")
        p = subprocess.run(["npm", "ci"], cwd=workdir, capture_output=True, text=True)
        if p.returncode == 0:
            break
    else:
        log(f"  ❌ npm ci 失败：{p.stderr[-400:]}")
        return False
    log("  npm run build …")
    p = subprocess.run(["npm", "run", "build"], cwd=workdir, capture_output=True, text=True)
    if p.returncode != 0:
        log(f"  ❌ 构建失败：{p.stderr[-600:]}")
        return False
    log("  构建通过")
    return True


# ── Step 9：单次提交推送 ──────────────────────────────────────────────

def push_commit(workdir, files, message):
    ref = api(f"repos/{REPO}/git/ref/heads/{BRANCH}")
    commit_sha = ref["object"]["sha"]
    base_tree = api(f"repos/{REPO}/git/commits/{commit_sha}")["tree"]["sha"]
    tree_items = []
    for rel in files:
        with open(os.path.join(workdir, rel), "rb") as f:
            content = base64.b64encode(f.read()).decode()
        blob = api(f"repos/{REPO}/git/blobs", {"content": content, "encoding": "base64"})
        tree_items.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = api(f"repos/{REPO}/git/trees", {"base_tree": base_tree, "tree": tree_items})
    new_commit = api(f"repos/{REPO}/git/commits",
                     {"message": message, "tree": new_tree["sha"], "parents": [commit_sha]})
    api(f"repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": new_commit["sha"]})
    return new_commit["sha"][:7]


def remote_changed(workdir, rel):
    """本地文件与远程版本是否不同（远程没有 = 不同）。"""
    path = os.path.join(workdir, rel)
    if not os.path.exists(path):
        return False
    with open(path, "rb") as f:
        local_b64 = base64.b64encode(f.read()).decode()
    r = api(f"repos/{REPO}/contents/{rel}?ref={BRANCH}", retries=2, ok_404=True)
    if r is None:
        return True  # 远程没有这个文件（如当天日记）
    return local_b64 != r.get("content", "").replace("\n", "")


# ── 主流程 ────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    today = today_str()
    log(f"===== daily_sync {today} =====")

    if not _HAS_GH and not (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")):
        log("❌ 既没有 gh CLI 也没有 GITHUB_TOKEN 环境变量，无法调用 API")
        return 1
    me = api("user")
    log(f"认证：{me.get('login')}")

    workdir = tempfile.mkdtemp(prefix="cafe-daily-")
    try:
        download_repo(workdir)

        state = {}
        state_path = os.path.join(workdir, STATE_PATH)
        if os.path.exists(state_path):
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)

        repos = api("user/repos?sort=pushed&per_page=100")
        log(f"仓库总数：{len(repos)}")

        # 1) 项目数据
        proj_changes = sync_projects(workdir, repos, state, today)
        with open(os.path.join(workdir, "src/data/projects.json"), encoding="utf-8") as f:
            projects = json.load(f)["projects"]

        # 2) 账本
        ledger_changed = sync_ledger(workdir)

        # 3) 统计
        stats_changed, stats = sync_stats(workdir, projects, repos, today)

        # 4) 日记
        diary_written, diary_commits = write_diary(workdir, repos, state, stats, today)

        # 5) og-image
        og_changed = sync_og_image(workdir, stats)

        # 6) 构建验证
        if not run_build(workdir):
            log("❌ 构建未通过，本次不推送（站点保持当前版本）")
            return 1

        # 7) 汇总变更文件（与远程逐字节比对）
        candidates = [
            "src/data/projects.json",
            "src/data/ledger.js",
            "src/data/stats.js",
            f"src/content/posts/{today}-{DIARY_SLUG}.mdx",
            "public/og-image.png",
        ]
        changed = [rel for rel in candidates if remote_changed(workdir, rel)]

        if not changed:
            log("今日无变化，不推送")
            report(today, stats, diary_written, diary_commits, proj_changes,
                   ledger_changed, og_changed, pushed=False)
            return 0

        # 8) state 一并提交
        state["last_run"] = now_tz().isoformat()
        commits_by_name = {p["name"]: p.get("commits") for p in projects}
        state["repos"] = {
            r["name"]: {"pushed_at": r.get("pushed_at"),
                        "commits": commits_by_name.get(r["name"])}
            for r in repos if not r.get("fork")
        }
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.write("\n")
        changed.append(STATE_PATH)

        msg = f"chore(daily): 自动同步 {today}"
        bits = []
        if proj_changes:
            bits.append(f"{len(proj_changes)} 项数据变动")
        if diary_written:
            bits.append(f"日记 +{diary_commits} 提交")
        if ledger_changed:
            bits.append("账本更新")
        if og_changed:
            bits.append("og-image")
        if bits:
            msg += "（" + " · ".join(bits) + "）"

        sha = push_commit(workdir, changed, msg)
        log(f"✅ 已推送 {sha}：{', '.join(changed)}")
        report(today, stats, diary_written, diary_commits, proj_changes,
               ledger_changed, og_changed, pushed=True, sha=sha)
        log(f"总耗时 {time.time() - t0:.0f}s")
        return 0
    finally:
        pass  # workdir 保留便于排查


def report(today, stats, diary, diary_commits, proj_changes,
           ledger_changed, og_changed, pushed, sha=None):
    print("\n========== 汇报 ==========")
    print(f"日期：{today}（第 {stats['days']} 天）")
    print(f"仓库：{stats['repos']} 个 · 项目：{stats['projects']} 个 · 累计提交：{stats['commits']}")
    print(f"收支：投入 ¥{stats['cost']} / 收入 ¥{stats['income']}")
    print(f"日记：{'已生成' if diary else '无'}（窗口内 +{diary_commits} 提交）")
    if proj_changes:
        print("数据变动：")
        for c in proj_changes:
            print(f"  - {c}")
    if ledger_changed:
        print("账本：已从 revenue/progress.md 更新")
    if og_changed:
        print("og-image：已刷新")
    print(f"推送：{'是 ' + sha if pushed else '否（无变化）'}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"❌ 运行失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
