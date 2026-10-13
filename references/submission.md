# 参赛发布步骤

核对日期：2026-10-13。发布前再次查看[官方活动入口](https://github.com/M-China/mcd-developer-innovation-challenge)和[活动规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)。本页是操作清单，不替代规则。

## 先完成真实验证

WorkBuddy 已在参赛者账号中报告门店、菜单、优惠、详情与算价调用；参赛者转交了一次算价的会话内入参和返回。见 workbuddy.md 和 MCP_INTEGRATION.md。公开报名前仍需在自己的环境中演示项目流程，并据实记载失败情形；旧价格不能作为当前有效报价。

## 公开项目

项目已发布于参赛者个人公开仓库：https://github.com/a2522945810-bot/mcd-budget-verified 。本目录内容位于仓库根目录。

保留 README.md、CONTEST_DECLARATION.md、MCP_INTEGRATION.md、mcp-config.example.json 及可运行源码。参赛者已确认同意官方声明；不要上传 private/、Token、完整券码、个人地址或原始账号记录。配置只有环境变量占位符。原创文件的 MIT 许可不覆盖官方材料。

若争取 WorkBuddy 专项奖励，按活动当时要求提交相应证据。当前 workbuddy.md 是参赛者提供的实际使用节选，标明了回述与独立日志之间的证据边界。

## 报名草稿

在官方活动仓库的指定 Issue 模板报名，截止为北京时间2026-10-25 23:59。报名正文：

```text
〖参赛申请〗
项目名称：麦当劳预算配餐助手
项目地址：https://github.com/a2522945810-bot/mcd-budget-verified
项目简介：按预算和口味偏好筛选一人到店取餐组合，通过麦当劳MCP查询菜单与优惠、核验候选应付价格，并说明报价时间和搜索覆盖范围。
```

标签与值保持同一行。即使报名成功，也须继续完成本项目的端到端现场演示；在此之前不可把历史报价作为实时价格宣传。

排名依据公开 Star，零 Star 不入榜；真实使用者的认可影响结果，不能刷榜。奖励是餐品兑换券、周边和 WorkBuddy 积分等，不是现金奖金；获奖不保证。详情以官方规则及券面为准。
