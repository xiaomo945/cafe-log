# cafeaitools.com · 使用说明

站点源码已推送到 https://github.com/xiaomo945/cafe-log

---

## 一、部署到 Vercel（约 3 分钟）

1. 打开 https://vercel.com/new ，用 GitHub 账号登录
2. 找到 `xiaomo945/cafe-log`，点 **Import**
3. 构建配置**不用改** —— 仓库里已经有 `vercel.json`，Vercel 会自动识别为 Astro：
   - Build Command: `npm run build`
   - Output Directory: `dist`
4. 点 **Deploy**，等约 1 分钟

### 绑定域名 cafeaitools.com

部署成功后：

1. 进入项目 → **Settings** → **Domains**
2. 输入 `cafeaitools.com`，点 Add
3. Vercel 会提示需要添加的 DNS 记录，通常是：
   ```
   类型: A      名称: @      值: 216.198.79.1
   类型: CNAME  名称: www    值: cname.vercel-dns.com
   ```
4. 去你的域名注册商（或 Cloudflare，如果 NS 已经迁过去）添加这两条记录
5. 等 DNS 生效（几分钟到几小时），Vercel 会自动签发 SSL 证书

> 建议同时把 `www.cafeaitools.com` 也加上，Vercel 会自动做跳转。
> 这个域名是 2026-05-15 买的（¥85），当时标注「未来项目」——现在它派上用场了。

---

## 二、以后怎么写新文章

在 `src/content/posts/` 下新建一个 `.mdx` 文件，文件名就是网址：

```
src/content/posts/2026-10-20-我的标题.mdx
```

文件内容开头这样写：

```markdown
---
title: "文章标题"
date: 2026-10-20
summary: "列表页显示的一句话"
tags: ["标签1", "标签2"]
---

正文从这里开始。
```

然后 `git push`，Vercel 会自动重新部署。

**草稿**：加一行 `draft: true` 就不会发布。

---

## 三、怎么插视频（你要的功能）

在文章里想插视频的位置，写这一行就行：

```markdown
import VideoEmbed from '../../components/VideoEmbed.astro';

<VideoEmbed platform="youtube" id="dQw4w9WgXcQ" title="视频说明" />
```

支持的平台和写法：

| 平台 | 写法 | id 从哪找 |
|:---|:---|:---|
| YouTube | `platform="youtube" id="dQw4w9WgXcQ"` | 网址 `watch?v=` 后面那串 |
| TikTok | `platform="tiktok" id="7234567890123456789"` | 网址 `/video/` 后面那串数字 |
| B 站 | `platform="bilibili" id="BV1xx411c7mD"` | 就是 BV 号 |
| Vimeo | `platform="vimeo" id="123456789"` | 网址最后的数字 |
| 自己的视频文件 | `platform="file" src="/videos/xxx.mp4"` | 文件放 `public/videos/` 下 |

**每个视频都有两个功能**：
- 直接在文章里播放
- 右上角有个「在 XX 观看 ↗」的链接，点开跳到原平台

TikTok 的嵌入脚本是懒加载的 —— 滚到那个位置才加载，不影响页面速度。

---

## 四、怎么插图片

```markdown
import ImageFigure from '../../components/ImageFigure.astro';

<ImageFigure
  src="/img/2026-05-11/desk.jpg"
  alt="网吧的桌子"
  caption="2026-05-11，保定，就这样开始了"
/>
```

图片放 `public/img/` 下，建议按日期建文件夹。

想要通栏大图（超出正文宽度），加一个参数：

```markdown
<ImageFigure src="/img/xxx.jpg" alt="说明" caption="说明" width="full" />
```

---

## 五、改数字

时间线、收支、项目清单都在 `src/data/` 下，是三个普通的 JS 文件：

| 文件 | 改什么 |
|:---|:---|
| `src/data/timeline.js` | 时间线节点 |
| `src/data/ledger.js` | 投入、收入、联盟申请记录 |
| `src/data/projects.js` | 项目清单 |

**收入第一笔进来的时候**，改 `src/data/ledger.js` 里的 `income` 数组：

```js
export const income = [
  { date: "2026-10-20", source: "AdSense", amount: 3.5, note: "第一笔" },
];
```

页面上「还没有收入」那个卡片会自动替换成收入表格。

---

## 六、本地预览

```bash
cd cafe-log
npm install
npm run dev     # 打开 http://localhost:4321
```

---

## 七、技术栈（不用管，但要出问题知道找谁）

| 项 | 选择 | 为什么 |
|:---|:---|:---|
| 框架 | Astro 4 | 静态输出、Markdown 原生、SEO 好 |
| 内容格式 | MDX | 文章里能直接插视频/图片组件 |
| 样式 | 手写 CSS | 无框架依赖，加载快 |
| 部署 | Vercel | 免费、自动 HTTPS、push 即部署 |
| 域名 | cafeaitools.com | 2026-05-15 购入，¥85 |

选 Astro 4 而不是 5：Astro 5 要求 Node ≥ 22.19，Vercel 默认环境更稳的是 4.x。

---

## 八、以后想加的东西（现在没做，但留好了位置）

- **RSS 订阅**：装 `@astrojs/rss`，加一个 `src/pages/rss.xml.js`
- **站点地图**：装 `@astrojs/sitemap`（`robots.txt` 里已经写了 sitemap 地址，装上就生效）
- **评论**：接 Giscus（用 GitHub Discussions 当后端，免费）
- **访问统计**：接 Vercel Analytics 或 Umami
- **深色/浅色切换**：现在只有深色，要加的话改 `global.css` 的 CSS 变量
