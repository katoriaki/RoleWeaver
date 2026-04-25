import os
import json
import time
from typing import List, Dict, Optional

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


class FaissMemoryStore:
    def __init__(
        self,
        memory_file: str = "memories_v2.json",
        index_file: str = "memories_v2.faiss",
        embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ):
        self.memory_file = memory_file
        self.index_file = index_file
        self.embedding_model_name = embedding_model_name

        print(f"[Memory] 加载 embedding 模型: {embedding_model_name}")
        self.encoder = SentenceTransformer(embedding_model_name)

        self.memories: List[Dict] = self._load_memories()
        self.dimension = self._get_embedding_dimension()

        self.index = self._load_or_build_index()

    # ========= 基础加载 =========
    def _load_memories(self) -> List[Dict]:
        if not os.path.exists(self.memory_file):
            return []
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception:
            return []

    def _save_memories(self):
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.memories, f, ensure_ascii=False, indent=2)

    def _get_embedding_dimension(self) -> int:
        test_vec = self.encoder.encode(["test"], normalize_embeddings=True)
        return int(test_vec.shape[1])

    def _new_index(self):
        # 用内积；因为我们会先做 normalize，所以等价于 cosine similarity
        return faiss.IndexFlatIP(self.dimension)

    def _load_or_build_index(self):
        if os.path.exists(self.index_file):
            try:
                index = faiss.read_index(self.index_file)
                # 简单一致性检查
                if index.d != self.dimension:
                    print("[Memory] FAISS 维度不匹配，重建索引。")
                    return self._rebuild_index()
                return index
            except Exception:
                print("[Memory] 读取 FAISS 索引失败，重建索引。")
                return self._rebuild_index()
        else:
            return self._rebuild_index()

    def _save_index(self):
        faiss.write_index(self.index, self.index_file)

    def _rebuild_index(self):
        index = self._new_index()
        if self.memories:
            texts = [m["content"] for m in self.memories]
            vecs = self._encode_texts(texts)
            index.add(vecs)
        self.index = index
        self._save_index()
        return index

    # ========= 编码 =========
    def _encode_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        vecs = self.encoder.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vecs.astype("float32")

    def _encode_query(self, text: str) -> np.ndarray:
        vec = self.encoder.encode(
            [text],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vec.astype("float32")

    # ========= 对外接口 =========
    def list_memories(self) -> List[Dict]:
        return self.memories

    def add_memory(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        importance: int = 3,
        metadata: Optional[Dict] = None,
    ):
        if tags is None:
            tags = []
        if metadata is None:
            metadata = {}

        content = content.strip()
        if not content:
            return

        # 简单去重：内容完全相同就跳过
        for m in self.memories:
            if m["content"] == content:
                return

        memory = {
            "id": len(self.memories) + 1,
            "content": content,
            "tags": tags,
            "importance": int(importance),
            "timestamp": int(time.time()),
            "metadata": metadata,
        }
        self.memories.append(memory)
        self._save_memories()

        vec = self._encode_texts([content])
        self.index.add(vec)
        self._save_index()

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.30,
    ) -> List[Dict]:
        if not query.strip():
            return []
        if len(self.memories) == 0 or self.index.ntotal == 0:
            return []

        query_vec = self._encode_query(query)
        k = min(top_k, len(self.memories))
        scores, indices = self.index.search(query_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            if idx >= len(self.memories):
                continue
            if float(score) < min_score:
                continue

            memory = dict(self.memories[idx])
            memory["_score"] = float(score)

            # importance 做一个轻微重排
            memory["_rerank_score"] = float(score) + 0.03 * memory.get("importance", 3)
            results.append(memory)

        results.sort(key=lambda x: x["_rerank_score"], reverse=True)
        return results

    def delete_memory(self, memory_id: int):
        self.memories = [m for m in self.memories if m["id"] != memory_id]

        # 重新编号，避免 id 乱掉
        for i, m in enumerate(self.memories, start=1):
            m["id"] = i

        self._save_memories()
        self._rebuild_index()

    def clear_all(self):
        self.memories = []
        self._save_memories()
        self._rebuild_index()


def extract_candidate_memories(user_text: str, assistant_text: str = "") -> List[Dict]:
    """
    规则版候选记忆提取器：
    只提取“值得长期保存”的信息，避免记忆污染。
    """
    text = user_text.strip()
    candidates = []

    explicit_memory_patterns = ["记住", "别忘了", "以后都", "从现在开始"]
    if any(p in text for p in explicit_memory_patterns):
        candidates.append({
            "content": text,
            "tags": ["显式记忆"],
            "importance": 5
        })
        return candidates

    trigger_rules = [
        ("名字", ["我叫", "我的名字是", "你可以叫我"]),
        ("偏好", ["我喜欢", "我不喜欢", "我更喜欢", "我讨厌"]),
        ("身份", ["我是", "我现在是", "我是学生", "我是程序员"]),
        ("目标", ["我想", "我的目标是", "我准备", "我要考", "我要做"]),
        ("项目", ["我现在在做", "我的项目是", "我在训练", "我在微调", "我在做一个"]),
        ("关系", ["你要记住", "别忘了这个", "以后都这样"]),
    ]

    for tag, patterns in trigger_rules:
        for p in patterns:
            if p in text:
                candidates.append({
                    "content": text,
                    "tags": [tag],
                    "importance": 3
                })
                return candidates

    return candidates