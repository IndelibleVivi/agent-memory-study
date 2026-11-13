# v1 组合迁移诊断：一次有限的合成跟随研究

Agent Memory Study editors · 2026-11-13 · Cove（AI-assisted research）

这是[原学习实验](README.md)与[1024 向量支持审计](support-audit.md)之后的预指定跟随诊断。
支持审计已经枚举并观察到全部 1,024 个布尔结果，因此这里不是独立盲测、held-out confirmation
或预注册研究。测试域的类别比例也不代表现实发生率。

## 问题与可识别边界

原 v1 规则的 positive core 只有一个：family、goal、parameter 匹配，前置条件齐备，
工具可用，目标 fact 未知道，且候选未过期、无副作用。`verified` 与 `sensitive` 在 v1
标签中都是 nuisance。本诊断只测试这同一个 core 在 `sensitive=1` 的完整向量上能否迁移；
它不能测试新的 useful 语义 core。

训练严格使用原 `train` 中 `sensitive=0` 的 144 行。训练得到 18 个唯一向量；测试使用
全部 512 个 `sensitive=1` 向量，每个合法十位向量只出现一次。训练／测试向量交集为
0。两个 useful 测试向量及其一距离的缺前置条件、过期、副作用邻居均已检查。
validation 只作描述性回放：72 个 `sensitive=0` 行，其余敏感 validation 行未参与训练、
选材或调参。filtered scorer 在这 72 行上为 72/72；这没有参与任何选择，也不能抵消测试域的
选择错误。

## 三个监督臂

- `filtered-original`：144 行过滤后的原始训练；唯一向量 18。
- `balanced-repeats`：原始训练加 32 行，四类各 8 行；只是原标签的等量监督控制，
  不是额外独立数据。增加部分含 18 个唯一向量。
- `balanced-counterexamples`：原始训练加 32 个 `sensitive=0` 的公开 oracle 标签行，
  四类各 8 行。每类按 `(是否已在过滤训练支持, 字典序向量)` 排序，取前八，不足则
  按该顺序循环。没有测试反馈或预测误差参与选材。增加部分含 20 个唯一向量；两臂
  增加行数与类别直方图相同，最终训练行数均为 176。

原 scorer 每次从零拟合一次，沿用 400 steps、rate 0.5、L2 0.01 与全部十项特征；
原 decision tree 按既定的 depth=4 归纳；nearest case 仍采用原 Hamming 距离与训练顺序
tie-break。每臂各拟合一次，没有用 test 调阈值、特征或超参数；validation 不参与选择。

## 已执行结果

下表按类标签正确数、二元选择、错注入和冻结的单位成本报告。useful recall 的分母是
2，harmful 误注入分母是 60，其他（redundant + irrelevant）误注入分母是 450。
utility 为：选对 useful `+1`，任何误注入 `-1`，漏选或拒绝 `0`；这不是现实收益。

| 方法 | class | 选中 | useful recall | harmful 误注入 | other 误注入 | utility |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| oracle v1 | 512/512 | 2 | 2/2 | 0/60 | 0/450 | +2 |
| constant reject | 448/512 | 0 | 0/2 | 0/60 | 0/450 | 0 |
| filtered scorer | 171/512 | 21 | 2/2 | 4/60 | 15/450 | -17 |
| filtered tree | 224/512 | 128 | 1/2 | 15/60 | 112/450 | -126 |
| filtered nearest | 258/512 | 129 | 2/2 | 15/60 | 112/450 | -125 |
| repeats scorer | 172/512 | 23 | 2/2 | 4/60 | 17/450 | -19 |
| repeats tree | 224/512 | 128 | 1/2 | 15/60 | 112/450 | -126 |
| repeats nearest | 258/512 | 129 | 2/2 | 15/60 | 112/450 | -125 |
| counterexample scorer | 312/512 | 21 | 2/2 | 4/60 | 15/450 | -17 |
| counterexample tree | 372/512 | 64 | 2/2 | 14/60 | 48/450 | -60 |
| counterexample nearest | 347/512 | 34 | 2/2 | 5/60 | 27/450 | -30 |

