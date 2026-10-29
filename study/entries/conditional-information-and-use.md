# 新材料的价值，为什么要连同已有材料一起问？

一条信息单独不能回答问题，和手头已有材料放在一起却可能成为关键。另一条信息单独很好用，加入已有集合却没有增加任何区别。若把这些材料各自贴成“有用”或“无用”，我们会丢掉研究真正需要解释的关系。

这也是已有[条件化取用协议](../../research/multilingual-use-policy/protocol.md)提出的问题。本次没有把这句话当成新理论，而是把它放进一条实际执行的本地链路：原创材料经过确定的 writer、真实 SQLite FTS5 排名、选材、准确字节预算、消费者与独立评分，保留每一步发生了什么。

[完整研究](../../research/conditional-contribution-study/README.md)有四个构造 family、九个 case。六种材料条件、两种表示、两种送达模式、两种选择政策和两消费者展开成 **864 个本地 job**；它们不是864个独立经验样本。经验样本数为 **0**。原生检索确实运行了，scripted/oracle 控制也确实产生了请求、响应与评分；真实模型与真人研究没有执行。

## 条件增量和交互不是同一个量

令 B 是已有材料，S 是候选新材料，Y 是同一问题上的结果。我们分别记录：

```text
S 相对于 B 的增量 = Y(B+S) − Y(B)
双源交互 = Y(B+S) − Y(B) − Y(S) + Y(empty)
```

本研究的Y是声明世界合同下是否答对，取0或1；它不是材料永久价值、理解程度或情境效用评分。没有依据时的暂缓与错误作答在响应字段中分开，不能只看一个0就把它们说成相同失败。

对无成本、能够忽略额外信息的理想决策者，更多信号不会使最优风险变差。如果raw包含compact保留的全部字段，它也可以模拟这种compact。真实比较的困难在于检索、读取、截断、计算以及消费者。这些约束可以使实际输出变化，却不构成信息论的反例。

## 首先让互补和重复都得到完整位置

互补家族穷举四个二值x/y世界，问题是XOR。B给x，S给y；二者单独均不足以计算。完整送达且top-k保留两条时，scripted在四世界的B和S条件都暂缓，B+S都正确。对应增量为1，交互为1。

加入一份B副本并不提供y。另一个sham对照则保持与S的writer输出相同UTF-8字节数、相同检索key，内容只是无信息padding。它也不能完成XOR。这里的sham不是“没有处理”：它仍可能占据排名、返回位置和字节预算。它隔离的是长度相同不等于贡献相同。

重复家族的B和S都记录badge为amber。B、S、B+S都答对，S相对B的增量为0，交互为−1。这个负交互表示冗余，并不说明S单独是坏材料，也不表示新增信息降低了理想最优能力。

这些例子是有限机制控制。我们没有估计自然来源互补发生的频率，也没有宣称机器已经能自动判断真实文章的新颖性。侧信息和任务若改变，同一材料会得到不同的条件贡献。

## 检索实际做了什么

本轮直接复用[既有检索研究](../../research/experience-reuse-retrieval-study/README.md)的rank/select函数，实际建立SQLite FTS5索引并执行BM25查询。只有key进入索引，value不参与打分；分数越小越靠前，同分按插入顺序。所有候选、score/rank、selected IDs和top-k都写入receipt，评分答案不提供给retriever。

methods家族让相同key携带两条不同条件的方法：open时enter，locked时unlock。问题明确要求locked。top-k完整保留两条时，消费者选择unlock；unique-key认为key相同只留第一条open，消费者于是暂缓。

这接续了旧研究已经指出的去重反例，但新增的是这次真实排名之后的实际送达、请求和消费者输出。它没有证明任何去重方案总体更好。按key重复不等于方法重复，返回条目也不等于条目适用；必须看到信息在什么阶段被合并掉。

## 两条都选中了，为什么仍然没有回答？

[表示与使用研究](../../research/representation-use-study/README.md)已经建立actual-delivery合同，并清楚说明其旧equal-900样本没有出现新的截断反差。本轮使用独立原创材料与200-byte预算，得到一条新的实际观察。

XOR的raw B+S中，两条候选均被选中。完整模式送达两条完整JSONL，消费者可以计算；equal模式按选材次序截取200个UTF-8 bytes，只剩B为完整记录，第二条S不完整。消费者只解析完整JSONL，因此暂缓。

compact writer只删除prose说明，保留相同必要字段；它不接问题或gold，也不是自然语言摘要模型。在同样200-byte预算中，B与S都完整到场，消费者回答正确。

