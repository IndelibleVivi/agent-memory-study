# MemSkill：部分回退与状态配对

**Status:** completed static source study and proposed, unexecuted intervention. Cove · AI-assisted research · 2026-11-05.

这项研究从 AMS 已有的经验复用、学习与更正问题继续，检查“退回最佳技能库”具体恢复了什么。它没有训练模型、执行 provider、运行 ALFWorld，或复现论文性能。

## 阅读入口

- [完整机制札记](memskill-mechanism-dossier.md)：论文与固定源码、状态对象、阶段奖励、普通回退、early stop、完整 checkpoint、ALFWorld 数据角色，以及可检验的状态配对问题。
- [四格迁移与回退协议](memskill-negative-transfer-protocol.md)：两个库 × 两个兼容 controller；每格从相同经验重建 MemoryBank；数据角色、效果尺度、负迁移定义、缺失条件与精确后续委托。
- [源码身份与逐文件哈希](memskill-source-receipt.json)：固定 `ViktorAxelsen/MemSkill@f65b797338033f4f9c34822f1810f9c2747e6022`。哈希固定实际核查字节，不证明任何运行分支已触发。
- [研究文章](../../study/entries/memskill-state-pairing.md)：核心论点及与 AMS 既有判断的联系。

## 本轮实际结论

所检查代码的演化阶段 snapshot 保存操作库和训练奖励等信息；普通回退恢复库，并不在该分支恢复历史 controller。完整 checkpoint 具有 controller、optimizer 等状态保存／载入能力，属于另一个操作。early-stop 在普通回退之前退出，final 保存当前状态。三个路径必须分别描述。

阶段平均奖励汇总训练期间的反馈，可能跨越多次 controller 更新；它不能直接归给一个静态历史配对，更不能识别重组配对 `(B_i, θ_t)` 的表现。这个推论并不证明部分回退有害。四格实验将区分库、controller 与配对效应，现阶段没有结果文件，也不应补造模型分数。

## 范围与继续条件

源码提交时间为 2026-10-01，晚于论文 v2（2026-05-24）；两者不能自动视为同一实验版本。所有缓存、checkpoint、实际训练分组和最终测试身份仍需要运行层面的清单。训练 A/B 可能重叠的源码分支不等于已观察到最终测试泄漏。

第一步是只读预检：是否存在两个可配对的完整 checkpoint，以及可追溯的经验／训练反馈／评估材料。只有 bank snapshot 时，不能重造历史 controller。预检充分后再固定模型、配置、预算与任务分层。该研究复用现有源码与研究目录，不建立新平台或通用适配器。

完整上游代码留在外部固定 checkout；这里提供作者研究与哈希回执，不复制上游整个仓库。文章、协议与静态核查不是三份独立实证验证。
