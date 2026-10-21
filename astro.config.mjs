import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import { readdirSync, writeFileSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = "https://cafeaitools.com";

/**
 * 自己生成 sitemap —— 不引入 @astrojs/sitemap 依赖。
 * 原因：CI 用 `npm ci`，加依赖必须同步 package-lock.json，风险高。
 * 做法：构建完成后扫描 dist/ 里真实产出的 index.html，还原成 URL 列表。
 * 好处：以后每天自动新增的日记，无需改任何代码就能被 sitemap 收录。
 */
function sitemapIntegration() {
  return {
    name: "cafe-sitemap",
    hooks: {
      "astro:build:done": async ({ dir, logger }) => {
        const outDir = fileURLToPath(dir);

        // 递归收集所有文件
        const walk = (d) =>
          readdirSync(d, { withFileTypes: true }).flatMap((e) => {
            const p = join(d, e.name);
            return e.isDirectory() ? walk(p) : [p];
          });

        const files = walk(outDir);

        // 只收录 index.html（静态站每个页面都会产出 <dir>/index.html）
        const urls = files
          .filter((f) => f.endsWith("index.html"))
          .map((f) => {
            const rel = relative(outDir, f).split(sep).join("/");
            const dirPath = rel.replace(/index\.html$/, ""); // "about/" 或 ""
            return dirPath ? `${SITE}/${dirPath}` : `${SITE}/`;
          })
          .filter((u) => !u.includes("404"))
          .filter((u, i, arr) => arr.indexOf(u) === i) // 去重
          .sort();

        const today = new Date().toISOString().slice(0, 10);

        const urlset = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (u) => `  <url>
    <loc>${u}</loc>
    <lastmod>${today}</lastmod>
  </url>`
  )
  .join("\n")}
</urlset>
`;

        writeFileSync(join(outDir, "sitemap.xml"), urlset, "utf8");

        // 同时产出 sitemap-index.xml（兼容 robots.txt 里历史上的声明，避免 404）
        const index = `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>${SITE}/sitemap.xml</loc>
    <lastmod>${today}</lastmod>
  </sitemap>
</sitemapindex>
`;
        writeFileSync(join(outDir, "sitemap-index.xml"), index, "utf8");

        logger.info(`sitemap.xml 已生成：${urls.length} 条 URL`);
      },
    },
  };
}

export default defineConfig({
  site: SITE,
  output: "static",
  integrations: [mdx(), sitemapIntegration()],
  markdown: {
    shikiConfig: {
      theme: "github-dark",
      wrap: true,
    },
  },
  build: {
    // 输出纯静态，Vercel 直接托管
    format: "directory",
  },
});