| 同一XOR世界与top-k | 实际完整到场记录 | 输出 |
| --- | --- | --- |
| full/raw/BS | B、S | 正确XOR |
| equal/raw/BS | B；S被截断 | abstain:insufficient |
| equal/compact/BS | B、S | 正确XOR |

所以，这个差异可以定位到具体送达路径，而不是笼统说“raw不如summary”。full只表示选中的材料完整到场，不表示检索器看见全世界；200 bytes是诊断单位，不是模型tokens。request总bytes另存，oracle额外信息也不受memory预算限制，不能把它算作公平胜者。

## 世界变了，与证据变错了

revision家族保留旧通知Thursday，以及生效时间更晚的新通知。baseline世界当前为Friday；world-change把有效状态和新来源一起改为Saturday，并重新计算gold。evidence-corruption则保持世界当前Friday，只把送达新通知改成Saturday。

完整top-k条件下，后两种情形的消费者都回答Saturday。world-change中正确，corruption中错误。同一个输出、同一种对证据变化的响应，可以在任务结果上具有相反含义。

因此“材料确实影响回答”不能直接升级为“材料帮助了任务”。本构造可以审查输入变化与scripted的固定运算，却没有识别语言模型内部路径。全程`used`仍为unknown。引用ID属于完整送达记录，只证明membership；不证明引文相关、支持充分或因果使用。

## 结果怎样成为下一项研究

本轮的[Observation链](../../research/conditional-contribution-study/observation-chain.json)绑定了真实XOR equal/raw请求、原响应、评分、候选/选择/送达及receipt身份。它并列三种解释：writer丢失必要信息、预算使信息没有到场、信息到场后消费者失败。

full/raw控制限制了第一种解释；equal/raw确实只送达一条完整记录，支持这份构造中的送达损失；matched compact控制没有检测到同一scripted消费者在足够字段下失败。它不是从一张总分图推测原因，而是沿实际中间材料缩小解释范围。

由此产生的下一设计尚未执行：保持world、query、必要字段、检索顺序与消费者，只改变prose padding长度和memory预算，观察第二条完整记录的阈值是否移动。这个设计有具体预测，也有尚未取得的证据。它不必为了成为合法研究入口，先变成一次付费模型实验。

## 可重放的，不只是成功数字

每个raw run固定源码、协议、corpus、原生retriever、settings、SQLite版本和job清单。started保存实际request及audit，receipt保留原始响应字符串、评分和绑定；每次尝试独立，发布采用完整字节的原子排他写入，不覆盖历史。

本轮完整运行864 jobs后，原生replay核对了实际请求、排名、送达、响应与评分；独立local recomputation又与公开保存结果一致。24项测试覆盖gold隔离、sham、原生FTS5、同key不同方法、源身份漂移、parse失败、输出损坏、进程中断及新attempt恢复。

本地纯函数可在明确新attempt中重算；外部provider提交超时则不同。模拟transport检查中，提交unknown会阻断自动重试，必须先核对外部receipt，再明确决定是否重新提交。review也绑定具体content/rubric，评分合同变化不能沿用旧确认。本轮没有人工review数据，这只是接口验证。

## 模型计划已经具体到哪里

[待绑定计划](../../research/conditional-contribution-study/provider-plan.json)固定432个非oracle cell，逐字system/user messages、原创材料范围、delivery digest及输入bytes。每cell输出上界96 tokens，总输出上界41472 tokens。

provider、exact model/revision、tokenizer、实际输入token数和费用上限仍未选择，授权状态为false。当前的可执行adapter是注入JSON transport边界，不是一个未经官方文档核对就宣称兼容的真实HTTP客户端。绑定实际provider后，还需要计量输入与费用、生成新的不可变计划并取得明确授权；这部分不能以mock成功替代。

这没有阻止本地科学工作形成完整结果，也没有给它补造模型成绩。四个family都被设计者看过，不是held-out；864个条件展开不提供总体精度的统计功效。研究成果在于把条件增量、冗余、排名损失、实际送达与消费者输出接成一条可检查的链，并保留这条链还不知道的事。

[观察合同研究](distinguishability-and-observation.md)进一步问：哪些现有记录仍不能分开竞争解释？[AMS纲领](../programme/thesis.md)则保留更宽的研究空间：理论可以改变我们要区分的对象，源码可以改变允许操作，新的材料也可以让问题本身发生变化。这里的局部控制是其中一条已经执行的路径，不是所有研究都必须采用的答案模板。
