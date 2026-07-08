"""
记忆管理器（Memory Manager）

核心职责：统一管理四种记忆组件，协调读写和转换

关键功能：
- 统一接口：add_short_term / add_long_term / add_profile 等
- 短期→长期转换：会话结束时将短期记忆摘要后写入长期
- 记忆更新覆盖：update / delete 操作同步到向量索引
- Token 统计：提供各类记忆的 Token 消耗概览

工程关注点：
- 短期→长期转换时需做摘要压缩，不能直接搬运
- 向量索引需与长期记忆保持同步（增删改时同步更新）
- 多用户场景下需按 user_id 隔离所有记忆
"""
from typing import Dict, Any, List, Optional
from .short_term_memory import ShortTermMemory
from .long_term_memory import LongTermMemory
from .user_profile import UserProfile
from .vector_memory import VectorMemory


class MemoryManager:
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.short_term = ShortTermMemory(max_segments=5, max_tokens_per_segment=2000)
        self.long_term = LongTermMemory()
        self.user_profile = UserProfile(user_id)
        self.vector_memory = VectorMemory()

    # ---- 写入操作 ----
    def add_short_term(self, content: str, role: str = "user") -> None:
        self.short_term.add_message(role, content)

    def add_long_term(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """写入长期记忆，同时写入向量索引"""
        self.long_term.add(content, metadata)
        self.vector_memory.add(content, metadata)

    def set_profile(self, key: str, value: Any, category: str = "basic_info") -> None:
        if category == "basic_info":
            self.user_profile.set_basic_info(key, value)
        elif category == "preferences":
            self.user_profile.set_preference(key, value)
        elif category == "entities":
            self.user_profile.add_entity(key, value)
        elif category == "tags":
            self.user_profile.add_tag(value)

    # ---- 读取操作 ----
    def get_short_term_context(self) -> str:
        return self.short_term.to_context()

    def get_long_term_context(self, limit: int = 5) -> str:
        return self.long_term.to_context(limit)

    def get_profile_context(self) -> str:
        return self.user_profile.to_context()

    def search_vector(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        results = self.vector_memory.search(query, top_k)
        return [
            {"content": e.content, "score": round(s, 4), "metadata": e.metadata}
            for e, s in results
        ]

    def search_long_term(self, keyword: str) -> List[Dict[str, Any]]:
        results = self.long_term.search(keyword)
        return [{"content": e.content, "metadata": e.metadata} for e, _ in results]

    # ---- 更新/删除（同步向量索引） ----
    def update_long_term(self, index: int, content: str) -> bool:
        if self.long_term.update_entry(index, content):
            self.vector_memory.update_entry(index, content)
            return True
        return False

    def delete_long_term(self, index: int) -> bool:
        if self.long_term.delete_entry(index):
            self.vector_memory.delete_entry(index)
            return True
        return False

    # ---- 短期→长期转换 ----
    def commit_short_to_long(self, min_tokens: int = 200) -> int:
        """
        将短期记忆提交到长期记忆
        当短期记忆 Token 数超过 min_tokens 时触发
        返回提交的条目数
        """
        if self.short_term.estimate_tokens() < min_tokens:
            return 0

        entries = self.short_term.get()
        count = 0
        for entry in entries:
            role = entry.metadata.get("role", "user")
            content = f"[{role}] {entry.content}"
            self.long_term.add(content, {"role": role})
            self.vector_memory.add(content, {"role": role})
            count += 1

        self.short_term.clear()
        return count

    # ---- Token 统计 ----
    def get_token_summary(self) -> Dict[str, Any]:
        return {
            "short_term": {
                "entries": self.short_term.size(),
                "tokens": self.short_term.estimate_tokens()
            },
            "long_term": {
                "entries": self.long_term.size(),
                "tokens": self.long_term.estimate_tokens()
            },
            "user_profile": {
                "tokens": self.user_profile.estimate_tokens()
            },
            "vector_memory": {
                "entries": self.vector_memory.size(),
                "tokens": self.vector_memory.estimate_tokens()
            }
        }

    # ---- 清理 ----
    def clear_short_term(self) -> None:
        self.short_term.clear()

    def clear_all(self) -> None:
        self.short_term.clear()
        self.long_term.clear()
        self.user_profile.clear()
        self.vector_memory.clear()
