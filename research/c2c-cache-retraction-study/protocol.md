# KV 来源撤回：预先确定的实验协议

日期：2026-09-18。作者：Agent Memory Study editors。
这是由 C2C 的 cache enrichment oracle（arXiv:2510.03215v2 §3.2.1）启发的原创机制实验，
不训练或运行 C2C fuser，不复现其 benchmark，也不测试权重级 machine unlearning。
本文在首次模型实验前写定；后续实质变更须明确记录。

## 问题与单位

用公开的小型 causal LM、原创合成事实，检查删去来源前缀 C 的 KV slots 后，
保留的 suffix R 是否仍依赖 C。当前事实、明确更正后的当前事实、明确更正后的历史事实
分别观察；历史可恢复性和当前适用性不能合并成一个“遗忘成功率”。

固定模型 HuggingFaceTB/SmolLM2-135M-Instruct，revision
`12fd25f77366fa6b3b4b768ec3050bf629380bac`。CPU / float32 / eager attention / eval，
torch 2.8.0、transformers 4.51.3；无采样、无训练、无远程推理、无私人输入。
四组事实、每组两种来源内容：只替换前缀事实值作为配对，避免把中性前缀本身当成无影响基线。
每对两种来源共用完全相同的 R、Q 和第三个 update 值，故更正/历史题也不把 query 改动混入来源对照。
fixtures 在首次正式运行前固定。所有条件和不符合预期的结果均保留。

## 条件

把原始输入拆为独立 token segments C、R、Q；明确保存分段 token IDs，
不声称它们必然等于一次性编码拼接字符串。R 不重复事实；Q 是每个条件下重新 forward 的查询，
不得复用 C+R 的末 token logits 作为撤回后的第一个答案。

1. **full**：prefill C+R，保留全部 cache 后输入 Q。
2. **trim**：prefill C+R，仅保留 R 的 cache 后输入 Q。
3. **recompute**：不输入 C，从空 cache 重算 R 后输入 Q。
4. **neutral_trim**：用与 C 等 token 长的中性前缀 N prefill N+R，裁掉 N 后输入 Q。
5. **masked_trim**：prefill C+R 时屏蔽对 C 的 attention，然后裁掉 C 后输入 Q；
   应与 recompute 接近，这是阻断来源依赖的负控制。

所有条件的 R 与 Q 使用相同的绝对 position_ids：R 从 |C| 起，Q 从 |C|+|R| 起。
裁剪后 physical cache_position 从实际 cache 长度起，attention_mask 覆盖 retained cache + query。
RoPE position 与 physical cache index 分开；不把位移差异误当内容效应。
cache 必须按条件独立 clone，防止 forward 原地扩展导致条件串扰。

## 观察与验收

- 保存每个条件的 prefix/suffix/query IDs、长度、position 范围、mask contract、
  候选答案 token 概率、完整词表 top-5、greedy continuation。
- 比较 next-token 全词表 logits 的最大绝对差、probability total variation，
  与各层 suffix K/V 最大绝对差。候选词可能是多个 token 时使用完整序列 log probability；
  不将首 token 概率称为整段答案概率。
- 配对 trim(Ca) 与 trim(Cb) 在相同长度、位置、mask 下的差异检验内容依赖；
  recompute 对来源替换不敏感，masked_trim 应与 recompute 在 float32 容差内一致。
- masked/recompute 全词表 logits 容差预定为 1e-4；第一层 suffix K/V 应无前缀内容依赖，
  后层是否出现依赖由结果决定。容差失败先检查 runner，不能无说明调大以换取 PASS。
- full cache 的 split prefill+Q 应与同 IDs、同 position 的整段 forward 一致（1e-4），
  作为 cache 使用正确性的正控制。
- 结果可为“检测到残留”“未检测到”或“控制失败，不能解释”。
  最大差异只表示本次 forward 的数值差异；不推出所有模型、所有来源、持续时长或现实错误率。
  更正/历史题只有模型在 full 条件下具备相应行为时才支持该行为的进一步比较。

## 验证层级

保存 receipt 可在无模型环境检查结构、fixture binding、派生统计；该检查不等于 fresh inference。
fresh run 必须显式提供上述固定模型的本地目录。下载权重、环境和原始 PDF 留在 repo 外。
完整 logits 可以作为外部复核文件；公开 compact receipt 保存足以核对所声称比较的指标和控制，
明确不声称 compact receipt 独立证明了模型真实执行。

## 实施记录

