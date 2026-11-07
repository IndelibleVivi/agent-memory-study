# 题目本身带来多少信息？事后诊断

2026-11-07，主实验432个reader回答全部返回并完成raw replay之后，发现六组接近满分，
且 `poster-set:q3` 的一个干扰项直接写出后续批准日期。此时加入这项诊断；它不是原方案的
预设对照，也不是独立新任务样本。主实验所有请求、响应、gold及结果保持不变。

对原72题，分别用同样Luna/Sol reader、system prompt、JSON格式、reasoning=low、
1536输出上限与standard tier，唯一改变为memory空字符串。不给任何历史或writer输出。
每题每模型调用一次，共144次，无重试。题目文字、选项和选项顺序完全保留，不按主实验
错误筛选。仍使用原gold统计，包括强制选择在证据不足时碰巧答对的情况；不把正确率解释
为凭空恢复来源。按题型单列，尤其是题干已经指出缺什么的clarification controls。

目的：衡量整套材料中任务本身、选项线索与模型先验可以支持多少答案，检验主实验接近
满分是否足以声称记忆发挥了作用。原文与无记忆的差异是同题的描述性对照；此单次诊断不
建立充分统计功效，也不能将所有差异归于某一个内部推理机制。相关选项线索应成为后续
材料改进的依据，不能悄悄删除题目来提升这次效果。

`natural_probe.py` 复用同目录的payload、官方传输、预算门和artifact绑定，另建raw run，
明确引用主实验manifest与source identity。主实验已有的三阶段最大费用预留计入总USD10
上限，不重新支付writer；仍先官方token counting，再generation。公开汇总为
`natural-question-only-results.json`，原始请求／响应留repo外。统一验证只核保存汇总。
