# InMind 的证据暴露与评分合取：固定源码核查

**Evidence status:** observed static source；论文中的实验数字为 source-claimed。本次没有运行系统、模型或 judge。编辑日：2026-11-05。研究者：Cove（AI-assisted research）。

## 固定对象

- 论文：[Keep It InMind v1](https://arxiv.org/html/2607.24368v1)，重点 §3.4、Table 1、Appendix 14.1–14.2、15–16。
- 源码：[imlrz/InMind at 5a2ab2686d3d5b832575f0288d41ecc93eab358b](https://github.com/imlrz/InMind/tree/5a2ab2686d3d5b832575f0288d41ecc93eab358b)。完整 clone 的 HEAD 已核对，worktree clean。逐文件哈希见[固定源码记录](inmind-source-lock.json)。
- 深读范围：evaluation README、两个 primary judge prompt、payload builder、timeline builder 和 submission validator。没有审计上游六个 memory system 的原始运行。

## 1. 正文里的两个最大值

Table 1 中，所有 retrieval 配置的 Application 最大值是 Naive RAG／text-embedding-3-large 的 16.0%；六个具名 memory systems 中最高是 MemoryOS／同一 embedding 的 14.4%。直接给予目标记录的 backbone 为 84.0%。这三个数字属于作者对 125 个任务的报告，不能把前两个说成版本矛盾，也不能把它们当作本次复现。

## 2. 合取关系与测量值是两回事

固定 [judge_application.txt](https://github.com/imlrz/InMind/blob/5a2ab2686d3d5b832575f0288d41ecc93eab358b/evaluation/prompts/judge_application.txt) 要求两个条件同时成立：给 answerer 的 context 中含该用户的目标信息，回答又给出相应提示。若 R 表示同一条记录上的真实 context recall，B 表示行为符合要求，则这个评分目标为 A=R∧B，必有 A≤R。

但独立执行的语言模型 judge 返回的是估计值 R-hat 和 A-hat；二者并不由同一确定性合取运算产生。Table 1 有 Application 高于 Target Recall 的行。作者在 Appendix 14.2 已经指出原因：回答可能仅凭世界知识给出一般提示，combined judge 因为看见符合预期的回答，漏查了个人信息实际不在 context 中的条件。其 100 个 configuration–task 记录的专家核查报告，Target Recall 一致率为 97%，Application 为 85%，后者的 15 个错误全为假阳性。

这不是本轮首次发现的论文缺陷。源码核查使这个已知限制有了可定位的输入合同：[build_judge_payloads.py](https://github.com/imlrz/InMind/blob/5a2ab2686d3d5b832575f0288d41ecc93eab358b/evaluation/scripts/build_judge_payloads.py) 的 target-recall payload 不带 answer；application payload 则增加了 answer。两者的用户事实、context、query、explanation 来自相同 task/result 字段。

**本轮推论：**使用这些观测量分解 retrieval 与 use 时，应保存 per-record 联合标签、冲突记录和盲审复核，不能只用两个平均值相减。若先盲判 R，再用确定性合取构造 R∧B，可以保证评分目标的逻辑一致；它仍不能证明回答因记忆而改变，因果归因要另作固定输入或历史干预。存在目标信息并且回答正确，也允许模型完全依赖其他信息。这与 Relata 已有 claim-boundary 判断相连，不构成新接受的因果评分合同。

## 3. 提问顺序的边界已经写明

[evaluation/README.md](https://github.com/imlrz/InMind/blob/5a2ab2686d3d5b832575f0288d41ecc93eab358b/evaluation/README.md) 明确要求每个任务独立 state；完成历史后 freeze/snapshot，direct 与 indirect query 从同一 frozen state 分别执行。direct 查询的检索、回答不得改变 indirect 查询使用的 state。因此，仅凭论文叙述“先 direct，后 indirect”，不能指称其发生了 probe 写回污染。

[build_timeline.py](https://github.com/imlrz/InMind/blob/5a2ab2686d3d5b832575f0288d41ecc93eab358b/evaluation/scripts/build_timeline.py) 将两条 test query 放在历史 sessions 之外，输出同一 frozen-state 的文字政策；它没有运行 memory adapter 或建立 snapshot。文档要求与原始报告是否遵守该要求是不同证据。本次没有后者的逐调用回执。

注入位置也需要精确：locator 是背景第 40 个 user turn 所在 session，实际把目标 pair 加在完整第九个 session 的末尾，所以目标前有 41 个背景 user turns；不是截断到第 40 个。后面仍有 38 个完整 sessions。单次 Naive RAG 使用额外 task-local chunk，不能与有状态中间注入误作同一种 lifecycle。

## 4. 对 AMS 后续研究的影响

一个已知有限世界里的充分证据集合，可以给“证据支持的完成”建立上限。把这个定理用于某真实 benchmark 时，必须说明支持集合、读者背景与测量过程。InMind 的 Target Recall 是有误差的特定目标信息检测，不是自然语言任务所有充分支持路径的全知 oracle。理论上限与 noisy score 不一致时，要先检查命题所针对的对象有没有改变。

InMind 的控制对“隐含关联容易在暴露前失去”给出有价值的实证压力。其结果不构成任意 query-conditioned 机制都无法发现关联的普遍不可能性证明；论文也将可全库运行模型的平凡解与受限高效检索分开。普通事实、有效隐含关联、过度提醒的负例，以及换域的路径，都值得在具体预算下继续测量。

## 5. 精确后续委托，尚未执行

在获得作者原始逐条 context、answer 和 verdict 后，先固定 judge 版本与原始包哈希，建立 R-hat/A-hat 的四格表；盲审全部 A-hat=1 且 R-hat=0 的记录，并从其余三格按预先规定方式抽样。审查员先只看 context 判断 recall，再看回答判断行为，最后核对角色、来源、同义改写和警告是否属于该用户。不要用已经看过答案的第一遍判定充当盲审。

输出每一格的原始数、分层样本量、具体冲突原因和不可判定记录。若原始逐条材料不可用，明确停止于静态合同研究；不从论文百分数重造任务级标签。对原始 prompt 作复核不自动成为对新的 scorer 的接受。这个委托不授权 provider 调用或公共发布原始记录。
