# 双语记忆使用策略，能怎样从反馈中学习？

Agent Memory Study editors · 2026-09-25 · **研究设计：proposed-not-run**。

[研究协议](protocol.md) · [表示与消费的共读](https://indeliblevivi.github.io/agent-memory-study/study/representation-and-use/) ·
[已有结构化学习实验](../decision-learning-study/README.md)

这一研究把问题从显式条件特征推进到自然语言：同一种使用条件换成中文、英文或自然混写时，
判断能否保持；条件真正改变时，又能否随之改变。中文反馈纠正后，还要检查英文／混写的
同范围判断与原本正确的邻近范围。

当前没有训练多语言 scorer，也没有证据证明模型已学会某位使用者的偏好。协议明确分开
公开原创诊断、私人真实材料的可用性检查，以及需要情境化反馈的个人取用研究。
静态 reading room 不连接私人记忆服务；原始记忆、标签、向量、小头权重和可反推内容的
逐例输出都不属于公开网站 artifacts。

拟议实现先使用冻结的多语言 encoder，将参数学习限定在独立小头。固定候选比较多数类、
cosine 阈值、保存反馈案例近邻和正则化线性头；更复杂的 attention 结构只在明确要回答
表示或容量问题时追加。模型复杂度、CPU 资源和数据规模均不是成绩保证。

官方 [multilingual E5 small model card](https://huggingface.co/intfloat/multilingual-e5-small)
给出 384 维表示、512-token 输入边界与 query/passage 使用方式；这些支持候选选型，
不证明在混写、否定、作用范围或私人效用标签上可靠。不得直接沿用不同编码器空间的旧权重。

运行环境和预算尚未批准为执行配置。后续真实执行需要单独记录模型 revision、输入身份、
训练和测试分组、实际 token 长度、截断、计时、峰值内存与 raw/derived 输出。
目前没有可下载的训练权重或结果 receipt；本文不是已经完成的模型实验。
