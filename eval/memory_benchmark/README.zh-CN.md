# RoleWeaver Memory OS Benchmark

这是 RoleWeaver 记忆系统的内部 smoke benchmark，用来防止 Memory OS、矛盾链、遗忘、反思和 A-Mem 式旧记忆演化在开发中回归。

运行：

```powershell
python eval\memory_benchmark\run_memory_os_benchmark.py
```

当前覆盖：

- single_fact_retrieval
- knowledge_update_and_conflict_resolution
- amem_old_memory_evolution
- abstention_no_spurious_recall
- protected_character_canon
- forgetting_decay_low_value_memory
- retrieval_reinforcement
- reflection_summary_created

报告默认写入：

```text
eval/memory_benchmark/reports/latest.json
```

这个测试不加载 embedding/reranker，也不调用 LLM。它适合做快速工程回归，不适合直接作为论文结果。论文级评测请接入 LongMemEval、LoCoMo、MemoryAgentBench、MemBench、PERMA、PersonaMem-v2、Memora/FAMA 等公开基准。

报告版本 2 移除了狗名和当前饮品查询中的答案提示，固定了测试时钟，并让 recency 基线在时间戳相同时按递增插入 ID 的倒序取最近记录。报告保存这两个查询、时钟参数、检索模式、Python 版本与脚本/runtime 的 SHA-256。由于查询和排序规则变化，版本 1 与版本 2 的分数不能直接比较。

这是固定的小型合成用例集，检查返回的记忆 ID 和系统状态，不评估 LLM 最终答案。单条查询中的基线列表不能证明系统优于这些基线，也不能替代独立测试集、多个随机种子、人工评价或论文实验的完整复现。

