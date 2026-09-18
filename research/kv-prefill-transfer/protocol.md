# 小配对跨模型 KV prefill reuse — 实验协议

状态：runner 已实现，21项本地测试及随机小模型闭环通过；真实 mapper 尚未拟合，尚无迁移质量结果。已执行范围见 [validation.json](validation.json)。

本实验沿 [Cross-Model KV Cache Transfer in LLM Families, arXiv:2608.03893v1](https://arxiv.org/html/2608.03893v1) §3 的中心化 ridge 与跨层输入构造，准备 Qwen3-0.6B → 1.7B 的缩小机制复现。模型、序列长度、校准规模和固定 k 与原文不同；不声称复现论文表格，也不把 cache 表征迁移叫作事实或记忆的正确继承。

## 固定设计

- source：`Qwen/Qwen3-0.6B` @ `c1899de289a04d12100db370d81485cdf75e47ca`。
- target：`Qwen/Qwen3-1.7B` @ `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`。
- 两者28层、8 KV heads、head_dim128，full attention。固定 revision 的 tokenizer.json、tokenizer_config.json、vocab.json、merges.txt 已逐文件验证一致；实际 prepare 仍对本次输入核对 token IDs。
- 公开校准文档64篇、validation 8篇、test 16篇；每篇截取256 tokens；按完整文档分割，重复文档身份不跨 split。
- 首轮固定 `top_k=1`，不通过 test 选择 k。校准位置 stride4；sum-loss ridge `lambda=.01`；层选择对应 head 的 K/V R²平均，数值稳定项 `selection_alpha=1e-6`。层选择也仅使用 train。
- validation 用于定位实现/选择后续实验，任何据此修改都写明；test 只用于冻结后评价。小规模 test 无力建立广泛性能声明。
- 真实模型 CPU BF16、eager attention；首轮 fit 固定 FP64 sufficient statistics，固定线程数。实际精度必须记入 receipt，不能以输出 dtype 冒充所有内部算术精度。

## 分阶段计算与数据边界

source 和 target 在独立 capture 进程中先后运行，不同时驻留。每个文档的 K/V shard 带 token、模型 revision、split 身份；只对相同输入与身份的完整 shard 续跑。train 保存 stride4采样，held-out保存完整prefix。K 在正确位置上去源/目标 RoPE 后以FP32落盘，V保持模型精度；位置不从压缩后槽位重新编号。held-out target另保留未修改的post-RoPE K供native分支使用。去RoPE采用固定上游的转置旋转；有限精度cos/sin不严格满足单位范数，因此其结果是本实验定义的content坐标，不能声称精确恢复模型内部pre-RoPE张量。

fit 不加载模型；读取 train shards，按目标层分块选择源层、积累统计量和求解。每目标层所有目标 heads共享同一组被选源层；最终特征拼接这些源层的全部 KV heads。K→K与V→V分别有自己的XTX/XTY；每一种特征内共享XTX一次求所有目标head输出列，与独立head的同lambda ridge等价。采用论文打印方程 `(Xc.T Xc + lambda I) W = Xc.T Yc`，bias 为 `mean(Y)-mean(X)W`，不把lambda隐式乘样本数。

独立社区实现 [souvikDevloper/kvbridge](https://github.com/souvikDevloper/kvbridge/tree/949d81d7861e998d5c42db68d7567cc70e2e58c5) 的 `RidgeAccumulator` 是固定外部依赖；本研究不把该实现称为作者官方代码，不复制另一份同功能回归器。社区上层capture默认同时加载模型，故本runner负责磁盘阶段与评价路径。

## 三分支评价

对同一 held-out 文档，prefix为前192 tokens，continuation为随后64 tokens。为了使第一个 continuation token 也获得真正由目标模型计算的概率，只迁移前191 tokens；把第192个prefix token与后续teacher-forcing输入交给目标模型fresh forward。

1. `native_target`：独立捕获、保留原始post-RoPE K的目标模型prefix cache。
2. `mapped`：source prefix经冻结mapper；每层补回目标RoPE。
3. `direct_source`：相同geometry下，source K去源RoPE后直接补回目标RoPE，V不经过学习映射；作为交接对照，不假设它必然差。

索引合同固定为 `past=x[:191]`、`fresh=x[191:255]`、`labels=x[192:256]`，fresh的64个logits逐一预测64个labels，位置为191…254；手动log_softmax评分，不借用HF内置causal loss的再次shift。完整参照是 `target(x[:255]).logits[:,191:255]`。

每分支使用独立cache对象。native logits只能用于评价比较，不能作为mapped的首token、输入状态或回退结果。不对坏的mapper自动fallback到native。核对原生分段路径与目标full-prefill对照，确保所有64个continuation标签没有漏一位或多移一位。

另列target content去/补RoPE往返相对raw native的误差。这是数值诊断，不替代native上限，也不计作跨模型改进或退化。

报告每文档 mean-per-token continuation NLL（包括第一token）、`exp(candidate NLL - native NLL)`、`KL(native || candidate)`、next-token top1 agreement与首token的gold_token_id、p_gold、argmax_token_id。聚合至少保留逐文档结果，不把同一文档的tokens伪装成独立样本。Native原生性能不能换算为论文benchmark retention。

同一批实际迁移的191个held-out prefix位置上，双方K都在去RoPE后的坐标中、V在原生坐标中，另记K/V重建MSE与R²；其聚合定义必须标明，不能把flattened整体R²写成paper head-averaged R²。随机模型的质量数值只验收数据流。Attention-output cosine 若未实现或未正确捕获，应明确记为未测，不以cache cosine代替。

时延区分采集/离线拟合、已有source cache时的映射、目标suffix评价；不同进程的首次加载与warm计算分开。未实际测到的端到端加速不外推。

## 本地验收与解释边界

随机小Qwen3走同一套磁盘与计算路径，覆盖：分阶段运行、全head特征顺序、非零位置/不同theta的RoPE对照、native split/full标签对齐、identity mapper、sum-lambda、split绑定与续跑身份。已通过的随机控制只证明这些具体实现合同；不证明真实模型映射有用。

先完成普通held-out质量基线，后续才开展来源撤回扩展。届时用同一冻结mapper比较“受旧来源条件化的保留cache”与“从未接触来源的重算cache”，先确认目标原生分支具备回答资格。RoPE-stripped不表示状态没有历史依赖。

真实实验尚未开始，统计阈值、数据快照身份与实际执行状态应随冻结run manifest公开；所有失败与协议修订保留，不修改既有结果伪装成初次确认。

## 独立方法检查后的补充

- 首logit future-invariance：修改continuation未来tokens，但保留前192tokens，首个输出分布应不变。
- mapped/direct候选计算接口只接收source与mapper；target reference在候选算完后才读取。用不可访问target reference的测试验证依赖，而非只检查函数名。交换分支顺序后输出不变；错误mapper不得fallback为native。
- fitter只消费train，held-out不可访问时仍可拟合同一结果。层选择分数为每个目标head在对应source head上拟合K、V后，分别按全部校准token与head维度的SSE/SST计算R²，再对2H个R²等权平均；selection_alpha进入未归一化sum方程。常量target沿固定RidgeAccumulator的零方差约定报告，不据此扩展质量结论。
- 非零位置/不同theta以Transformers官方rotary为oracle；仅用自写inverse/apply互相抵消不足以验收。BF16去/补RoPE带来的坐标与量化误差须单列，不能让重编码后的native分支冒充未经改动的原生上限。
- 1024×1024矩阵的tensor-only probe已执行；首轮真实fitting前仍需一条256-token pretrained target经capture→disk→rebuild→191/64 scorer的full/split检查，旧128-token资源探针不能代替。
- 真实test首次执行前冻结输入、模型、依赖、代码与mapper身份；test查看后影响结果的修改应记录为新探索，不能重新称为未见测试。

上述检查用于拒绝具体的错位、泄漏、别名与数值错误；它们不设置任意的论文性能通过线。随机模型、资源探针与真实迁移结果始终分列。

本地验收已覆盖这些实现合同，包括完整256-token随机模型路径。尚未执行的pretrained单文档检查由`probe_native_cache.py --run`提供独立入口；此项必须单独记录，不能用随机模型结果替代。
