# 内部数据契约

这不是麦当劳官方请求schema。接入者需读取实时工具定义，取得真实返回后逐项规范化。严禁猜测字段、单位、餐品编码或虚构报价。第一版由支持MCP的AI客户端编排查询与规范化；没有通用的无人值守菜单解析器。

## menu

参考 `assets/synthetic-menu.json` 的结构。source仅允许`synthetic`或`mcp`；currency为CNY；service为pickup；store_id为本轮确认的店；fetched_at用带时区ISO8601。实时模式必须用实际查询完成时间，不能给旧数据续签新时间。

offers最多12项。每项含：id（本轮唯一）、name、kind（main/meal/side/drink）、available、components_known、components、selections、coupon_ids、reference_minor。

components列出已经确认的具体组成名称，包括套餐内饮料、固定配餐及已选替换项。字符串匹配仅支持规范化后的包含关系，不是完整语义识别或过敏原检测；调用者须把“汽水”等偏好解释为明确餐品限制，必要时询问用户。

selections每项为item_code、quantity（1至10整数）、options对象。保留精确规格和替换选项；单个原子项是面向一人的一份选择，套餐可以有多个组件。coupon_ids仅记录当前门店可用的优惠标识，不在公开文件存真实券码。reference_minor是可缺省的参考标价，只用来安排报价顺序。

当前 `official_price.py` 对未用券套餐提供保守预检：`options.roundList[].round` 只接受数字字符串（如 `"1"`），不可把轮次展示名（如“选择主食”）当作 ID。对 `9900015602`，详情 `data.rounds[]` 的整数 `id` 为 1/2/3，历史成功算价请求分别使用 `"1"/"2"/"3"`；将整数 ID 转成字符串是基于该记录的映射推断，并非当前工具 schema 明示的规则。每轮选中项只接受 `code`、`quantity`。本版不支持 `modification` 特制，不能自动加入详情中的默认特制值。对其他 ID 形态或确需特制的商品，应标记为待支持，先从当次 `query-meal-detail` 和工具 schema 核对，不能伪装为已核价。

对 `source=mcp` 的新鲜 plan，可用 `python scripts/official_price.py --plan private/plan.json --output private/requests.json` 预检最多8个候选。结果含 `ready`（候选ID及最小试算请求）和 `blocked`（候选ID及原因）；它只组装请求，不接入官方服务，也不能代替当次工具 schema。超过30分钟的菜单会被拒绝。

所有金额使用整数分。官方若以元为单位，先用Decimal准确转换；无法确定单位时不要填。未取到的营养或价格字段不能填0。

## plan

用`budget.py plan`生成，不手工编辑。例：

```bash
python scripts/budget.py plan --input private/menu.json --budget 25 --exclude 可乐 --include 薯条 --output private/plan.json
```

候选可以是一份主餐或套餐，搭配最多一份小食和一份饮料；也允许一份小食单点或搭配一份饮料（轻食组合）。饮料单点不生成候选。同券不得在一个候选内重复；组合券能否叠加最终由官方报价决定。每个候选含id与cart，plan有plan_id；ID绑定数据来源、门店、预算、偏好、时间及精确选项。每轮最多150候选；本轮仅尝试部分时必须披露覆盖数。reference_minor再高也不能代替真实核价。

## quotes

顶层为`{"quotes": [...]}`。每个候选只保留最新一次结果，重复记录会报错。字段：

| 字段 | 规则 |
|---|---|
| plan_id | 从当前plan复制 |
| candidate_id | 当前候选id |
| cart_fingerprint | `budget.digest(candidate['cart'])`，用于检测误配，不能证明来源真实性 |
| source | 与plan一致；只有真实调用才用mcp |
| tool | 实时必须calculate-price；模拟必须synthetic-price |
| currency / store_id / service | CNY / 当前门店 / pickup |
| quoted_at | 实际调用成功时刻，带时区；不能任意改新 |
| status | 明确核对成功才用ok；失败用error |
| payable_minor | 最终应付整数分；失败结果不需要金额 |

接入者必须确认官方报价覆盖精确餐品、数量、已选配置及所列优惠；不能只把任意金额配上指纹。此JSON不是有签名的官方票据，本地程序不能独立证明其真实来源。原始调用结果若需留证，仅私有保存并脱敏，禁止将账号/地址/凭证发布。

```bash
python scripts/budget.py rank --plan private/plan.json --quotes private/quotes.json
```

本地检查会拒绝来源混用、错误门店、旧plan、不同购物篮、非整数金额、未来时间、早于菜单的报价及超过5分钟的报价。菜单超过30分钟整轮失效。时效阈值是项目自定，不是麦当劳保价政策。

## 输出含义

found：至少一个有效且预算内的结果，但不表示其余候选已核价；insufficient_quotes：没有可推荐结果且仍有候选未获得有效报价；over_budget：本轮全部候选都有效核价且均超预算；no_candidates：偏好/组成规则下没有候选。`all_generated_candidates_priced` 仅表示本轮生成的候选全部有有效报价，不能扩展为全菜单覆盖。`found` 且 `unpriced_candidates>0` 时文本会明确提示其他候选可能更合适。

同一精确购物篮的不同优惠路径只占一个推荐位，保留最低有效报价。剩余预算仅为预算减应付金额，不把它叫“省了多少钱”；若要比较节省额，必须另外获取同一篮子的无优惠有效报价。
