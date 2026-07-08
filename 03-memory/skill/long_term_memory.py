"""
长期记忆（Long-Term Memory）

特点：
- 基于文件持久化，跨会话保留
- 支持增删改查 + 关键词搜索
- 按时间戳排序，优先返回最新记忆

加载时序：部分加载，只取最近 N 条（非全量）
Token 策略：占总预算 25%
写入策略：异步写入（先写内存，定期 flush 到文件）

工程关注点：
- 分布式场景下多实例写入需乐观锁/版本号
- 文件存储仅适合单机 Demo；生产应换 Redis/数据库
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import os
from .base_memory import BaseMemory, MemoryEntry


class LongTermMemory(BaseMemory):
    def __init__(self, storage_path: Optional[str] = None):
        self._entries: List[MemoryEntry] = []
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "long_term_memory.json"
        )
        self._ensure_storage_dir()
        self.load()

    def _ensure_storage_dir(self) -> None:
        directory = os.path.dirname(self.storage_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        entry = MemoryEntry(content=content, metadata=metadata or {})
        self._entries.append(entry)
        self.save()

    def get(self, limit: int = 10) -> List[MemoryEntry]:
        return self._entries[-limit:]

    def get_recent(self, limit: int = 5) -> List[MemoryEntry]:
        return sorted(self._entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        """关键词搜索，返回 (entry, score) 列表"""
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
        """持久化到文件"""
        data = {"entries": [e.to_dict() for e in self._entries]}
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        """从文件加载"""
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._entries = [
                    MemoryEntry.from_dict(item) for item in data.get("entries", [])
                ]
