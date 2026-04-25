# 记忆模块测试文档

测试日期：2026-04-24  
测试目录：`C:\Users\kator\Desktop\HMSZ`  
Python 环境：`C:\Users\kator\Desktop\HMSZ\.venv\Scripts\python.exe`

## 1. 测试目标

本轮测试聚焦于新的记忆运行时 `memory_runtime.py`，验证它是否已经具备以下基础能力：

- 短期记忆窗口是否正常保留最近对话
- 用户画像是否能从用户输入中提取并写入知识图谱，再以画像视图形式呈现
- 情节记忆是否能被存储、检索和重排
- 摘要缓冲是否会在窗口溢出后自动归档旧对话，并进入情节记忆
- 知识图谱是否具备预置角色知识和增量写入能力
- 调试命令是否能正确暴露当前记忆状态

## 2. 测试范围

本轮已测试文件：

- [memory_runtime.py](C:/Users/kator/Desktop/HMSZ/memory_runtime.py:1)
- [test_memory.py](C:/Users/kator/Desktop/HMSZ/test_memory.py:1)
- [tests/test_memory_runtime.py](C:/Users/kator/Desktop/HMSZ/tests/test_memory_runtime.py:1)

本轮没有直接测试大模型生成质量，只验证记忆系统本身的行为逻辑。

## 3. 测试方法

### 3.1 自动化回归测试

执行命令：

```powershell
& '.\.venv\Scripts\python.exe' -m unittest -v tests.test_memory_runtime
```

测试总数：6  
执行结果：全部通过

原始结果：

```text
test_commands_cover_profile_summary_and_knowledge ... ok
test_hybrid_long_term_search_finds_relevant_memory ... ok
test_knowledge_seed_and_context_rendering ... ok
test_profile_extraction_and_persistence ... ok
test_reranker_can_reorder_candidate_memories ... ok
test_summary_buffer_archives_old_turns ... ok

Ran 6 tests in 0.044s
OK
```

### 3.2 Smoke Check

执行了两项轻量检查：

```powershell
& '.\.venv\Scripts\python.exe' -m py_compile memory_runtime.py test_memory.py tests\test_memory_runtime.py
& '.\.venv\Scripts\python.exe' -c "import memory_runtime; print('memory_runtime import ok')"
```

结果：

- 语法编译通过
- `memory_runtime` 导入通过
- `HybridMemoryStore` 真实启动时已确认 `encoder=True / faiss_index=True / reranker=True`

## 4. 测试用例设计

### 用例 1：用户画像提取与持久化

输入示例：

- `我叫小林，你可以叫我阿林，我喜欢寿司，我现在在做记忆系统。`

验证点：

- `名字 / 称呼偏好 / 喜欢 / 项目` 四类画像都能提取
- 画像会被写入知识图谱中的 `制作人` 节点
- `/profile show` 能从图谱投影出画像视图
- 对应信息不会再冗余写入文本情节记忆

结果：通过

### 用例 2：摘要缓冲归档

设计方式：

- 连续写入 5 轮对话，让近期窗口超过上限

验证点：

- 旧对话会被压成摘要
- 摘要会进入 `state summaries`
- 摘要会同步写入情节记忆
- 最近对话窗口不会无限增长

结果：通过

### 用例 3：情节记忆混合检索

设计方式：

- 手动注入多条情节记忆
- 用“喜欢吃什么 / 烤肉”这类查询做召回

验证点：

- 相关情节记忆能被检索出来
- 最相关的“喜欢：烤肉套餐”排在最前面

结果：通过

### 用例 4：知识图谱预置知识与上下文构建

设计方式：

- 使用查询 `美铃生日`

验证点：

- 预置知识中能找到 `2月6日`
- `build_context()` 返回的上下文里包含角色知识段落
- 返回内容带有 `秦谷美铃的生日：2月6日`

结果：通过

### 用例 5：调试命令链路

设计方式：

- 先写入画像和多轮历史，再调用命令接口

验证点：

- `/profile show` 能输出用户画像
- `/summary show` 能输出历史摘要
- `/kg add` 能新增知识图谱事实
- `/kg search` 能查到新增事实
- `/ctx 查询词` 能输出最终注入上下文

结果：通过

### 用例 6：Reranker 精排重排能力

设计方式：

- 预先注入多条相近候选记忆
- 使用伪造 reranker 分数模拟交叉编码重排

验证点：

- reranker 能在候选集合内部改变最终排序
- 最终排序不是简单沿用粗召回顺序
- `_rerank_score` 和 `_final_score` 会反映精排结果

结果：通过

## 5. 当前结论

新的记忆运行时已经从原来的“聊天窗口 + 单一 FAISS 桶”升级成了一套更清晰的分层结构：

- Working memory：已实现
- 摘要缓冲并入 episodic memory：已实现
- 图谱真源的用户画像视图：已实现
- Episodic memory：已实现
- `Embedding + FAISS` 粗召回：已实现
- `BGE-Reranker` 精排：已实现
- 预置知识图谱：已实现
- 调试与观察命令：已实现

从行为测试结果看，这一版已经具备继续往下做产品化迭代的基础。

## 6. 当前未覆盖项

以下内容本轮没有纳入自动化验证：

- 真实大模型推理时的角色表现是否会正确利用这些记忆
- 向量 embedding 与 FAISS 在真实记忆数据规模下的召回率与延迟表现
- 长对话高轮次下的摘要质量是否会逐渐失真
- 用户画像抽取规则的误提取与冲突合并策略
- 知识图谱冲突事实、时间版本和可信度衰减
- 多用户隔离、会话隔离和跨会话记忆治理

说明：

为保证测试可重复、可快速执行，自动化用例中仍然会对 embedding/reranker 初始化做隔离，主要验证记忆逻辑和接口行为本身，不依赖外部模型下载状态。  
同时，本轮已额外补做真实 smoke check，确认在当前 `.venv` 环境下 `Embedding + FAISS + BGE-Reranker` 可以同时成功初始化。

## 7. 建议的下一轮测试

建议下一轮补三类测试：

- 集成测试：让 `test_memory.py` 走真实一轮推理，确认 prompt 注入后的模型输出确实会引用画像、摘要和长期记忆
- 污染测试：专门喂一些“临时情绪、闲聊噪声、反讽句子”，检查画像和长期记忆会不会误收录
- 检索测试：构造近义表达、口语表达、错别字表达，验证 `Embedding + FAISS` 粗召回和 BGE rerank 是否足够稳
