# C2C source-contract audit：协议与修订记录

日期：2026-09-18。作者：Agent Memory Study editors。

本文件记录执行前问题及其修订；当前方法以以下 source-bound 合同为准。
论文 authority 为 [arXiv:2510.03215v2](https://arxiv.org/abs/2510.03215v2)，
实现为 [thu-nics/C2C](https://github.com/thu-nics/C2C) 的固定 commit
`113c3a9b2538cbf096a0477e1ec99ae2a2e0d12a`。
源码身份不代表 paper-time 运行身份。

## 执行前问题

1. §3.3.3 / A.1.2 的一对多 first / maximal-coverage 选择在当前实现中怎样工作？
2. §3.3.2 的 layer gate 在 inference 时怎样判定，闭 gate 是否保留 Receiver？
3. Eq. 3 的 residual 是否可用闭 gate、开 gate 和零化投影的配对输入区分？
4. §3.2.1 的 exemplar cache 删除在示例代码里如何实现，position / mask 怎么处理？
5. 模型冻结名单、对齐配置与训练超参分别由哪些 shipped config 控制？

## 实际方法

- 检查 clean checkout 的固定 commit，记录被读取文件的 repo-relative 路径与文件身份。
- 直接 import 官方 `TokenAligner` / `C2CProjector`，不复制、重写或改动其代码。
- Aligner 的 tokenizer 输入是固定手写 doubles。每个 fixture 指定候选形状和需要保留的词素
  或完整文本；每种策略使用新实例，避免实例 cache 干扰。
- 对照覆盖：前导空白后的否定词、一分为二的年份、一对一映射、否定词后的尾空白。
  末项只要求保留完整否定词，不要求保留空白。
- Projector 用固定 seed `20260918`、toy dimensions 的张量执行：gate=0、gate>0、
  gate>0 且 projection output 为零；另记录阈值与 temperature schedule。
- Trimming、训练与 evaluation wiring 仅作绑定源码的阅读，明确 `executed:false`。
- 测试验证真实官方类；无 external checkout 时 skip 不计为已执行结果。

环境为 Python 3.12、torch 2.8.0、transformers 4.51.3；exact versions 随 receipt 保存。
无模型权重、训练、API、GPU 或 benchmark execution。

## 证据上限

一对多的输入形状是构造的，因此只能说明固定代码在这些给定形状下的行为；不能推出真实
Qwen tokenizer 发生该 split、真实语义失效率或完整模型 accuracy。
闭 gate 恒等是结构事实，不证明 gate 能识别撤回、信任或错误。
直接残差输出与随后替换 cache 可同时成立，不构成论文内部矛盾。
保持原始 RoPE 位置可与裁剪后的 physical cache 长度不同，不预设其为错误。

## 修订顺序

- 初次 source acquisition 受环境网络限制，尚无官方 checkout。那时写下 H1–H5 的论文
  问题，并运行了自造 policy 的 harness；该 harness 没有提供上游实现证据。
- 取得固定公开 checkout 后，退役通用 AST harness、自造 first/longest policy、其 tests 和
  checksum 清单。新的 runner 直接执行官方类。原来“等长时自行抛错”的规则作废；只记录
  官方严格 `>` 比较下取最早候选的实际行为，不把 paper 未规定 tie 当成缺陷。
- 保留判定从非空子串改成 fixture 显式声明的完整词素 / 完整内容。library、training 与
  evaluation 默认值分别报告，未建立 current source 与论文实验配置的身份对应。
- Source-bound 初轮之后，复核发现 NHTSA→NHT 的原 control 只保留一个指定片段，不能
  支撑“语义角色仍完整”的说法。将 F4 改为 `not `→[`not`, ` `]，直接与 F1 的
  ` not`→[` `, `not`] 配对；随后重新执行整个 source audit 和相关 tests。

被退役的 harness 与 policy 结论不属于最终 evidence；本文件保留其被修正的原因，
不保留一个仍可误调用的旧 runner。
