# 麦当劳MCP集成说明

## 实现状态

2026-10-13：参赛者在 WorkBuddy 5.7.7（Windows）连接自己的麦当劳 MCP，并提供本轮门店、菜单、套餐详情及算价的会话记录。下表是 **WorkBuddy 报告的实际业务调用**；本仓库不持有 Token，也没有从本地 Python 直接调用这些业务工具。脱敏节选见 [workbuddy.md](workbuddy.md)。

2026-10-14：参赛者再次使用更新后的 Skill；WorkBuddy 报告本地 `plan`/`rank` 均执行，8 个试算候选中仅薯条单点通过价格核验，7 个套餐请求返回 500。该次未取得原始完整工具请求和返回，不能据此诊断 `roundList` 的根因，也不能把单点价格外推至套餐。报告见 [workbuddy.md](workbuddy.md)。

同日追加说明：失败的 `9900015602` 请求由 WorkBuddy 从私有文件重建，轮次为展示名称，还增加特制项和可选餐具字段；与前一天成功的数字轮次且无特制请求存在多处差异。本版 `official_price.expected_items` 已加本地预检并仅支持已观察的数字轮次及无特制项，不能据此宣称官方接口只接受这种格式。

官方Server：`https://mcp.mcd.cn`，Streamable HTTP，Authorization Bearer鉴权。来源：https://github.com/M-China/mcd-mcp-server

| 工具 | 作用 | 当前证据范围 |
|---|---|---|
| query-nearby-stores | 提供门店候选 | WorkBuddy 回复报告成功，门店3350005 |
| query-meals | 查询该门店可售餐品 | WorkBuddy 回复报告成功，15个分类 |
| query-meal-detail | 核对套餐组成和换项 | WorkBuddy 回复报告6次成功 |
| query-store-coupons | 查询当前门店可用券 | WorkBuddy 回复报告2张，未领用 |
| calculate-price | 核验具体购物篮的应付 | WorkBuddy 回复报告4次成功；其中C组合的入参与响应由参赛者转交，见下文 |

list-nutrition-foods列在诊断白名单供后续研究，但本版不实现营养优化。所有参数应以真实tools/list定义为准；公开README只列工具名称及用途，不能替代输入schema。

## 流程与业务价值

用户给出预算与偏好 → 确认门店 → 查询菜单、详情和优惠 → 宿主按内部契约规范化 → 脚本枚举候选 → 宿主按当前schema逐项核价 → 脚本拒绝错配/过期/超预算结果 → 输出有限范围的推荐与搜索覆盖数。

内部金额一律为整数分，不自己模拟真实优惠算法。希望减少用户反复试购物篮的操作；尚无节省时间、节省金额或公开用户使用效果的测量证据。

## 哪些代码实际做了什么

- budget.py可独立运行合成演示并检查规范化报价；它不直接访问麦当劳服务。
- official_price.py核对一份未用券、到店自取的算价请求与精确购物篮，读取分单位价格并生成内部报价；它处理的是宿主提供的JSON，不向服务器发请求，也不能证明转交文本的真实性。
- replay_workbuddy.py从公开的脱敏历史回述重建一个本地候选并执行购物篮核对，便于复查预算余额；重建的菜单时间仅供复核，不是原始菜单查询的日志。
- connect_mcp.py实现initialize、notifications/initialized、tools/list及会话关闭；它只发现工具定义，不查询用户菜单、优惠和订单。
- 实际业务调用由支持MCP的宿主AI按SKILL.md编排。本轮 WorkBuddy 会话提供了真实账号环境下的调用报告；宿主回述的原始JSON尚未与独立服务端日志核对，见证据边界。

## 数据处理

Token仅在用户本机客户端或诊断进程中使用。示例配置是变量占位符，客户端变量展开能力需实测。原始账号结果不进入公开仓库。对外展示应去除手机号、地址、完整券码、会话ID等。

## 一次算价记录与证据边界

参赛者转交 WorkBuddy 2026-10-13 16:41:54（北京时间）的 `calculate-price` 入参和返回，门店 `3350005`、`orderType=1`、`beType=1`，商品 `9900015602` 一份；三轮选择 `521147` 鸡排堡、`4810` 中薯条、`515281` 阳光柠檬红茶中杯。无用券字段。返回 `success=true`、`code=200`、`data.price=2290` 分、`data.originalPrice=2290` 分、`data.discount=0`，商品列表同为 `9900015602` 一份。详见 [workbuddy.md](workbuddy.md)。

这些JSON是 **WorkBuddy 在同一会话中回述的工具记录**，并非本仓库独立抓取的HTTP日志。不能由此推断其他门店、其他时段的价格或券后价。Skill约定报价5分钟后失效；该记录仅作为历史测试和适配样本。对外现场演示需重新查询菜单、选项与应付金额。
