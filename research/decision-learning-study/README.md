# 经验怎样长成判断习惯？

Agent Memory Study editors · 2026-09-21 · **已执行：原创结构化学习与纠正实验**。

一份反馈可以保存成案例、归纳成可读规则，也可以参与参数拟合。本实验比较这些具体实现，
再检查局部纠正改变了什么。它确实训练了小型分类器，**没有运行 Jev、jevlike、BGE、
自然语言 agent 或私人对话**。标签由公开规则生成，正确率表示标签预测，不是现实效用。

[进入跨源共读](https://indeliblevivi.github.io/agent-memory-study/study/experience-becomes-policy/) ·
[继续研究这个问题](https://indeliblevivi.github.io/agent-memory-study/question/experience-becomes-policy/) ·
[协议与探索修订](protocol.md) · [完整已执行结果](results.json)

## 怎么运行

Python 3.12/3.13，stdlib，无下载、API 或额外依赖：

```bash
python3 -B research/decision-learning-study/study.py --check
python3 -B -m unittest discover -s research/decision-learning-study -p 'test_*.py'
```

`--check` 重新拟合并核对参数、规则、预测、分组指标与控制；仅单次计时和 Python 版本不参与
确定性比较。更新实验时先修订协议，再用无参数命令保存新结果；原始输入在
[fixtures.json](fixtures.json)，[fixture_build.py](fixture_build.py) 可重建它，测试检查两者一致。
[study.py](study.py) 是唯一训练/评价实现；网页展示同一 receipt，不在浏览器训练。

## 这次实际测到了什么

4/2/4 个 train/validation/test 名称组使用同样的结构模板；每事件 12 个候选。
测试有 24 个事件、288 条候选，**288/288 测试向量都在训练支持内出现过**。
因此新名称组不是新语义或分布外泛化，不能把多个模板复制当成独立样本来扩大证据。

初次学习，在固定条件下：

| 具体实现 | 标签正确 | 说明 |
| --- | --- | --- |
| 恒定输出 irrelevant | 72/288 | 不使用新增反馈，亦不是无记忆 LLM |
| Hamming 最近案例 | 288/288 | 保存 288 条训练案例，按输入顺序打破距离平局 |
| 归纳 decision tree | 192/288 | 最大深度 4、8 个叶；这个容量限制是比较的一部分 |
| 小型 logistic scorer | 288/288 | 10 个显式观测、44 个参数、从零开始 400 次梯度更新 |

近邻与小头在这里相同，不能据此推荐训练。训练标签置换后，小头为 32/288；
仅候选字段、仅 context 敏感字段、仅六个关系特征的分类器分别为 144/288、96/288、240/288。
这些是给定表示下的信息删减对照，不能识别单个特征的独立因果贡献。
8 个测试事件的正确选入集合为空；整体分类分数与集合是否完全正确分别记录。

## 纠正之后，旧能力保住了吗

新的合成约束只改变“敏感任务、来源未核验、原本有用”的标签。12 条训练反馈被纠正；
在独立 test 中有 12 条该变、276 条应保留，其中 36 条为仍有效的边界候选。
全部处理使用相同分类器结构，按 v2 标签评价；完整重训从零开始，其余保留或更新原参数：

| 处理 | 应改变范围正确 | 应保留范围正确 | 其中：有效边界正确 |
| --- | --- | --- | --- |
| 仅改记录，参数不动 | 0/12 | 276/276 | 36/36 |
| 完整 v2 数据从零重训 | 12/12 | 264/276 | 24/36 |
| 从旧参数只学 12 条纠正，40 步，无 replay | 12/12 | 96/276 | 0/36 |
| 原参数加精确的运行时范围约束 | 12/12 | 276/276 | 36/36 |

这次少量更新只见到 harmful 标签，产生严重的范围外退化；完整重训也未完整保住边界。
固定超参数下的这个结果被保留，没有增加训练预算把它调成成功。它不证明所有增量学习
必然失败。运行时约束直接使用了已知的新规则，信息形式与梯度更新不同；成功只证明
这条精确约束在此任务上起作用，不是参数已纠正，更不是权重遗忘。

## 可检查的证据和限制

- `models` 保存原始、重训、增量模型的初始/最终参数，以及实际归纳的树。
- `cases` 保存每条 test 观测、v1/v2 标签和所属范围；`before` / `after` 的预测按同一顺序绑定。
- `after` 保留纠正训练行 ID、changed/preserved/boundary 的指标与转移矩阵。
- `cost` 保留模型规模与拟合预算；`execution` 是整个流程的一次本机计时，不是方法速度排名。
- 十项行为测试覆盖输入重建、分组、无标签/ID泄漏、反事实关系、作用域边界、真实 warm start、
  参数回放、计数以及全不选事件。统一 reader 验证也会重新拟合这个实验。

输入特征由明确字段比较得到，语义识别工作已经由 fixture 完成；组间支持重合也是主动
公开的限制。没有下游任务、用户评价、pretrained encoder 或 learned attention。
四条路径的容量和归纳方式不同，结果只比较这些机制包。
本实验没有测量样本影响是否彻底撤回，不把输出约束或训练版本替换称为 machine unlearning。

## 研究连接

[CoALA §4](https://arxiv.org/html/2309.02427v3)提供 memory/actions/decision-making 的架构语言。
[Jev 官方接口](https://docs.typesafe.ai/introduction)与
[jevlike README](https://github.com/vinnylarouge/jevlike)提供结构化判断与可训练部件的线索；
它们不是本实验的实现来源或效果背书。[Policy Distillation](https://arxiv.org/abs/1511.06295v2)
是策略压缩的历史阅读线索，本轮仅摘要范围。更多来源与各自限制见跨源共读。
