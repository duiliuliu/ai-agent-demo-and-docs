"""
向量化记忆（Vector Memory）

特点：
- 将文本向量化，通过相似度检索召回相关内容
- 本 Demo 使用词频向量 + 余弦相似度 + Jaccard 系数混合算法
- 中文按单字符分词（简单但有效），英文按单词分词

加载时序：按需加载——仅当用户输入有查询意图时才触发搜索
Token 策略：占总预算 10%（只注入 top-K 最相关结果）

工程关注点：
- TF-IDF 无法理解语义（"天气"和"气象"不匹配）
- 生产环境应替换为 Embedding 模型（如 text-embedding-3-small）
- 需配合 Rerank 提升召回精度
- 向量索引应使用专用数据库（FAISS/Milvus/Chroma）
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import os
import re
from collections import Counter
from .base_memory import BaseMemory, MemoryEntry


class VectorMemory(BaseMemory):
    def __init__(self, storage_path: Optional[str] = None):
        self._entries: List[MemoryEntry] = []
        self._vectors: Dict[int, Counter] = {}
        self._doc_freq: Dict[str, int] = {}
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "vector_memory.json"
        )
        self._ensure_storage_dir()
        self.load()

    def _ensure_storage_dir(self) -> None:
        directory = os.path.dirname(self.storage_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    def _tokenize(self, text: str) -> List[str]:
        """字符级分词：中文按单字，英文按单词"""
        text = text.lower()
        tokens = []
        i = 0
        while i < len(text):
            if '\u4e00' <= text[i] <= '\u9fa5':
                tokens.append(text[i])
                i += 1
            elif text[i].isalnum():
                j = i
                while j < len(text) and text[j].isalnum():
                    j += 1
                tokens.append(text[i:j])
                i = j
            else:
                i += 1
        return tokens

    def _compute_vector(self, text: str) -> Counter:
        return Counter(self._tokenize(text))

    def _update_doc_freq(self, text: str) -> None:
        for word in set(self._tokenize(text)):
            self._doc_freq[word] = self._doc_freq.get(word, 0) + 1

    def _cosine_similarity(self, vec1: Counter, vec2: Counter) -> float:
        common = set(vec1.keys()) & set(vec2.keys())
        if not common:
            return 0.0
        dot = sum(vec1[w] * vec2[w] for w in common)
        norm1 = sum(v * v for v in vec1.values()) ** 0.5
        norm2 = sum(v * v for v in vec2.values()) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def _jaccard_similarity(self, vec1: Counter, vec2: Counter) -> float:
        s1, s2 = set(vec1.keys()), set(vec2.keys())
        union = s1 | s2
        if not union:
            return 0.0
        return len(s1 & s2) / len(union)

    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        entry = MemoryEntry(content=content, metadata=metadata or {})
        idx = len(self._entries)
        self._entries.append(entry)
        self._update_doc_freq(content)
        self._vectors[idx] = self._compute_vector(content)
        self.save()

    def get(self, limit: int = 10) -> List[MemoryEntry]:
        return self._entries[-limit:]

    def get_recent(self, limit: int = 5) -> List[MemoryEntry]:
        return self._entries[-limit:]

    def search(self, query: str, top_k: int = 5) -> List[Tuple[MemoryEntry, float]]:
        """语义搜索：余弦相似度 60% + Jaccard 40%"""
        if not self._entries:
            return []
        query_vec = self._compute_vector(query)
        results = []
        for idx, entry in enumerate(self._entries):
            entry_vec = self._vectors.get(idx, Counter())
            cos = self._cosine_similarity(query_vec, entry_vec)
            jac = self._jaccard_similarity(query_vec, entry_vec)
            combined = 0.6 * cos + 0.4 * jac
            if combined > 0.05:
                results.append((entry, combined))
        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def update_entry(self, index: int, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        if 0 <= index < len(self._entries):
            old_tokens = set(self._tokenize(self._entries[index].content))
            for w in old_tokens:
                if self._doc_freq.get(w, 0) > 1:
                    self._doc_freq[w] -= 1
            self._entries[index].content = content
            self._entries[index].metadata = metadata or self._entries[index].metadata
            self._entries[index].timestamp = datetime.now()
            self._update_doc_freq(content)
            self._vectors[index] = self._compute_vector(content)
            self.save()
            return True
        return False

    def delete_entry(self, index: int) -> bool:
        if 0 <= index < len(self._entries):
            old_tokens = set(self._tokenize(self._entries[index].content))
            for w in old_tokens:
                if self._doc_freq.get(w, 0) > 1:
                    self._doc_freq[w] -= 1
            del self._entries[index]
            new_vectors = {}
            for i in range(len(self._entries)):
                old_idx = i + 1 if i >= index else i
                new_vectors[i] = self._vectors.get(old_idx, Counter())
            self._vectors = new_vectors
            self.save()
            return True
        return False

    def clear(self) -> None:
        self._entries = []
        self._vectors = {}
        self._doc_freq = {}
        self.save()

    def size(self) -> int:
        return len(self._entries)

    def estimate_tokens(self) -> int:
        return int(sum(len(e.content) for e in self._entries) / 4)

    def to_context(self) -> str:
        entries = self.get_recent(5)
        if not entries:
            return ""
        return "\n".join(f"- {e.content}" for e in entries)

    def save(self) -> None:
        data = {
            "entries": [e.to_dict() for e in self._entries],
            "vectors": {str(k): dict(v) for k, v in self._vectors.items()},
            "doc_freq": self._doc_freq
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = [MemoryEntry.from_dict(item) for item in data.get("entries", [])]
            self._vectors = {int(k): Counter(v) for k, v in data.get("vectors", {}).items()}
            self._doc_freq = data.get("doc_freq", {})
