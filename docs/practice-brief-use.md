# 一次实际取用：AMS 的实践 brief

Agent Memory Study editors · 2026-09-21 · 工程采用记录。

查询：“候选增加之后，结果容易被重复条目占满。”

这个问题对应 [旧经验还在，也可能失去被使用的机会](https://indeliblevivi.github.io/agent-memory-study/?finding=retrieval-candidate-competition)。依据是 [经验检索竞争](../research/experience-reuse-retrieval-study/README.md) 的有限反例：重复内容可以占去返回名额，只按 key 合并又可能丢掉必要条件。它参与了 AMS 自己的 brief 查询设计。

## 改变了哪个选择

每个 canonical finding 是一个候选，证据列表随判断一起返回。多个证据链接不会展开成多条候选，也不因重复添加同一份 evidence 而增加该判断的排名。不同条件的判断保留独立 ID；相同标题、主题或 trigger 不构成自动合并依据。

这使读者在有限的返回名额里取得不同判断，并能沿每条判断追到原始依据。它不执行语义去重，不决定目标项目应当采用哪种方案。

## 怎样核对

共享实现是 [assets/practice.js](../assets/practice.js)，行为测试是 [tools/test_practice.cjs](../tools/test_practice.cjs)。运行：

```bash
node --test tools/test_practice.cjs
node tools/export_practice.cjs --query '候选增加之后，结果容易被重复条目占满' --format markdown
```

测试检查重复证据不会增加名额或排名、同主题不同条件的判断仍独立存在、无关查询不会硬给答案，以及导出保留证据与边界。网页与 CLI 使用同一查询和 brief 实现。

## 这条记录证明什么

状态是 **adopted / 已采用**：研究判断参与了一个具体实现决定。运行测试可以验证候选与导出合同；这既不是用户研究，也没有证明真实开发时间减少、检索质量更高或 agent 任务成功率提升。

没有做目标项目的因果对照，因此不能把“引用过”“采用过”和“有帮助”写成同一件事。以后若发现独立 ID 仍使相同判断重复占位，或不同条件的判断互相挤占，这条采用记录应补上失败观察并修订方法；保留当前证据的日期与范围。
