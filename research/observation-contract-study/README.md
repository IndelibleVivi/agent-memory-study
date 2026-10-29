# 观察相同以后，还能怎样把机制分开？

Agent Memory Study editors · 2026-10-29 · **已执行的有限确定性研究**。

本目录拥有 P8 的独立科学方法、原创构造、runner、结果与测试；[研究正文](../../study/entries/distinguishability-and-observation.md)解释推导和观察。它继续[任务相对充分性研究](../task-relative-sufficiency/README.md)，新增允许行动后的可观察区分，不改写先前 32-world 研究。没有模型、参与者、真实来源、付费服务或网络请求；**经验样本数为 0**。

## 运行与保存

Python 3.11+，仅标准库，repo root 下执行：

```bash
python3 -B research/observation-contract-study/study.py
python3 -B research/observation-contract-study/study.py --check
python3 -B -m unittest discover -s research/observation-contract-study -p 'test_*.py'
python3 -B research/observation-contract-study/study.py --search writeback-active live cached --max-steps 1
python3 -B research/observation-contract-study/study.py --search score-weighted revision scope --max-cost 1
python3 -B research/observation-contract-study/study.py --packet --output /fresh/path/observation-packet.json
```

默认只向 stdout 输出完整 JSON。`--output` 使用排他创建，拒绝覆盖；`--check` 重算与本目录 `results.json` 完整比较。源码、协议或输入变化时，先输出到新路径，审查后有意识地更新保存结果；不能以 `--check` 修复 drift。packet 是含全部 fixtures/results 的 JSON 数据，没有执行代码或工具授权；`--packet` 不与单 pair 的 `--search` 混用。未提供 arbitrary file loader，仪器只执行目录内具名模型。

## 文件与单一职责

| 文件 | 所有权 |
| --- | --- |
| protocol.md | 定义、竞争预测、搜索范围与推导依据，首次运行前写定 |
| fixtures.json | 13 个模型：三个非同构主家族和一个全交控制家族 |
| study.py | 唯一计算实现；分区/全类答案兼容/碰撞/最短区分行动 |
| results.json | 完整确定性结果，绑定 source/protocol/fixture 字节身份 |
| test_study.py | 21 项行为检查，含 256 个二状态系统的独立穷举对照 |
| adapter.py | 无 I/O mutation 的具名模型边界，不拥有平台 job/registry/UI |

## 实际结果

13 个模型共 70 个初始 state pairs，每个 pair 保存无界搜索、一步界搜索和独立长度 5 全动作词枚举核对。世界和状态是构造对象，不是独立经验样本。

| 模型 / pair | 初始观察与目标 | 实际无界结果 |
| --- | --- | --- |
| future-access / w00,w01 | x 相同、未来 y 不同 | revisit，一步，成本 1 |
| future-denied-* / w00,w01 | 相同碰撞，五项门槛逐项关闭 | 允许模型内不可分；源未到场 |
| future-side-information / w00,w01 | 已声明侧信息提供 y | 初始已分开，空词成本 0 |
| writeback-active / live,cached | 答案同为 Friday，支持机制不同 | withdraw→read，两步，成本 2 |
| writeback-forbidden / live,cached | withdraw 不获准 | 允许模型内不可分 |
| equivalent-control / a,b | handle/目标标签不同，可见行为完全相同 | 穷尽 product graph 后仍不可分 |
| score-weighted / revision,scope | 总分同为 1，错误类型不同 | prepare→inspect，成本 1；直接 probe 成本 3 |
| score-unit-cost / revision,scope | 同一 plant，仅动作成本统一为 1 | 直接 probe，一步，成本 1 |
| nonpairwise-control / a,b,c | 每对答案集合有交，整体无交 | 最小空交见证必须含全部三状态；没有行动可分 |

writeback-active 的一步界只得到 `not-distinguished-within-bound`，不能把它写成等价。score-weighted 的一步界会找到昂贵 probe，明确是界内最优，不能冒充全局最低成本。五个 gate 模型中的 gate 值对全部状态相同，拒绝动作不会编码隐藏答案。源版本与目标标签出现在获准返回的合成片段中；这里没有外部身份验证。

