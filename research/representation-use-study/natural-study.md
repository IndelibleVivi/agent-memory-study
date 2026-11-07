# 模型生成的范围记忆：运行与核对

本研究使用原创合成历史，比较完整原文、question-blind 普通文字记忆和条件／修订记录。
writer 与 reader 分开调用。研究问题、材料、评分及 reader 前的一次长度政策修订见
[冻结协议](natural-protocol.md)；[原创历史和 gold](natural-cases.json)可独立检查。
原 [scripted/oracle controls](README.md) 与其 `sample-results.json` 保持原义。

`natural.py` 拥有输入 projection、评分、source identity 与已保存汇总检查；
`natural_api.py` 是官方 Responses API 的显式执行入口及离线 raw replay；
`natural-cases.json` 是原创材料／gold 真源。没有检索器、训练或浏览器端 inference。
writer 看不到问题、选项或 gold，reader 每次只收到一个任务和一种实际记忆。

## 离线验证

```bash
python3 -B -m unittest discover -s research/representation-use-study -p 'test_*.py'
python3 -B research/representation-use-study/natural.py check-saved
python3 -B research/representation-use-study/natural_probe.py check-saved
python3 -B research/representation-use-study/natural_facts.py check-saved
python3 -B tools/verify_reader.py
```

这些命令不调用 API。`check-saved` 校验当前 source identity、case/gold 定位、分母与配对
计数，不能替代原始响应重放。原始运行文件必须留在 repo 外。

## 另行授权的真实调用

下面是可复跑入口，会向官方 OpenAI 发送这里的原创合成文本并消耗 API credits。
操作者从自己的安全运行环境提供 `OPENAI_API_KEY`；不要把 key、`.env` 或 raw responses
放入 Git。模型、输出上限、标准服务层和 USD 10 预算写在源码／协议中。预算检查使用
官方 input-token counting 与最大输出额度预留，usage 估价不是账单或账户余额。

```bash
python3 -B research/representation-use-study/natural.py prepare --output /path/outside/repo/run-01
python3 -B research/representation-use-study/natural_api.py writers --run /path/outside/repo/run-01
python3 -B research/representation-use-study/natural_api.py readers --run /path/outside/repo/run-01
python3 -B research/representation-use-study/natural_api.py replay \
  --run /path/outside/repo/run-01 --output /path/outside/repo/replay.json
```

正式文件独占、原子发布，不覆盖；同时只能有一个 executor。已有成功请求跳过，已写 request
却没有 response 的请求视为 outcome unknown，不自动重复扣费。HTTP 错误、incomplete 或
无效格式保留原响应，不自动重试。token counting 失败会阻止该阶段 generation。
若进程崩溃留下 lock，先确认原进程已结束、检查已启动请求和缺失 receipts，再由操作者
处理 stale lock；不要仅因等待变长就重启。已正式发布的损坏文件必须拒绝。

source／protocol／corpus 变化需要新 run。首次研究在 writer 完成、reader 尚未启动时
调整了长度处理：所有原 writer 输入及输出完整继承，不重新抽样。该精确情形可用：

```bash
python3 -B research/representation-use-study/natural_api.py inherit-writers \
  --run /path/outside/repo/original-writer-run --output /path/outside/repo/amended-run
```

入口要求 corpus 和实际 writer／canary requests 完全相同、所有 writer 均有 receipt、
原 run 没有 reader request；将全部记录和来源 manifest 绑定到新 run，不挑选成功输出。
这不是任意跨版本复用权限；改变 writer 提示或语料须重新生成。

## 结果的阅读边界

公开 [natural-results.json](natural-results.json) 是离线 replay 的紧凑投影，逐组给出
正确数、有效输出数、按历史／题型分解、错误定位与配对增减。原始文本响应不入 Git。
按 kind 单列的 clarification controls 有些直接指出缺失字段，不能据此证明记忆保留。
长度服从性与回答质量分别报告；共享一次 writer 的两个 reader 不是独立 writer 复现。
完整结果解释见[研究正文](../../study/entries/scope-memory-after-revision.md)。

主实验出现ceiling与选项线索之后，又加入[事后question-only诊断](natural-question-only.md)，
其 [144次调用汇总](natural-question-only-results.json)独立于主结果。`natural_probe.py` 的
`prepare --parent /path/to/primary --output /path/to/new-control` 绑定已完成主run；随后
`run --run /path/to/new-control` 才显式调用API，`replay --run ... --output ...`离线重放。
它只移除memory，保留原问题及选项，主run已有最大费用预留计入同一USD10上限。

该诊断暴露题目线索后，另有[去选项线索的范围／事实任务](natural-facts-protocol.md)，
在同12段历史、同24份writer输出上固定24个新任务，比较raw/prose/ledger/none。
`natural_facts.py prepare --parent /path/to/primary --budget-parent /path/to/question-only
--output /path/to/new-facts`绑定既有证据和所有已花费阶段的最大预留；`run --run ...`
显式调用API，`replay --run ... --output ...`离线评分。问题、答案schema与gold由
[natural-facts.json](natural-facts.json)拥有，格式化答案和聚合保存在
[natural-facts-results.json](natural-facts-results.json)。集合不计顺序但拒绝重复；null
只在gold确实未定时正确，其余暂缓与非null错误分别计数。它是事后设计修正，不能改称
未见历史、额外独立families或预注册复现。
