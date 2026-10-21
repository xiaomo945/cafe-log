/**
 * 全站统计数字 —— 由 scripts/daily_sync.py 每天 18:00 自动生成，勿手改。
 * 数据来源：GitHub API（仓库 / 提交）+ devlog-private/revenue/progress.md（收支）。
 * 页面一律从这里读数字，不再硬编码——脚本换数，全站跟着变。
 */
export const stats = {
  asOf: "2026-10-21", // 数据日期（Asia/Shanghai）
  days: 163, // 距 2026-05-11 的天数
  projects: 21, // 产品仓数量
  repos: 24, // 全部仓库数（含 cafe-log / mind-vault / devlog-private）
  commits: 1469, // 总提交次数
  commitBucket: "1400+", // 提交数约数（ prose 用）
  cost: 438, // 累计投入 ¥
  income: 0, // 累计收入 ¥
  online: 7, // 在线可访问项目数
};
