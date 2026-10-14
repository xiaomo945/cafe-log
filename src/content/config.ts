import { defineCollection, z } from "astro:content";

/**
 * 日志文章
 *
 * frontmatter 说明：
 *   title    标题（必填）
 *   date     日期（必填）
 *   summary  列表页显示的一句话摘要
 *   tags     标签数组
 *   draft    草稿，true 则不发布
 */
const posts = defineCollection({
  type: "content",
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    summary: z.string().optional(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
  }),
});

export const collections = { posts };
