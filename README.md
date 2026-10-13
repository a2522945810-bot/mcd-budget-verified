# 麦当劳预算配餐助手

根据预算与口味偏好整理一人到店取餐候选，用麦当劳MCP价格查询结果核验，再推荐本轮预算内的组合。非麦当劳官方产品。

**当前为0.2开发版：Skill、离线计算、连接诊断和未用券到店自取算价适配已实现。参赛者提供了 WorkBuddy 真实账号会话的业务调用回述，见 [workbuddy.md](workbuddy.md)。本次代码发布不代表已完成端到端的现场演示。**

## 使用者会得到什么

输入“25元、一个人、不要可乐、必须有薯条”，先确认门店，查询当前菜单和可用券，再核验有限数量的候选。输出最多三种不同购物篮及应付金额，说明搜索覆盖数、报价时间与剩余预算。

设计重点是价格和偏好可核对：组成不明的套餐先排除，过期或对应错误购物篮的报价拒绝使用，没有足够有效报价时不说“没有便宜套餐”。代码按整数分处理金额；优惠是否生效由官方查询结果判断，不由大模型猜测。

## 运行离线演示

Python 3.10或以上，无第三方包、无需账号。进入本目录后运行：

```bash
python scripts/budget.py demo
python scripts/budget.py demo --budget 25 --exclude 可乐 --include 薯条
python scripts/budget.py demo --budget 10
python -m unittest discover -s tests -v
```

所有演示商品、价格、编码和优惠都是虚构。结果不是实际麦当劳价格，不能作为真实接口接入证据。

## 使用真实数据

按照 [连接指南](references/connect.md) 在支持MCP与本地Skill的客户端连接官方服务并加载本目录。宿主AI按SKILL.md调用真实工具、读取schema、规范化数据，再调用脚本检查。

第一版并非全自动独立点餐应用：自然语言理解、菜单字段映射和调用编排依赖宿主AI；预算、偏好匹配、候选枚举、报价绑定和排序为确定性Python代码。`official_price.py`已针对本次 WorkBuddy 转交的未用券算价结构实现精确购物篮校验，但其他场景与优惠用券尚待验证。

## 文件

| 路径 | 用途 |
|---|---|
| SKILL.md | 客户端运行步骤及触发说明 |
| scripts/budget.py | 候选生成、报价检查、演示 |
| scripts/official_price.py | 未用券到店自取算价结构校验和内部报价转换 |
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

本轮最多12个经核对组成的单品/套餐项；一份主餐或套餐，加最多一份配餐和饮料。候选范围外的更便宜组合可能存在。报价调用数量有限，明确披露未核价数量，不宣称全局最低。

偏好匹配依赖输入中准确的餐品组成及文字标签；不支持过敏原安全判断。第一版不包含营养优化、外送、多人配餐、自动下单、领券或积分兑换。图片和店铺实拍不是本项目启动依赖。

source字段和购物篮摘要用于检测混用、误配和陈旧数据，不能证明输入文件来自官方。调用方必须保留真实性，不得把演示改标签冒充实测。价格以麦当劳官方实时结果为准。

## AI和第三方资源

本项目使用ChatGPT辅助设计、代码、说明和测试；参赛者使用 WorkBuddy 连接 MCP 并试算，脱敏回述记于 workbuddy.md。生成代码仍需参赛者和实际用户核验。第三方来源及官方声明校验信息见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 当前下一步

在 WorkBuddy 中完成一次端到端的即时演示，记录精确购物篮和当时有效的报价；当前仓库提供历史调用节选和离线测试，不能将历史价格当作实时报价。不要将账号凭证、完整券码和个人信息提交至公共仓库。
