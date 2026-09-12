# Reward 能看见哪一次记忆操作？执行前协议

Agent Memory Study editors · 2026-09-12

来源为 [AgeMem ACL 2026 论文](https://aclanthology.org/2026.acl-long.981/) §§3.3–3.5、Appendix A.2–A.3、C.4，以及 [官方源码固定 revision](https://github.com/y1y5/AgeMem/tree/98f563f907d67b2f2436e3ae7b7ceff32e482814)。协议与 fixtures 在首次执行本 runner 前写定；这是读过源码后的定向检查，不是盲测或第三方 preregistration。

## 问题与实际执行范围

直接加载未修改的 `trinity/common/workflows/memory_reward/my_reward.py`，运行三个 stats extractors 和 `ThreeStageRewardCalculator.calculate_total_reward`。模块只依赖 Python 标准库，不初始化 Trinity、torch、模型、embedding 或网络客户端。外部 checkout 固定 commit，并检查执行模块与用于解释调用关系的 train / advantage 文件没有 tracked diff；上游代码不复制进本站。

固定 task score 0.5、found_answer=true、Stage 3 rounds=4/10、token budget=8192。使用训练调用点的四项权重 task/tool/context/memory=0.5/0.2/0.15/0.15，而不是把它误写成论文 Appendix C.4 的三项各 1/3。不修改官方算法以贴合论文。

`fixtures.json` 有 16 例：

| 组 | 输入干预 | 需要区分的对象 |
| --- | --- | --- |
| maintenance，6 例 | Update / Delete 各 True、False；取消删除；无维护 | 字符串出现、执行成功、维护奖励 |
| history，2 例 | 相同后续问答，是否保留 Stage 1 的 add 消息 | 当前 context 可见性与历史动作；本组不模拟训练或真实 store |
| retrieval，2 例 | 同一 retrieved block 后，assistant 使用或明确忽略内容 | 消息邻接与语义利用 |
| preservation，3 例 | 原问题、无关替代问题、完全没有 user 消息 | 留下某个 user message 与保留原任务 |
| mention，1 例 | 只在普通 prose 中提及 Summary_context | 工具名出现与真正调用 |
| judge，2 例 | 相同失败 update 与 retrieval，注入固定 judge 返回 0 / 1 | LLM override 能改的 relevance 与不受它影响的 maintenance |

所有消息均为本站原创 train/platform 小例子。工具返回的格式依据 `train_hotpotQA.py` 的 `_apply_tools`：`memory_updated:{ok}` / `memory_deleted:{ok}` / `memory_deletion_cancelled:confirmation_required`。成功与失败消息是手动输入 reward 函数的控制，不是本次真的执行了 store mutation。`memory_manager=None`，不装配 memory backend。

前 14 例 `chat_client=None`，只刻画模块明确支持的 fallback。最后 2 例用记录请求的本地 stub 返回固定字符串；不把这些字符串称为真实 LLM verdict。覆盖两条路径，避免把无 judge 的 fallback 推广到正常联网训练。

## 可否证预期与计数边界

- 每例 expected 子集在执行前记录；任何不同输出必须使 runner 失败，而不能删掉该例。
- 成功/失败的 Update 与 Delete 应得到相同 maintenance 指示量；取消与无操作为 0。比较这一分项，不要求字符串长度不同的总 reward 完全相等。
- reset 配对若失去 add 统计，只说明从最终 context 重新提取的观测会变化；不得说 persistent store 被清空。
- fallback 的 `used_retrieved_memory` 若只受相邻 assistant 影响，不得把它称为语义正确利用。有 judge 时 relevance 可以不同，仍需单列 maintenance。
- preservation 预期只反映当前 context 的自我检查，不证明最初的用户问题或 supporting facts 留下。
- 用未加权分项和调用点权重独立重算返回的 total，检查 raw breakdown 与汇总一致。维护项的贡献为 `0.15 × 1/3 = 0.05`，不是每次调用都加 0.05。

输出公开全部输入、返回的 stats、完整 reward breakdown、stub 请求与汇总。`--check` 必须重新执行官方模块并逐字段比较；`--verify-checked` 只审查现有 receipt 的绑定与算术，不冒充官方模块重跑。

## 不支持的结论

不执行整个训练 workflow、step-wise GRPO optimizer、memory backend、真实 LLM judge 或五项 benchmark；不估计失败率、reward hacking 的实际发生率或模型性能。源码 revision 与 ACL PDF 是分别固定的两个来源，不能证明它就是论文实验时的版本。不会向上游发 issue / PR 或修改上游以制造通过。
