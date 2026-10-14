# 部署状态

## ✅ 已上线

| 项 | 值 |
|:---|:---|
| **正式网址** | **https://cafeaitools.com** |
| www | https://www.cafeaitools.com （自动跳转） |
| 备用地址 | https://cafe-log-9ce.pages.dev |
| 平台 | Cloudflare Pages |
| 状态 | 两个域名均 `active`，证书已签发（Google CA） |

全站 7 个页面已验证返回 200：
`/`、`/timeline/`、`/ledger/`、`/projects/`、`/posts/`、`/about/`、`/posts/2026-10-15-facing-myself/`

---

## 部署信息（以后更新用）

```
Cloudflare Account ID : 22b57986d4c786f3a92f2e9652a6c986
Pages 项目名          : cafe-log
生产分支              : main
cafeaitools.com Zone  : e6fa6883ef054dc79884164c0e232490
```

API Token 已保存在：
- `~/.zshrc.d/cloudflare_token.sh`
- `~/.bashrc.d/cloudflare_token.sh`

（权限 600，导出 `CLOUDFLARE_API_TOKEN` / `CF_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`）

---

## 以后怎么更新网站

### 方式一：一行命令（推荐）

改完内容后，在项目根目录执行：

```bash
cd cafe-log
npm run build
npx wrangler pages deploy dist --project-name cafe-log --branch main
```

Wrangler 会自动读取环境变量里的 token，不用再登录。
部署完约 30 秒生效。

### 方式二：连 GitHub 自动部署

在 Cloudflare Dashboard → Workers & Pages → cafe-log → **连接到 Git**，
选 `xiaomo945/cafe-log` 仓库，以后 push 就自动部署。

构建配置填：
```
构建命令     : npm run build
输出目录     : dist
```

> 注意：两种方式选一个。如果接了 Git，之后就用 push 触发，
> 不要再手动 `wrangler deploy`，否则会冲突。

---

## DNS 记录现状

| 类型 | 名称 | 指向 | 说明 |
|:---|:---|:---|:---|
| CNAME | cafeaitools.com | cafe-log-9ce.pages.dev | 根域名，走 CNAME flattening |
| CNAME | www.cafeaitools.com | cafeaitools.com | 跟主域名走 |

> 原本有一条 `A cafeaitools.com → 47.76.60.100`，
> 探测确认该 IP 已无服务响应（连接超时、域名返回 521），
> 属于失效记录，已安全替换为 CNAME。

---

## 域名成本

`cafeaitools.com` 是 2026-05-15 购入的，¥85。
当时在收支表里标注为「未来项目」——现在它成了这个站。
