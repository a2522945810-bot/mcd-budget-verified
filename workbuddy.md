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
