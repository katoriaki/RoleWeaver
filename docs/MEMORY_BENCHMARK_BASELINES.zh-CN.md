# LLM 记忆系统公开基线与 RoleWeaver 评测路线

更新时间：2026-05-01

## 1. 结论先行

如果目标是“超过就有论文潜力”，不能只跑自建小测试。需要在公开 benchmark 上同时超过至少两类强基线：

- 传统基线：recency、BM25/lexical、embedding RAG、raw-dialogue RAG；
- 长上下文基线：把历史直接塞进长上下文；
- 记忆系统基线：MemoryBank/MemGPT/MemoryOS/A-Mem-like；
- 商业或强闭源模型结果：若论文已有报告，可以作为参考上界或对照；
- 消融：证明不是单个 prompt、单个 reranker 或单个数据清洗技巧带来的收益。

## 2. 值得优先对齐的公开 benchmark

| 优先级 | Benchmark | 类型 | 为什么重要 | RoleWeaver 对齐点 |
| --- | --- | --- | --- | --- |
| S | [LongMemEval, ICLR 2025](https://web.cs.ucla.edu/~kwchang/bibliography/wu2025longmemeval/) | 长期交互记忆 | 明确评测 information extraction、multi-session reasoning、temporal reasoning、knowledge updates、abstention；包含 500 个问题，并指出商业/长上下文系统在持续交互记忆上明显掉点。 | 我们的上下文预算、矛盾更新、abstention、会话分解可直接对齐。 |
| S | [LoCoMo, ACL 2024](https://aclanthology.org/2024.acl-long.747/) | 超长期多会话对话 | 每个对话约 600 turns、16K tokens、最多 32 sessions，含 QA、事件摘要、多模态对话生成。 | 适合测试长期关系、时间因果、图片对话和角色稳定性。 |
| S | [MemoryAgentBench, ICLR 2026](https://github.com/HUST-AI-HYZ/MemoryAgentBench) | 增量多轮记忆 agent | 四项能力：accurate retrieval、test-time learning、long-range understanding、conflict resolution；评估 RAG、外部记忆和工具型 agent。 | 最接近 RoleWeaver 的“交互中持续积累和更新记忆”。 |
| A | [MemBench, ACL Findings 2025](https://arxiv.org/abs/2506.21605) | LLM agent 记忆能力 | 同时看 factual memory、reflective memory，以及 participation/observation 场景；指标包含 effectiveness、efficiency、capacity。 | 适合验证反思记忆和观察型记忆。 |
| A | [PERMA, arXiv 2026](https://arxiv.org/abs/2603.23231) | 个性化记忆/偏好演化 | 从事件驱动偏好、跨会话、跨领域和用户语言变体评测 persona consistency over time。 | 对 RoleWeaver 的关系状态、偏好演化、persona 稳定很关键。 |
| A | [PersonaMem-v2, arXiv 2025](https://arxiv.org/abs/2512.06688) | 隐式个性化 | 1000 个用户 persona、300+ 场景、20000+ 偏好、128K 上下文；论文报告 agentic memory 用 2K memory 取得强结果。 | 适合检验“少 token 的人类可读记忆”是否真的能超过长上下文。 |
| A | [Memora/FAMA, ACL Findings 2026](https://arxiv.org/abs/2604.20006) | 遗忘感知长期记忆 | 强调过期记忆惩罚，提出 FAMA，覆盖 remembering、reasoning、recommending。 | 与 RoleWeaver 的矛盾链、valid_until、status、遗忘曲线高度匹配。 |

## 3. 论文级对照实验矩阵

RoleWeaver 应至少提供以下系统版本：

| 系统 | 说明 | 目的 |
| --- | --- | --- |
| Recency | 最近 N 条记忆 | 最低基线，证明不是只靠近因。 |
| Lexical/BM25 | 词面检索 | 检查实体和显式事实召回。 |
| Embedding RAG | 向量检索原始对话或记忆 | 当前常见 baseline。 |
| Long-context | 直接塞历史 | 与长上下文模型比较 token 成本和准确率。 |
| RoleWeaver Memory OS | 分层记忆 + 图谱 + 矛盾链 + 反思 | 主系统。 |
| RoleWeaver minus Reflection | 去掉反思整理 | 证明反思的贡献。 |
| RoleWeaver minus Contradiction | 去掉矛盾链 | 证明更新/遗忘能力。 |
| RoleWeaver minus A-Mem Evolution | 去掉旧记忆演化 | 证明旧记忆重写/链接的贡献。 |
| RoleWeaver minus Persona Anchors | 去掉角色锚点 | 证明 persona 稳定贡献。 |

## 4. 已加入的内部 smoke benchmark

脚本：

```powershell
G\runtime\python.exe eval\memory_benchmark\run_memory_os_benchmark.py
```

当前结果：

```text
RoleWeaver Memory OS benchmark: 8/8 = 100.00%
```

覆盖项：

- 单事实召回；
- 知识更新与旧记忆 contradicted；
- A-Mem 式旧记忆演化；
- 无关问题 abstention；
- 角色 canon 不被聊天纠正覆盖；
- 低价值旧记忆降级；
- 检索后 use_count 强化；
- 反思摘要创建。

注意：这是离线确定性 smoke benchmark，主要防回归，不可当论文结果。

## 5. 下一步实现路线

1. LongMemEval adapter：把其历史切成 RoleWeaver session，查询时只给问题，比较答案准确率和 token 成本。
2. LoCoMo adapter：测试 QA、事件摘要、多模态问答；重点看时间因果和关系连续性。
3. MemoryAgentBench adapter：映射 accurate retrieval、test-time learning、long-range understanding、conflict resolution。
4. Memora/FAMA adapter：把 invalidated memories 映射到 `contradicted/stale/archived`，直接报告 FAMA。
5. PERMA/PersonaMem-v2 adapter：把偏好事件输入为长期互动，测试隐式偏好和跨领域干扰。
6. 统一报告：accuracy/F1、FAMA、abstention precision、token cost、latency、storage growth、LLM calls、错误类型。

## 6. 可投稿方向

一个较强的论文叙事可以是：

> RoleWeaver proposes a biologically inspired, layered and evolving memory system for role/persona agents, combining Memory OS style tiering, contradiction-aware forgetting, and A-Mem style memory evolution. It improves long-term personalized memory while preserving persona autonomy under cross-domain interaction.

最低证据要求：

- 至少两个公开 benchmark 显著优于 RAG 和 long-context；
- 至少一个个性化/遗忘 benchmark 优于现有 memory agent；
- 消融证明三件事：反思、矛盾遗忘、旧记忆演化各自有用；
- 长期角色实验证明不会因为专业问答退化成普通助手。

