# Recent sources: verified identity, reading depth and bounded use

Accessed 13 November 2026. These notes keep author results separate from AMS's reasoning. Full abstracts are not copied. Search snippets were used for discovery; technical claims below use the primary texts or pinned source files.

## 1. What Is This Memory Useful For?

- Authors: Chih-Hsuan Yang, Anjir Ahmed Chowdhury, Feng Yan, Rajeev Thakur.
- Version: [arXiv:2611.03930v1](https://arxiv.org/html/2611.03930v1), submitted 2 November 2026.
- Read: main protocol/results/limitations, S1 screening and writer controls, S3 noise/additive-null discussion, S4 length controls, release documentation, relevant official execution/analysis code. Do not claim every supplement paragraph was closely read.
- Code: [pinned repository](https://github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory/tree/386ac65a8b5fc46414abdd2755375f2a52d4d3b8).
- Dataset: [HF revision](https://huggingface.co/datasets/AgentsSci/AAMAS2027-ConditionalMemory/tree/332cd047e9093a948606c4251bf5b294b0664762).

**Bounded source capsule.** A query-blind writer and frozen single-call reader permit paired exposure measurements with identical filler. Gold-dependent screening selects an answer-bearing measurement population; it is not a deployable retriever. Main support concerns factual recall. The tested procedural-style structured writer often loses answer-bearing details. No length-matched irrelevant placebo isolates semantic content in the primary design. Coding results do not establish useful procedural transfer. The author already distinguishes opportunity-conditioned harm, sign flips and interaction. Public code subsequently exposes reproducibility coverage and a fixed-context cache defect; affected cells are excluded in the headline. This commission independently reran the published analyses rather than treating the README as execution evidence.

**AMS consequence.** Exposure utility needs a future-task model and exposure policy before it can become retention value. Fixed-context padding also leaves the opportunity cost of the freed context unspecified. These are interpretation gaps, not evidence that the measured contrast is wrong.

**Source audit locator.** At the pinned commit, `src/p1mem/memory/representations.py::_LLMWriter._call` renders only the source segment; `scripts/r1_write_representations.py` invokes the blind-signature check and `scripts/x2_fixed_context.py` consumes existing representations. Signature checks and prompt loading were executed without calling a model. Saved prompt versions match the source loader's normalised hashes. All 2,216 fixed-context rows nevertheless record original inference `code_sha="unknown"`; source review cannot authenticate the original execution. The receipt preserves this distinction.

## 2. MemAgent: Learning to Manage Heterogeneous Memory Providers for LLM Agents

- Authors: Yongxian Wei, Yilin Zhao, Runxi Cheng, Xinrui Chen, Chun Yuan, Yaoru Wang, Jiahong Yan, Dian Li.
- Version: [arXiv:2609.32521v1](https://arxiv.org/html/2609.32521v1), submitted 26 September 2026.
- Read: §§3–5, equations 1–3, Tables 1–5, Appendix A.1–A.5, inference pipeline. Author repository [WalkerWorldPeace/MemAgent](https://github.com/WalkerWorldPeace/MemAgent) was located; implementation was **not independently executed or comprehensively audited**.

**Bounded source capsule.** A trained small router chooses among thirteen providers at task start, gates within-task summaries, and selects storage providers afterward. Content probes hide incompatible retrieval scores. The reported average is 75.7 versus 65.7 without memory, a **10.0 percentage-point** increase. Appendix A.2 discloses reuse of 53 GAIA L1 tasks for exploration/population and evaluation; 112 GAIA L2/L3 tasks and the other two benchmarks are held out. End rewards combine retrieval frequency and downstream success, not paired counterfactual benefit. Thus the full headline cannot be labelled entirely held-out transfer, and End supervision is a useful heuristic whose causal interpretation is limited. Author ablations support trained routing over random routing and broad concatenation, within this experimental setup.

**AMS consequence.** Name precisely what is learned: provider selection and storage routing, not an unrestricted ability to infer useful memories. The counterexample in `research-note.md` shows why reuse followed by success cannot alone identify a memory's contribution. This does not negate empirical policy improvement.

Reading locators: Eq. 2 (End reward), Appendix A.2 (exploration/evaluation split), Tables 1–5 (main results and ablations).

## 3. Learning to Remember: End-to-End Training of Memory Agents for Long-Context Reasoning

- Authors: Kehao Zhang, Shangtong Gui, Sheng Yang, Wei Chen, Yang Feng. **PDF spells Wei Chen; the Anthology metadata renders Chen Wei. Use the PDF as publication authority and record the discrepancy.**
- Publication: [EMNLP 2026 PDF](https://aclanthology.org/2026.emnlp-main.1299.pdf), pp. 29575–29599, October 2026, DOI `10.18653/2026.emnlp-main.1299`.
- Read: architecture/MDP, nested sampling and reward assignment, result and ablation tables, limitations, raw-retrieval tool specifications; selected appendices. Repository [ictnlp/unified-memory-agent](https://github.com/ictnlp/unified-memory-agent) was identified from the PDF, not executed.

**Bounded source capsule.** UMA trains one policy for query-agnostic CRUD maintenance and later QA. Each memory trajectory branches into a shared question set; average downstream QA outcome supervises memory sessions, with separate advantage normalisation for memory and question groups. It retains access to raw-context retrieval. At 16k, aggregate TTL/AR score is 75.86; removing raw retrieval gives 57.74. The paper explicitly limits Ledger-QA to synthetic state tracking and session-level reward attribution. Training a maintenance policy, improving QA tool use and retaining external information remain distinct mechanisms. The “MemAgent” baseline here is a recurrent-compression method, not Wei et al.'s heterogeneous-provider paper above.

**AMS consequence.** Test which information survives and which controller was trained separately. A shared reward is a learning signal; individual CRUD contribution still needs a finer intervention. Open-world personal memory cannot inherit guarantees from transparent ledger rules.

Reading locators: nested trajectory sampling and reward-assignment sections; main result and raw-context ablation tables; limitations; appendix specification of the raw-retrieval tool.

## 4. RoutePrism: Tracing Construction Order Effects in Agent Memory

- Authors: Dong Xu, Zhangfan Yang, Jiantao Wu, Shipeng Zhang, Zexuan Zhu, Jiangqiang Li, Jun Zhang, Junkai Ji.
- Version: [arXiv:2609.34160v1](https://arxiv.org/abs/2609.34160v1), submitted 28 September 2026. The complete [primary PDF](https://arxiv.org/pdf/2609.34160v1) was obtained and inspected: 55 pages, SHA-256 `b054634ad1ca82fcbdd0852643364e287aee6889c269e42a035791971f057f82`.
- Read: §§3.1–3.3, §§4.1–4.3 and limitations; Appendices A.4–A.5, B, F.2–F.3, I.10–I.12; selected compactor pseudocode and sensitivity tables. No RoutePrism official repository URL was identified in the inspected PDF. Its code and saved trace matrices were not executed or independently reanalysed.

**Bounded source capsule.** Task-preserving permutations keep record text, dates and within-record relations fixed. The primary screen retains 63 queries/29 users, but focal support restoration uses 33 queries/21 users: exactly one supporting record must be displaced, with four structurally matched conditions. Support audit uses gold but not generated answers. Present, absent, restored and same-pool nonsupport replacement prompts match question, source count, serialization and token length. Luna's restored-minus-absent effect is +0.671; restored-minus-replacement is +0.601 (Table 3). These are conditional intervention effects, not whole-population harm prevalence. A controlled last-arrival compactor localizes changes mainly to survivor selection. Appendix A.5 identifies excess cross-route disagreement as half the squared distance between answer distributions. Qwen's focal restored-minus-replacement interval includes zero; the paper does not establish uniformly strong recovery across all readers.

**AMS consequence.** Preserve event chronology separately from processing order, as the eligibility rule already does. Changing source identity, compiled text, answer distribution and correctness are distinct outcomes. Reversal's direction in a last-arrival policy depends on support position; it is not a general recommendation to build memory backward. Source/answer changes alone do not measure usefulness.

**Internal numerical inconsistency.** Section 4.6 says Qwen's focal restored-minus-absent interval includes zero, while Table 49 gives `[0.071,0.381]`. Table 49's focal restored-minus-replacement interval is `[-0.071,0.341]`, consistent with §4.2. Use the explicitly tabulated contrast and do not silently turn this into a five-model uniform-significance claim.

## Discovery leads not promoted to evidence

- *When to Remember, When to Abstain: Category-Conditioned Retention for Reliable Agent Memory*, [arXiv:2610.07100](https://arxiv.org/abs/2610.07100): identified as an adjacent write-boundary retention study. Its full text is available; this package does not report an independent analysis of its threshold claims. See the main AMS synthesis for the separate reading.
- *EvoMemEval*, [OpenReview n3GMbobXnc](https://openreview.net/forum?id=n3GMbobXnc): located in the Utility bibliography. Not independently read or audited for this package; its purported harm prevalence is not used as an established observation.

## Suggested integration with existing AMS

`study/entries/conditional-information-and-use.md` can gain the narrower distinction between fixed-length padding and the opportunity cost of reallocating saved context. `study/entries/experience-becomes-policy.md` can distinguish success-based routing supervision from counterfactual attribution, then reference the MemAgent split disclosure and UMA's session-level reward. This package's public-output reanalysis belongs in the existing canonical research path, without copying upstream text or creating a new research registry.
