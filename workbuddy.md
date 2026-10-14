# WorkBuddy 实测记录节选

2026-10-13，参赛者在 Windows WorkBuddy 5.7.7 配置麦当劳 MCP 服务后，要求查询附近到店取餐门店，再指定门店 `3350005`，以“预算25元、想吃薯条、不喝可乐”为条件查询菜单、套餐详情和应付价格。WorkBuddy 回复报告已调用 `query-nearby-stores`、`query-meals`、`query-store-coupons`、`query-meal-detail` 和 `calculate-price`。没有下单、领券或兑换积分。

参赛者随后要求 WorkBuddy 从本轮会话的工具调用记录中列出 C 组合的原始入参与返回。下列内容是 **WorkBuddy 回述的JSON脱敏节选**；项目作者未在本地抓取HTTP报文或独立验证服务端日志。完整截图和账号信息不发布。

请求（保留篮子与选配字段）：

```json
{
  "storeCode": "3350005", "orderType": 1, "beType": 1,
  "items": [{
    "productCode": "9900015602", "quantity": 1,
    "roundList": [
      {"round": "1", "comboItemList": [{"code": "521147", "quantity": 1}]},
      {"round": "2", "comboItemList": [{"code": "4810", "quantity": 1}]},
      {"round": "3", "comboItemList": [{"code": "515281", "quantity": 1}]}
    ]
  }]
}
```

返回（仅保留算价判断所需字段；去掉链路ID及其他元数据）：

```json
{
  "success": true, "code": 200, "datetime": "2026-10-13 16:41:54",
  "data": {
    "originalPrice": 2290, "discount": 0, "price": 2290,
    "productList": [{
      "productCode": "9900015602", "productName": "大堡口福三件套",
      "quantity": 1, "subtotal": 2290
    }]
  }
}
```

三轮选择对应鸡排堡、中薯条、阳光柠檬红茶中杯；试算应付22.90元，没有用券。这个报价只代表该次请求，已超过项目的5分钟有效窗口。展示当前价时必须重新调用接口。

可运行 `python scripts/replay_workbuddy.py` 复核公开的两段JSON是否与精确套餐选配及22.90元预算计算一致。复核脚本使用记录中的算价时刻作为本地重建菜单时刻，因为本节没有精确的菜单抓取时间；此时间不代表原始菜单调用日志，运行脚本也不会向麦当劳服务联网。

## 2026-10-14：新版 Skill 的部分现场运行

参赛者在 WorkBuddy 中加载更新后的 Skill，指定门店 `3350005`、预算 25 元、必须有薯条且不要可乐。以下是参赛者转交的 **WorkBuddy 文字总结**，本仓库没有收到该次调用的原始完整请求、返回、脚本执行日志或服务端日志，因此只记录可归于该总结的结论：

| 项目 | WorkBuddy 报告 |
|---|---|
| 本地流程 | `budget.py plan` 和 `budget.py rank` 均运行成功；生成 31 个候选 |
| 业务调用 | `now-time-info`、`query-meals`、`query-meal-detail`（10 次）、`query-store-coupons`、`calculate-price`（10 次） |
| 试算覆盖 | 8 个候选各试算 1 次，另有 2 次对照；仅 1 个候选进入有效报价，30 个候选未获得有效报价 |
| 有效结果 | 薯条单点，WorkBuddy 报告应付 ¥14.50，预算余额 ¥10.50；报价时间为 2026-10-14 11:05:32（北京时间） |
| 套餐失败 | 7 个带 `roundList` 的套餐请求据报告返回 `code=500`；WorkBuddy 未将其当作有效核价 |
| 操作边界 | 未下单、领券或兑换积分 |

这笔 ¥14.50 价格已超过本项目 5 分钟有效窗口，不能作为当前报价；`found` 仅表示本轮至少找到一个已核价的预算内候选，**不代表 25 元内只有薯条**。去掉 `roundList` 的对照请求改变了购物篮表达，返回 200 并不能单独证明 `roundList` 本身是故障根因，也不能核实原套餐的完整选配。需要取得脱敏的失败请求、响应和调用时实际工具 schema 后，才可进一步区分参数问题与服务端故障。

### 随后的失败记录回述（2026-10-14）

参赛者又转交一条 `9900015602` 套餐 500 请求的 WorkBuddy 说明。WorkBuddy 明确表示 **不能逐字回读原始调用日志**：请求由本地 `private/menu.json` 和 `plan.json` 重建，而非原始请求字节；其报告的响应为 `success=false`、`code=500`、时间 11:05:32、无业务 `data`。重建请求里的 `round` 分别为“选择主食”“选择小食”“选择套餐内饮料”，还在主食和饮料子项加入了 `modification`，并增加可选的 `needTableware=false`。相较 10 月 13 日成功请求的 `"1"/"2"/"3"` 轮次、无特制、无餐具字段，**同时改动了至少三处**，不能归因于某一字段。

WorkBuddy 转交的当次输入 schema 只说明 `round` 是字符串，没有提供“展示名称可用作轮次编码”的依据。本项目现在对观察过的数字轮次形态进行本地预检，未核实的展示名称与特制项会在调用前被拒绝；该预检是项目的保守限制，不代表官方 MCP 对其他合法输入的完整定义。下一步应从本轮详情中核实真实轮次编码，对同一门店的单个套餐进行受控试算，避免在结构未明时批量请求。
