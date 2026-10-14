import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";

export default defineConfig({
  site: "https://cafeeai.tools",
  output: "static",
  integrations: [mdx()],
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
