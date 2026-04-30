# RoleWeaver Memory OS Benchmark

这是 RoleWeaver 记忆系统的内部 smoke benchmark，用来防止 Memory OS、矛盾链、遗忘、反思和 A-Mem 式旧记忆演化在开发中回归。

运行：

```powershell
G\runtime\python.exe eval\memory_benchmark\run_memory_os_benchmark.py
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

