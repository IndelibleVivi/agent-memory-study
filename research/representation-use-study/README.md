# 概括之后，往事还记得准吗？

Agent Memory Study editors · 2026-09-25 · **研究方案：proposed-not-run**。

[进入跨源共读](https://indeliblevivi.github.io/agent-memory-study/study/representation-and-use/) ·
[原事件／概括／并存的比较协议](protocol.md) ·
[双语记忆使用策略的独立问题](../multilingual-use-policy/README.md)

这项研究追问：概括是否帮助新推论，同时保住历史来源和当前适用范围？目前交付的是
论文串读与可检验的协议，没有生成模型输出、参与者数据或效果数字。文献的实际阅读范围
与定位统一由 `data/materials.json` 中该专题的 `externalReadings` 维护，页面展示同一来源。

现有 [Jev 源码实验](../jev-memory-contract-study/README.md)看到了指定判断下原节点与派生
节点并存；[学习与纠正实验](../decision-learning-study/README.md)看到了给定特征空间内的
参数变化。前者未测回答收益，后者未测自然语言语义识别。本协议提出两者尚未回答的消费端问题。

原事件、概括和并存三臂同时测来源辨识、当前适用与跨事件推论。概括删除的信息单列为
表示损失，不能要求模型凭空补回；信息充分时的错误、信息不足时恰当暂缓，以及无依据编造
分别计数。完整输入和固定预算比较分别报告，位置置换仍属于同一个事件组。

新论文不会因为在共读中被引用就自动加入 bibliographic materials / Zotero，也不改变
既有材料的 `noteDepth`、paper findings 或历史 receipts。生物记忆和模型内部表示提供
问题与评价方法，不直接证明某种 agent memory 设计有效。

执行前仍需固定：原创事件组、可检查的答案与信息充分性标注、answerer 的具体模型与版本、
输入预算及运行资源。先公开这些选择，再运行；如果看过开发结果后修订协议，保留探索性修订记录。