首次 inference 前，四对来源均确认 9 tokens；中性前缀是重复九次的单 token ` note`。
它只是固定长度控制，既不自然也不保证对模型中性；主内容因果对照依赖同长度、同格式的事实值替换。
使用自定义 cloze 提问，没有套用模型 chat template，不宣称测量最佳 instruction-following 能力。
模型文件由固定 HF revision 取得；权重 SHA-256 与该 revision 官方 LFS metadata 相同，
`model-files.json` 用于 fresh run 的确切输入身份检查，不用于证明模型行为。

## 2026-09-18 · 独立审阅后的 amendment

此 amendment 写于首轮 120 个输出已执行且被查看之后、下一次 fresh run 之前。
[initial-summary.json](initial-summary.json)保留首轮 fixture、全部 12 组主比较和控制结果。
首轮使用 2D padding mask 屏蔽 C；其最终 logit 负控制通过，但没有明确避免全遮蔽的 C query 行。
不得把下面新增控制、问题和分析称为首轮预注册内容。

1. 保留手工 slice 后重建 `DynamicCache`、独立 clone、显式位置和 manual greedy decode；
   没有使用裁尾的 `crop()`，也没有把步骤交给可能重编号的 `generate()`。
   新增 native/repacked cache 的 Q logits 与扩展后 K/V 对照。
2. 新增 shifted-recompute 的 split / 一次性 forward 对照，比较 Q **所有位置**的 logits；
   每次 Q 另取前半段独立运行，与完整 Q 的同一前半段比较，检验后面的 query tokens 不泄漏到前面。
3. masked_trim 改用明确的 4D causal additive mask：C 自身保持 causal，只有 R→C 被遮蔽。
   验证所有层 R→C attention mass 为零、masked 来源配对 K/V 相同、masked/recompute 所有层 K/V 接近。
   zero-based layer 0 的 K/V 在该层 attention 前投影，内容依赖最早可出现在 layer 1。
4. 原来的三种 query 文本保留但改用明确名字；另加 record_correction 的 corrected_truth 与 prior_report，
   与 state_change 的 updated_current_state / prior_world_state 分开。最终共 4×2×5×5=200 个输出。
   prior_report 问先前记录说了什么，不把错误记录当作过去世界的真实状态。
5. 候选实际均为一个 continuation token；新增长度与 `encode(Q+answer)==Q_ids+answer_ids` 检查。
   原 runner 已按 teacher-forcing shift 评分，候选从独立 post-Q clone 开始，算法无需改变。
6. 新增探索性来源值 margin contrast `(z(Ca)-z(Cb))/2`，其中 `z=logP(a)-logP(b)`。
   它是在首轮之后决定报告的诊断量，不是原先预注册的行为主指标。
   两个 source variants 的 full 条件都偏好该 query 的目标候选，才标为 `full_candidate_eligible_both`。
   对 corrected_truth / updated_current_state，正确值相同；旧值 contrast 仅描述残留的来源偏向，
   不能解释为正确率增益。所有不满足资格的 cases 仍完整保留。

采纳审阅的具体控制建议，不把其“阻断项”标签直接当作既有实现已错的证据。
所有数值控制继续使用 `1e-4`；模型、原有 source/retained/query 文本及首轮主要比较均未调优。

## 2026-09-18 · 数值控制失败后的 amendment

加强控制后的 200-output float32 run 没有全部通过：shifted split 最大差 `0.00014495849609375`，
缩短 Q 的因果前缀对照最大差 `0.000148773193359375`，均超过预定容差。
这次执行保留为未通过控制，不用调大阈值改判。

定点诊断保持同一输入，比较 float32 / float64 运算与相同 shape 的未来 token 置换。
lamp/corrected_truth 的 shifted split 差从上述值降为 0；gate/updated_current_state 的
recompute 缩短 Q 差从 `6.699562072753906e-05` 降为 0；相同 shape 的未来置换在两种 dtype 下均为 0。
这支持 shape 相关数值运算差异的解释，但定点诊断不代替全组控制。

最终 fresh run 改用 **float64 model parameters / hidden states**，继续保留同一 `1e-4` 阈值，
重新运行全部 200 个输出与所有控制；再为每行加入相同长度未来 token 置换的因果控制。
上游 Llama 的 RoPE frequency 与 eager softmax 仍显式用 float32，因此不称为端到端 float64 算术。
CLI 的 `--dtype float32` 保留，用于复查这个实际遇到的精度敏感性，不作自动 fallback。
见 [execution-history.json](execution-history.json) 的各次结果与定点诊断；最终执行不是盲确认性重复。
