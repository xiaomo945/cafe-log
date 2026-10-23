# cafeaitools.com

保定出租车司机，一天 30 块，用 AI 做产品与游戏的**全程公开记录站**。

不是技术博客——是一个「普通人每天拱一点」的实验档案：今天做了什么、砸了多少钱、收入到账了没有，全部摊开。

## 站点内容

| 页面 | 内容 |
|:---|:---|
| `/` | 起点：项目数、累计提交、投入产出，一眼看全貌 |
| `/projects/` | 22 个项目的花名册：能玩的给网址，公开仓库给 ZIP 直下载 |
| `/timeline/` | 按 git 时间戳排的成长线 |
| `/ledger/` | 收支账本：域名钱、联盟申请、收入（目前还是 ¥0） |
| `/growth/` | 阶段性复盘 |
| `/about/` | 我是谁、为什么这么干 |
| `/posts/` | 手写长文 + 每日流水账 |

## 每日自动更新（18:00）

仓库里挂着 `scripts/daily_sync.py`，由定时任务每天 18:00 自动执行：

1. 抓 GitHub 全部仓库与提交 → 刷新 `src/data/projects.json`（新仓库自动录入花名册）
2. 从 `devlog-private/revenue/progress.md` 重生账本 `src/data/ledger.js`
3. 汇总全站数字 → `src/data/stats.js`
4. 生成当日流水账日记（`src/content/posts/YYYY-MM-DD-daily-log.mdx`）
5. 刷新 og-image 底部数据条
6. `npm run build` 验证 → **有变化才**通过 Git Data API 单次提交推送

设计原则：幂等（重跑不重复）、无变化不推送、构建不过不推送（站点保持旧版不会坏）。

> `src/data/` 下的文件全部由脚本生成，**不要手改**。

## 本地开发

```bash
npm install
npm run dev      # 本地预览
npm run build    # 构建到 dist/
```

技术栈：Astro 4 + 内容集合（`src/content/posts/*.mdx`）+ 数据驱动（页面数字全部读 `src/data/`，无硬编码）。

## 手动跑一次同步

```bash
python3 scripts/daily_sync.py
```

需要 gh CLI 已认证（或 `GITHUB_TOKEN` 环境变量）。
