# C2C source-contract audit — 上游实现函数级审查

日期：2026-09-18。作者：Agent Memory Study editors。
状态：**source-bound 执行完成**。对固定 commit 直接 import 并运行了真实的 `TokenAligner`
与 `C2CProjector`；trimming 示例只做源码级检查。

本单元审查公开 Cache-to-Cache（C2C）实现的一小组函数级契约：成对 tokenizer 一对多对齐的
信息选择、`C2CProjector` 的 learnable gate 与 residual fusion、示例 cache enrichment 的
trimming 与 position/mask 处理，以及 shipped 训练/评估配置。它不是论文精读、不是 benchmark
复现、不是模型实验，也不写入 canonical data。预先登记与更正见 [protocol.md](./protocol.md)。

## 证据对象

| 对象 | 身份 | 证据标签 | 边界 |
| --- | --- | --- | --- |
| Paper | [`arXiv:2510.03215v2`](https://arxiv.org/abs/2510.03215v2)（ICLR 2026 camera-ready） | `paper-reported` | 只按 canonical section/appendix 引用；不 vendor PDF。 |
| Official code | [`thu-nics/C2C`](https://github.com/thu-nics/C2C) commit `113c3a9b2538cbf096a0477e1ec99ae2a2e0d12a`（2026-02-06，clean tree） | `official-source` | 执行与检查都绑定该 commit；`results.json.source` 记录每个文件的 sha256。 |
| Tokenizer stand-in | 本目录 `fixtures.json` 的手写 vocab | `bounded-input-substitute` | 只为固定一对多输入形状；**不是** Qwen tokenizer metadata，不构成真实 tokenizer 结论。 |
| 执行 receipt | `audit.py run` 的 `results.json` | `official-source execution receipt` | projector 用 toy 维度合成张量；aligner 行用替身 tokenizer。 |

## 结果

### 1. one-to-many 选择（真实 `TokenAligner.align_tokens(..., return_mapping=True)`）

保留判定按 fixture 显式声明：`exact_lexeme` = 选中 token 去空白后必须等于指定词素；
`complete_content` = 必须等于 SLM token 的完整文本。

| fixture | 角色 | SLM token | LLM 候选 | `first` 选中 | `longest` 选中 |
| --- | --- | --- | --- | --- | --- |
| `F1_negation_one_to_many` | negation | `" not"` | `[" ", "not"]` | `" "`（**丢失否定词**） | `"not"`（保留） |
| `F2_temporal_two_way_split` | temporal | `"2024"` | `["20", "24"]` | `"20"`（**截断**） | `"20"`（**截断**） |
| `F3_one_to_one_control` | control | `" the"` | `[" the"]` | `" the"`（保留） | `" the"`（保留） |
| `F4_one_to_many_first_retains` | control | `"not "` | `["not", " "]` | `"not"`（保留否定词） | `"not"`（保留否定词） |

三个可复核的点：

- **一对多确实会丢内容，且是否丢取决于策略。** `F1` 中 `first` 选中分隔空格，negation
  词素不在对齐结果里；`longest` 选中 `"not"`。这个构造输入展示的是 token 选择契约，不能直接推广到真实 tokenizer。
- **等长并列按官方行为记录，不自订规则。** `F2` 两个候选都是两个字符；source 的 `longest`
  用严格 `>` 比较，因此保留最早候选 `"20"`，**不抛错**。两种策略在该 split 下都只能拿到
  年份片段——单一候选无法承载完整日期。paper 未定义该 tie。（`F2` 的 split 形状来自替身
  vocab，不是真实 tokenizer 行为。）
- **一对多不必然丢失指定词素。** `F4` 的 split 中首候选同时是最长者，两策略一致保留完整否定词 `"not"`（不要求保留尾空白）；
  `F3` 一对一同样不受策略影响。因此 `F1` 的差异来自 split 形状与策略的组合，而不是「拆分」
  本身。

其它真实执行到的 aligner 事实：

- `TokenAligner(slm, llm)` 的构造默认是 `AlignmentStrategy.FIRST`；字符串 `"longest"`
  正常解析；非法字符串（如 `"prefix"`）抛 `ValueError`。
- special token id 走 `_map_special_token` 分支，不咨询 one-to-many 策略。
- 实例按 `tuple(slm_token_ids)` 缓存对齐结果；改实例的 `strategy` 不会使缓存失效。所有
  shipped 调用点都在构造时传入策略且不再改，故各 probe 使用新实例。

### 2. 策略取值分三层，不能合并成一个「default」

| 层 | 取值 | 位置 |
| --- | --- | --- |
| library 默认 | `AlignmentStrategy.FIRST` | `rosetta/model/aligner.py:33` |
| training script fallback | `"first"` | `script/train/SFT_train.py:394` |
| shipped **training** recipe | `"first"`（且 `is_do_alignment: false`） | `recipe/train_recipe/C2C_0.6+0.5.json` |
| shipped **evaluation** recipe | `"longest"`（且 `is_do_alignment: false`） | `recipe/eval_recipe/unified_eval.yaml` |
| 评估脚本 fallback | `"prefix"`，**不是**合法 enum 值 | `script/evaluation/unified_evaluator.py:905` |

与 paper 的边界：Appendix A.1.2 声明「empirically adopt Maximal-coverage selection as the
default」。当前源码里 `longest` 出现在 shipped **评估** recipe，而 library 默认与 shipped
**训练** recipe 都是 `first`。评估配置值与 paper 的声明相同，但其 alignment 同时关闭；本次未建立 paper-time 运行与该配置的对应关系。

### 3. `C2CProjector` gate 与 residual fusion（真实类，合成张量）

- **闭 gate = 精确恒等。** 推理分支用 `(gate_logit > 0)`；构造初值 `0.0`，因此输出与
  Receiver 张量逐位相等（`torch.equal` 为真）。
- **阈值是严格大于零。** `logit = 0` 关闭、`logit = 1e-6` 打开。
- **加性项只来自投影路径。** 打开 gate 后零化 `key_proj_out` / `value_proj_out`，输出重新与
  target 逐位相等。这与 Eq.(3) 的残差形式一致；fused cache 在下游如何被使用是另一条接线
  问题，本单元不把它读成与 §3.3.4 表述的矛盾。
- **gate temperature 退火。** `update_temperature` 从 `initial_temperature` 指数退火到
  `final_temperature`，`anneal_steps` 后钳位；shipped recipe 取 `1.0 → 0.001`、
  `anneal_steps=1929`。buffer 为 float32，报告值带 float32 舍入。
- `num_layers < 3` 触发 `AssertionError`。

### 4. cache enrichment trimming（源码级，未执行）

`script/evaluation/standard_kvcache_del.py` 的 `few_shot_delete` 分支：第一遍 prefill 之后，
每层 cache 重建为 `[0:15)` 拼接 `[few_shot_len:N)`（即模板前缀 + exemplar 边界之后的部分），
第二遍只送入 answer 前缀，position ids 从 `full_seq_len` 继续。因此保留段沿用删除前的原始
绝对位置，第二遍也不传 attention mask（注意力覆盖保留 cache + 新 token）。

- 该分支需要真实模型 forward，本单元**未执行**，只记录 locator 与语义。
- 保留原始绝对位置对「keys 已在那些位置旋转过」的 cache 是自洽的；本单元不把它判为缺陷。
- 前缀切片的行内注释写「保留第一个元素」，而代码保留的是 15 个位置。记为注释与代码不一致，
  不推断意图。

### 5. shipped 训练配置

`recipe/train_recipe/C2C_0.6+0.5.json`：base `Qwen/Qwen3-0.6B`、teacher
`Qwen/Qwen2.5-0.5B-Instruct`、`mapping: last_aligned`、`projector.type: C2CProjector`
（`hidden_dim/intermediate_dim=1024`、`num_layers=3`、`dropout=0.1`）、
`freeze: ["teacher", "base"]`、`lr=1e-4`、`weight_decay=0.01`、1 epoch、linear scheduler、
warmup 0.1、grad clip 1.0、grad accum 8、batch 4。冻结名单确实同时包含 base 与 teacher，
与论文「只训练 C2C module」一致。

## 未验证

- **真实 paired-tokenizer roundtrip 未测**：无本地 tokenizer metadata，本单元不下载模型工件。
  所有 aligner 行使用的是 `fixtures.json` 的手写替身 tokenizer，其一对多 split 形状是构造出来的。
- trimming 分支未执行（需要真实模型 forward）；其 position/mask 语义为源码级阅读。
- 评估侧 `"longest"` 是否真的进入对齐路径：shipped 评估 recipe 同时设 `is_do_alignment: false`，
  本次只记录配置值与代码路径，未端到端跑评估。
- 未训练、未加载权重、未跑 benchmark；`AllInOneProjector`（另一 registered projector）不在
  本单元范围内。

## 复跑命令

在 repo 外准备官方 checkout，固定到上述 commit；在隔离环境安装
[torch / transformers 版本](../c2c-cache-retraction-study/requirements.txt)。
`results.json.environment` 记录实际环境；此审计不需要下载模型权重。

```bash
git clone https://github.com/thu-nics/C2C.git /path/to/C2C
git -C /path/to/C2C checkout 113c3a9b2538cbf096a0477e1ec99ae2a2e0d12a
```

```bash
cd research/c2c-source-contract-audit

# 1. 对固定 checkout 运行真实类，写出 receipt（需要 torch/transformers 解释器）
python3 -B audit.py run --source-dir <checkout> --write results.json

# 2. 直接执行真实类的契约测试
C2C_SOURCE_DIR=<checkout> python3 -B -m unittest discover -s tests -p "test_*.py"
```

## Claim ceiling

- `TokenAligner` 的每一行都执行了真实实现，但输入 tokenizer 是手写替身；关于真实 Qwen
  tokenizer 的行为本单元无结论。
- `C2CProjector` 的行是 toy 维度下的结构检查，不是训练结果、准确率或质量结论。
- trimming 示例只做源码级检查，未执行。
- 本单元不支持关于准确率、benchmark、生产频率或系统行为的任何陈述。
- `F2` 记录的是等长并列下的实现行为与 paper 未定义该 tie 的事实，不是缺陷报告。
