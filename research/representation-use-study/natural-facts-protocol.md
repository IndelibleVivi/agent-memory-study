# 去掉选项线索之后：范围与历史事实诊断

2026-11-07。原选择题主实验和事后question-only诊断之后，后者得到Luna65/72、Sol68/72，
证明原题有很强的题干／选项线索。这组任务因此是公开披露的探索性设计修正，不是未见过
的历史或预注册的确认性复现。原72题及全部结果不删改，也不把新任务行增加为独立历史。

沿用原12段历史和全部24份question-blind writer输出，不再次调用writer，也不修补记忆。
另写每段2个任务，共24题。题目不再提供带正确性暗示的选项解释。回答为一个具体动作值、
集合、数字或日期；JSON Schema只限定格式或中性的操作名称。reader可返回null表示当前
证据不足。每段至少一个问题需要把范围用于一个新指定任务；其余检验历史状态、日期或
实际量值。24题中2题的来源确实未定答案，以null作为gold；其余均可从完整历史回答。

`natural-facts.json`在全部新调用之前冻结问题、schema、gold、支持和解释。writer原先
既没看到这组问题，也没看到原选择题。reader只收到本次问题、回答schema，以及raw、
prose、ledger或空memory四种条件之一。Luna和Sol各一次，24×4×2=192次，独立调用。
raw与两种记忆完全沿用前轮实际输入内容；两种模型共享同一次writer输出。

主分数为严格的格式化答案匹配；集合不计顺序，拒绝重复项。null在gold非null时记为
未恢复／暂缓，不混同错误行动；非null且不匹配计为错误值。两道未定控制另报。gold及
正常化规则在新调用前固定，不按回答扩充同义词。日期题输出YYYY-MM-DD；中性schema
标签不附带日期、适用解释或对错暗示。没有后端工具行动或自由长回答质量评分。

预先报告全部24题、每历史／题型，另报告22个来源充分任务，比较每种记忆与raw、none。
原选择题ceiling不作为新任务的成功标准；若没有记忆仍能大量答对，也照实报告。不能从
一次writer或少数历史的错误宣称普遍格式因果关系；来源存在、送达及可恢复性分开解释。

官方Responses、reasoning=low、standard tier、store=false、1024输出上限；无重试，
无provider fallback。三阶段已有最大费用预留连同本阶段全输出预留合计仍受USD10约束，
先官方token counting，再generation。`natural_facts.py`复用既有传输与artifact绑定，
另存source/protocol/task identity，并绑定原始writer的manifest与实际记忆。raw留repo外，
公开`natural-facts-results.json`只含任务定位、格式化值、分数和usage；不含原始模型文本。

离线测试与`check-saved`不调用API。实际运行用`prepare --parent /path/to/primary
--budget-parent /path/to/question-only --output /path/to/new-run`，再显式`run --run ...`；
`replay --run ... --output ...`只读冻结响应。旧阶段在新调用前已全部结束，不允许并发
执行别的付费阶段来绕过累计预算；不同协议与结果始终保留。