## 稳定 instrument 接口 v1

`fixtures.models[i]` 严格分为：

- `plant.states`：每个 handle 的 `observation / side_information / transitions`；transition 只有 `next / output`。
- `plant.actions`：`cost / gates / meaning`；gates 为公开、state-independent 的 permission/availability/version/target/coverage 条件。全开才允许，transition 对所有动作全定义。
- `evaluator.targets / answers / question_descriptions`：仅分析器使用。`search_pair(plant,left,right,...)` 不接这个分支。

纯 Python 入口：`validate_model(model)`、`partition(plant)`、`compatibility(members,answers)`、`search_pair(plant,left,right,max_steps=None,max_cost=None)`、`trace_word(plant,left,right,word)`、`analyze(model)`、`run()`。`naive_pair` 仅用于小域独立验算，不是第二个生产搜索入口。

成本只接受整数或精确有理数字符串（如 `"1/2"`），拒绝浮点、负值和 bool。搜索优先总成本，其次步数，再动作词字典序；零成本环不造成无限搜索。总预算与步数界可同时使用；有步数界时 product key 包含步数，避免丢弃贵而短的可行前缀。无界穷尽结论只覆盖有限 graph，见协议中的论证。

adapter 的 `describe_capabilities()`、`validate_plan(plan)`、`execute(plan)` 供平台接入。计划样例：

```json
{"operation":"search-pair","model":"score-weighted","left":"revision","right":"scope","max_steps":1,"max_cost":3}
```

另一操作为 `{"operation":"analyze-model","model":"future-access"}`。adapter 拒绝未知字段、未知模型、gold 参数和无效界，返回 `ams-observation-contract-instrument/1` 加原计划、当前 source/protocol/fixture bindings 和结果。没有伪造 Run/Job，统一平台应在外层记录实际执行身份。

完整结果 schema 为 `ams-observation-contract-results/1`：`bindings` 固定三个科学真源文件；`models` 含 `classes[].observation/members/questions/target_collisions` 和 `pairs[].unbounded/step_bound_1/independent_check`。搜索输出固定 `pair / bounds / allowed_actions / inaccessible_actions / optimization / scope / status / word / cost / steps / trace / expanded / pruned_by_bound`；未发现时附 certificate。`trace[0]` 是两侧初始可见信息，后续行是动作与实际两侧输出；expanded 是算法搜索证据，不是消费者可见信息。handle 只供审计，UI 不得把它变成隐藏答案通道。

portable schema 为 `ams-observation-contract-packet/1`，包含 `fixtures` 与完整 `results`。UI 可以直接浏览保存结果，或通过本地 adapter 重新计算具名模型；二者须标清。正文/方法链接是 repo-relative，不含任何私人执行路径。

## 验证和边界

21 项测试包括：全交最小性、五项访问 gate、side-information refinement、延迟序列、真实等价、变成本/零成本、负成本/随机转移拒绝、预算、成本较高但步数较短的前缀、目标隔离、handle/顺序不变、删动作与改观察的 mutation、问题扩大、动作扩展单调性、adapter 边界，以及全部 256 种二状态二动作确定性转移/输出配置与朴素枚举比较。`run()` 另对全部 70 pair 用长度 5 独立枚举核对界内最优。

这验证实现合同，不是对开放世界或 LLM 的等价性证明。三类主构造检验协议所列竞争预测，支持“聚合输出并不总能辨别目标、某些允许行动可以补充区别”，也保留不能区分的完整病例。没有引用未实际阅读的外部论文，没有理论首创或经验效用主张。

**当前交付边界**：独立科学 source、保存结果、CLI、portable output 与文章齐备；公共目录注册、统一 verifier、Lab UI、Observation→案头→DesignRevision 接续由 programme 集成层完成。本目录不把 adapter 或 JSON 下载称为整个 P8 产品已完成。
