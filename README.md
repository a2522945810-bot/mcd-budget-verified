# 麦当劳预算配餐助手

**给出预算和口味偏好，筛选到店自取餐品；实际推荐前核对门店、套餐选项和应付金额。** 非麦当劳官方产品。

> 例：预算 ¥25，想吃薯条、不喝可乐。参赛者在 WorkBuddy 查询淄博商厦餐厅（门店 `3350005`）时，一份鸡排堡＋中薯条＋阳光柠檬红茶套餐，2026-10-13 16:41:54 的未用券试算为 **¥22.90**，余 **¥2.10**。这是[历史调用回述](workbuddy.md)，不是现在的菜单或报价。

## 30秒体验

Python 3.10+，不需要账号或 Token：

```bash
python scripts/budget.py demo --budget 25 --exclude 可乐 --include 薯条
python scripts/replay_workbuddy.py
```

第一个命令使用**完全虚构**的餐品和价格，可看候选筛选与预算排序。第二个命令从公开的[脱敏历史记录](workbuddy.md)读取算价请求与响应，核对同一购物篮、套餐换项及 ¥22.90 的计算；它不联网，且明确提示该报价已过期。请勿拿任何一种演示结果当成当前售价。

| 输入与检查 | 项目如何处理 |
|---|---|
| 预算、要薯条、不喝可乐 | 排除组成不明或含可乐的项，保留套餐和小食加饮料等候选 |
| 门店及套餐换项 | 绑定精确商品编码、数量和三轮选配，防止拿别的购物篮价格冒用 |
| 官方实时试算结果 | 按整数分比较应付和预算；超时或返回商品不一致就拒绝推荐 |
| 候选没有全部核价 | 显示覆盖数，不声称找到全菜单最低价 |

项目的[参赛申请 #624](https://github.com/M-China/mcd-developer-innovation-challenge/issues/624)已获官方回复成功参赛。项目源码、使用范围和测试均公开；Star代表你觉得项目有用或想持续关注，不影响你使用代码。

**当前为0.2开发版：Skill、离线计算、连接诊断和未用券到店自取算价适配已实现。10月14日 WorkBuddy 报告确实运行了 `plan`、`rank` 和真实算价，但本轮 31 个候选仅 1 个获得有效报价；7 个套餐试算报 500。详见 [实测记录与证据边界](workbuddy.md)。完整套餐配餐仍待验收。**

## 使用者会得到什么

输入“25元、一个人、不要可乐、必须有薯条”，先确认门店，查询当前菜单和可用券，再核验有限数量的候选。输出最多三种不同购物篮及应付金额，说明搜索覆盖数、报价时间与剩余预算。

设计重点是价格和偏好可核对：组成不明的套餐先排除，过期或对应错误购物篮的报价拒绝使用，没有足够有效报价时不说“没有便宜套餐”。代码按整数分处理金额；优惠是否生效由官方查询结果判断，不由大模型猜测。

## 运行离线演示

Python 3.10或以上，无第三方包、无需账号。进入本目录后运行：

```bash
python scripts/budget.py demo
python scripts/budget.py demo --budget 25 --exclude 可乐 --include 薯条
python scripts/budget.py demo --budget 10
python scripts/replay_workbuddy.py
python -m unittest discover -s tests -v
```

`budget.py demo` 的商品、价格、编码和优惠都是虚构，不能作为真实接口接入证据。`replay_workbuddy.py` 读取历史 WorkBuddy 回述，可复查具体请求与返回结构，但不是现在的报价，也不能证明独立获取了官方服务端日志。

## 使用真实数据

按照 [连接指南](references/connect.md) 在支持MCP与本地Skill的客户端连接官方服务并加载本目录。宿主AI按SKILL.md调用真实工具、读取schema、规范化数据，再调用脚本检查。

第一版并非全自动独立点餐应用：自然语言理解、菜单字段映射和调用编排依赖宿主AI；预算、偏好匹配、候选枚举、报价绑定和排序为确定性Python代码。`official_price.py`已针对本次 WorkBuddy 转交的未用券算价结构实现精确购物篮校验，但其他场景与优惠用券尚待验证。

## 文件

| 路径 | 用途 |
|---|---|
| SKILL.md | 客户端运行步骤及触发说明 |
| scripts/budget.py | 候选生成、报价检查、演示 |
| scripts/official_price.py | 未用券到店自取算价结构校验和内部报价转换 |
| scripts/replay_workbuddy.py | 读取脱敏历史记录，复查一笔算价和预算余额 |
| scripts/connect_mcp.py | 初始化并发现官方工具定义 |
| tests/test_budget.py | 规则边界与模拟协议测试 |
| assets/synthetic-menu.json | 清楚标注的合成数据 |
| MCP_INTEGRATION.md | 工具、调用流程、实现状态 |
| workbuddy.md | 用户提供的真实 WorkBuddy 会话脱敏节选与证据范围 |
| mcp-config.example.json | 脱敏连接示例 |
| CONTEST_DECLARATION.md | 官方声明原文件，提交前参赛者须阅读 |
| references/data-contract.md | 内部数据契约，非官方API规范 |
| references/connect.md | 连接与真实验收步骤 |
| references/submission.md | 公开与报名步骤及缺失事项 |

原创代码与项目说明按 [MIT License](LICENSE) 开放；官方参赛声明及第三方材料不在该许可范围内，见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 范围与限制

本轮最多12个经核对组成的单品/套餐项；主餐或套餐可加最多一份小食和饮料，也可只选小食或小食加饮料。候选范围外的更便宜组合可能存在。报价调用数量有限，明确披露未核价数量，不宣称全局最低。

偏好匹配依赖输入中准确的餐品组成及文字标签；不支持过敏原安全判断。第一版不包含营养优化、外送、多人配餐、自动下单、领券或积分兑换。图片和店铺实拍不是本项目启动依赖。

source字段和购物篮摘要用于检测混用、误配和陈旧数据，不能证明输入文件来自官方。调用方必须保留真实性，不得把演示改标签冒充实测。价格以麦当劳官方实时结果为准。

## AI和第三方资源

本项目使用ChatGPT辅助设计、代码、说明和测试；参赛者使用 WorkBuddy 连接 MCP 并试算，脱敏回述记于 workbuddy.md。生成代码仍需参赛者和实际用户核验。第三方来源及官方声明校验信息见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 当前下一步

根据 10 月 14 日 WorkBuddy 的部分运行，取得套餐失败请求、响应和实际工具 schema 的脱敏记录，核对 `roundList` 参数结构后再试；提高有效核价覆盖。当前仓库提供历史调用节选和离线测试，不能将过期价格当作实时报价。不要将账号凭证、完整券码和个人信息提交至公共仓库。
