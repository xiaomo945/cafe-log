# 部署状态

## ✅ 已上线 · Git 自动部署

| 项 | 值 |
|:---|:---|
| **网址** | **https://cafeaitools.com** |
| www | https://www.cafeaitools.com |
| 备用 | https://cafeaitools.pages.dev |
| 平台 | Cloudflare Pages |
| 部署方式 | **push 到 GitHub 自动触发** |

7 个页面全部 200。

---

## 自动部署怎么工作

```
你改内容 → git push 到 main
              ↓
   GitHub Actions 自动触发（.github/workflows/deploy.yml）
              ↓
   npm ci → npm run build → wrangler pages deploy
              ↓
   Cloudflare Pages 更新，约 30 秒生效
```

**你只需要做一件事：`git push`。**

在 GitHub 网页上也能手动触发：
仓库 → Actions → 「部署到 Cloudflare Pages」→ Run workflow

---

## 部署信息

```
Cloudflare Account ID : 22b57986d4c786f3a92f2e9652a6c986
Pages 项目名          : cafeaitools
Pages 地址            : cafeaitools.pages.dev
GitHub 仓库           : xiaomo945/cafe-log
生产分支              : main
构建命令              : npm run build
输出目录              : dist
```

**仓库 Secrets**（已配置，Actions 用）：
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

本地 token 也在：
- `~/.zshrc.d/cloudflare_token.sh`
- `~/.bashrc.d/cloudflare_token.sh`

---

## 日常更新

```bash
# 写完文章后
git add .
git commit -m "日志：xxx"
git push
```

推完等 1~2 分钟，刷新 https://cafeaitools.com 就能看到。

想看构建过程：https://github.com/xiaomo945/cafe-log/actions

---

## 本地预览

```bash
npm run dev    # http://localhost:4321
```

---

## 踩过的坑（都解决了）

### 1. 直接上传项目无法改成 Git 源

Cloudflare 限制：Direct Uploads 项目的 `source` 不可修改，
报 `You cannot update the source object in a Direct Uploads project`。

**解决**：新建了一个 Git 源项目 `cafeaitools`，构建成功后把域名切过去，
再删掉旧的 `cafe-log` 项目。切换期间网站未中断。

### 2. Cloudflare 原生 Git 集成没有真正生效

API 显示项目已连 GitHub，但仓库里查不到任何 webhook（`hooks` 返回 `[]`）——
说明 Cloudflare 的 GitHub App 授权没覆盖到这个新建的仓库，推送不会触发构建。

**解决**：改用 GitHub Actions 部署，不依赖 OAuth 授权，完全可控。

> 如果以后想在 Cloudflare Dashboard 里也看到构建记录，
> 需要去 GitHub → Settings → Applications → Cloudflare Pages → Configure，
> 把 `cafe-log` 加进授权仓库列表。
> **注意**：那样会和 Actions 重复部署，二选一即可。

### 3. 缺 package-lock.json 导致 CI 失败

`npm ci` 需要 lock 文件，第一次上传时漏了，Actions 报
`Dependencies lock file is not found`。补传后正常。

---

## DNS 记录

| 类型 | 名称 | 指向 |
|:---|:---|:---|
| CNAME | cafeaitools.com | cafeaitools.pages.dev |
| CNAME | www.cafeaitools.com | cafeaitools.com |

> 原有一条 `A cafeaitools.com → 47.76.60.100`（已无服务响应），已替换。
