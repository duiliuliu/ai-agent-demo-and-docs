"""
长期记忆（Long-Term Memory）- 集成压缩器版

在原版基础上集成 MemoryCompressor：
  - add() 时先过压缩器决策（SKIP/MERGE/REPLACE/APPEND）
  - 自动去重、合并、覆盖
  - 同时同步向量索引

加载时序：部分加载，只取最近 N 条（非全量）
Token 策略：占总预算 25%
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import os
from .base_memory import BaseMemory, MemoryEntry
from .memory_compressor import MemoryCompressor, CompressAction


class LongTermMemory(BaseMemory):
    def __init__(
        self,
        storage_path: Optional[str] = None,
        compressor: Optional[MemoryCompressor] = None
    ):
        self._entries: List[MemoryEntry] = []
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "long_term_memory.json"
        )
        self.compressor = compressor or MemoryCompressor()
        self._ensure_storage_dir()
        self.load()

    def _ensure_storage_dir(self) -> None:
        directory = os.path.dirname(self.storage_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        添加记忆（带压缩决策）

        返回：(是否真正入库, 决策原因)
        """
        existing = [(i, e.content) for i, e in enumerate(self._entries)]
        result = self.compressor.compress(content, existing)

        if result.action == CompressAction.SKIP:
            return (False, result.reason)

        if result.action == CompressAction.APPEND:
            entry = MemoryEntry(content=result.final_content, metadata=metadata or {})
            self._entries.append(entry)
            self.save()
            return (True, result.reason)

        if result.action == CompressAction.MERGE:
            idx = result.target_index
            if idx is not None and 0 <= idx < len(self._entries):
                self._entries[idx].content = result.final_content
                self._entries[idx].timestamp = datetime.now()
                if metadata:
                    self._entries[idx].metadata.update(metadata)
                self.save()
                return (True, result.reason)

        if result.action == CompressAction.REPLACE:
            idx = result.target_index
            if idx is not None and 0 <= idx < len(self._entries):
                self._entries[idx].content = result.final_content
                self._entries[idx].timestamp = datetime.now()
                if metadata:
                    self._entries[idx].metadata = metadata
                self.save()
                return (True, result.reason)

        return (False, "未匹配的 action")

    def force_add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """绕过压缩器直接添加（用于已确认要入库的内容）"""
        entry = MemoryEntry(content=content, metadata=metadata or {})
        self._entries.append(entry)
        self.save()

    def get(self, limit: int = 10) -> List[MemoryEntry]:
        return self._entries[-limit:]

    def get_recent(self, limit: int = 5) -> List[MemoryEntry]:
        return sorted(self._entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        results = []
        query_lower = query.lower()
        for entry in self._entries:
            if query_lower in entry.content.lower():
                score = entry.content.lower().count(query_lower)
                results.append((entry, float(score)))
        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def update_entry(self, index: int, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        if 0 <= index < len(self._entries):
            self._entries[index].content = content
            if metadata:
                self._entries[index].metadata = metadata
            self._entries[index].timestamp = datetime.now()
            self.save()
            return True
        return False

    def delete_entry(self, index: int) -> bool:
        if 0 <= index < len(self._entries):
            del self._entries[index]
            self.save()
            return True
        return False

    def clear(self) -> None:
        self._entries = []
        self.save()

    def size(self) -> int:
        return len(self._entries)

    def estimate_tokens(self) -> int:
        total_chars = sum(len(e.content) for e in self._entries)
        return int(total_chars / 4)

    def to_context(self, limit: int = 5) -> str:
        entries = self.get_recent(limit)
        if not entries:
            return ""
        lines = []
        for entry in entries:
            ts = entry.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] {entry.content}")
        return "\n".join(lines)

    def save(self) -> None:
        data = {"entries": [e.to_dict() for e in self._entries]}
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._entries = [
                    MemoryEntry.from_dict(item) for item in data.get("entries", [])
                ]