这组结果没有把任一学习器变成成功方法。等量重复对 scorer 几乎只改变少量行；
反例监督提高完整类别正确数，并把树与最近案例的 harmful 误注入从 15/60 降到
14/60 与 5/60，把其他类别误注入从 112/450 降到 48/450 与 27/450。tree 仍保留
14/60 harmful 误注入；scorer 的二元选择没有改善（21 次，utility -17）。nearest
的 347 是固定训练顺序下的观测，不是最佳顺序。

## 顺序、invariance 与 v2 边界

filtered-original nearest 的最小距离 tie 集给出逐案例的可达标签集合。逐案例独立选择的最小／最大
标签正确总数是 48/512 至 512/512，二元选择为 385/512 至 512/512，utility 为 -125
至 +2。它们是逐案例 envelope，并不保证由同一个全局训练排序共同实现。另报告两个
有限顺序：scope-first（`irrelevant, harmful, redundant, useful`）得 512/512，hazard-first
（`harmful, irrelevant, redundant, useful`）得 92/512；这两个类优先顺序对应的得数与
同名 per-case priority controls 相同，它们仍是命名的有限顺序结果，不是全局极值，
也没有搜索所有排列。

256 对仅在 `verified` 上翻转的测试向量用于检查不变性。oracle v1 为 0 个类别、0 个
选择变化。counterexample tree 也是 0/0；其 scorer 有 44 个类别变化、19 个选择变化，
nearest 有 111 个类别变化、32 个选择变化。因测试全部 `sensitive=1`，不能在测试内构造
sensitive 翻转对；这只是“测试域不可识别”，不能升级为 v2 的 invariance。

v2 的冻结策略错配重新评分，不训练修正模型：changed 为 1 行，preserved 为 511 行，
boundary 为 preserved 中的 1 行。各方法的 changed / preserved / boundary 类别正确数
分别保存于逐方法 receipt；例如 counterexample tree 为 0/1、371/511、1/1。只有 filtered
与 repeats 的树正确预测了 changed 行；三种训练方案都没有证据表明学会了 v2 修正。
v2 的 `sensitive` 和 `verified` 真正参与规则，但这里没有 sensitive training 或
correction feedback，故该结果显示旧策略与 v2 的错配，而不是学会新规则。要识别 v2
的修正规则，需要另设包含 correction supervision 的独立切分，不能把本诊断改写成 v2
迁移成功。

## 容量与可复现性

useful 需要八个相关固定位同时为真（前三关系位、前置条件、工具、未已知、未过期、
无副作用）。固定 depth=4 的树不能在整个十维域表达这个精确八条件的合取；即使只在
本测试的 `sensitive=1` 半域，树深度也不足以保证覆盖一个 8 位合取及其相邻负例。这是原
实验的容量受限比较，本跟随研究保留该 comparator，不为补反例而改变容量。反例监督可以
帮助选择接近的规则区域，却不把 depth=4 变成全合取表达器。

最初审查的候选选材曾错误地给 harmful 增加 hazard-sum 排序，并改动了预拟合协议文本。
这些改动被拒绝；协议恢复到首次拟合前的原文，实现也恢复为每类统一的
`(support, vector)` 字典序选材，随后才重新生成最终 receipt。上表是这次最终实现的结果，
没有根据输出回头修改协议。支持审计、旧结果与历史 receipt 没有改写。

实现入口是 [transfer.py](transfer.py)，冻结规范是 [transfer-protocol.md](transfer-protocol.md)，
完整逐向量、训练身份、权重/树、顺序与 v2 分组结果在
[transfer-results.json](transfer-results.json)。行为检查在 [test_transfer.py](test_transfer.py)，
入口以 `--check` 重新计算完整 deterministic receipt，并核对源文件、协议、切分、选材、拟合与
指标。所有数据都是原创公开合成数据；没有 LLM/API 调用、现实中的人类判断或部署效用。
