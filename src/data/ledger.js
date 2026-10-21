/**
 * 收支账本（本文件由 scripts/daily_sync.py 根据 devlog-private/revenue/progress.md 自动生成，勿手改）
 * 投入和收入分开记 —— 不合并，不互相抵消。
 *
 * 关于「跑车收入」：这是每天生活的底，不是项目的收入，所以单独记在这里做背景。
 * 最近两个月一天平均 30 块左右；5 月份行情好时一天能跑 100~150 块。
 * 下文 costs / income 只记「项目相关的钱」，跑车收入不混进去。
 */

// 跑车日收入（背景，不参与项目盈亏计算）
export const runIncome = [
  { period: "2026-05", avg: "100~150 / 天", note: "行情好的月份" },
  { period: "2026-08 → 10", avg: "≈30 / 天", note: "最近两个月，收入在往下走" },
];

export const costs = [
  { date: "2026-05-11", item: "`useaitools.me`", amount: 135.0, note: "主站域名" },
  { date: "2026-05-15", item: "`tryouraitools.com`", amount: 85.0, note: "主推 .com" },
  { date: "2026-05-15", item: "`cafeaitools.com`", amount: 85.0, note: "未来项目" },
  { date: "2026-05-15", item: "`useaitools.net`", amount: 95.0, note: "品牌防守" },
  { date: "2026-05-15", item: "`useaitools.cn`", amount: 38.0, note: "国内防守" },
];

export const income = [
  // 目前一条都没有。
  // 第一笔进来的时候，往这里加：
  // { date: "2026-XX-XX", source: "来源", amount: 12.5, note: "备注" },
];

export const affiliate = [
  { platform: "平台", tool: "工具", commission: "佣金", date: "申请日期", status: "pending", note: "状态" },
  { platform: "Rytr 官网", tool: "Rytr", commission: "30% / 12个月", date: "2026-05-15", status: "approved", note: "第一个拿下的联盟链接" },
  { platform: "Impact", tool: "AppSumo", commission: "100%新用户", date: "2026-05-13", status: "rejected", note: "被拒：新网站缺乏流量" },
  { platform: "PartnerStack", tool: "ElevenLabs", commission: "22% / 12个月", date: "2026-05-13", status: "rejected", note: "被拒：网吧 IP 风控误判" },
  { platform: "PartnerStack", tool: "Descript", commission: "$25/次", date: "2026-05-13", status: "rejected", note: "同上" },
  { platform: "邮件申请", tool: "Jasper", commission: "待确认", date: "2026-05-15", status: "pending", note: "无下文" },
  { platform: "邮件申请", tool: "Copy.ai", commission: "待确认", date: "2026-05-15", status: "pending", note: "无下文" },
];

// 自动计算，以后加数据不用改页面
export const totalCost = costs.reduce((s, c) => s + c.amount, 0);
export const totalIncome = income.reduce((s, c) => s + c.amount, 0);
export const net = totalIncome - totalCost;
