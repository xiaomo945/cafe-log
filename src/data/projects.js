/**
 * 项目数据加载器 —— 数据本体在 projects.json。
 *
 * - 定量字段（pushed / days / commits / visibility / url / zip）：
 *   由 scripts/daily_sync.py 每天 18:00 自动更新，勿手改（改了会被覆盖）。
 * - 定性字段（kind / desc / intro / note / status）：手写维护；
 *   新仓库由脚本自动录入（note 里带「自动录入」字样），欢迎随时润色。
 */
import data from "./projects.json" with { type: "json" };

export const projects = data.projects;

// 统计
export const totalCommits = projects.reduce((s, p) => s + (p.commits || 0), 0);
export const byStatus = (s) => projects.filter((p) => p.status === s);
export const publicCount = projects.filter((p) => p.visibility === "public").length;
export const privateCount = projects.filter((p) => p.visibility === "private").length;
export const hasLiveUrl = projects.filter((p) => p.url).length;
