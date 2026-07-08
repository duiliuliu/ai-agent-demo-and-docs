"""
短期记忆（Short-Term Memory）

特点：
- 基于内存，读写极快
- 滑动窗口：超过 max_entries 或 max_tokens 自动驱逐最旧条目
- 每轮对话后追加 user/assistant 消息
- 永远全量加载到 Prompt（受 Token 限制保护）

加载时序：每轮请求都加载，优先级最高
Token 策略：占总预算 50%（当前对话上下文最关键）
"""
from typing import Dict, Any, List, Optional
from collections import deque
from .base_memory import BaseMemory, MemoryEntry


class ShortTermMemory(BaseMemory):
    def __init__(self, max_entries: int = 20, max_tokens: int = 2000):
        self._entries: deque = deque(maxlen=max_entries)
        self._max_entries = max_entries
        self._max_tokens = max_tokens

    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        meta = metadata or {}
        entry = MemoryEntry(content=content, metadata=meta)
        self._entries.append(entry)
        self._evict_by_tokens()

    def add_message(self, role: str, content: str) -> None:
        """便捷方法：添加对话消息"""
        self.add(content, {"role": role})

    def _evict_by_tokens(self) -> None:
        """按 Token 限制驱逐最旧条目"""
        while self.estimate_tokens() > self._max_tokens and len(self._entries) > 1:
            self._entries.popleft()

    def get(self, limit: int = 10) -> List[MemoryEntry]:
        entries = list(self._entries)
        return entries[-limit:] if limit < len(entries) else entries

    def get_recent(self, limit: int = 5) -> List[MemoryEntry]:
        return list(self._entries)[-limit:]

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """获取 OpenAI 格式的对话历史"""
        result = []
        for entry in self._entries:
            role = entry.metadata.get("role", "user")
            result.append({"role": role, "content": entry.content})
        return result

    def clear(self) -> None:
        self._entries.clear()

    def size(self) -> int:
        return len(self._entries)

    def estimate_tokens(self) -> int:
        total_chars = sum(len(e.content) for e in self._entries)
        return int(total_chars / 4)

    def to_context(self) -> str:
        if not self._entries:
            return ""
        lines = []
        for entry in self._entries:
            role = entry.metadata.get("role", "user")
            lines.append(f"{role}: {entry.content}")
        return "\n".join(lines)

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def max_tokens(self) -> int:
        return self._max_tokens
