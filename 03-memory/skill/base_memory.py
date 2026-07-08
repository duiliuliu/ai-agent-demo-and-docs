"""
记忆基类：定义所有记忆类型的统一接口。

设计原则：
- 统一 add/get/search 接口，便于 MemoryManager 统一调度
- 每种记忆自行管理存储和生命周期
- 提供 estimate_tokens() 供 Token 预算管理
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional


@dataclass
class MemoryEntry:
    """单条记忆条目"""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        ts = data.get("timestamp")
        if ts:
            try:
                timestamp = datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                timestamp = datetime.now()
        else:
            timestamp = datetime.now()
        return cls(
            content=data["content"],
            timestamp=timestamp,
            metadata=data.get("metadata", {})
        )


class BaseMemory(ABC):
    """所有记忆类型的抽象基类"""

    @abstractmethod
    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """添加一条记忆"""
        pass

    @abstractmethod
    def get(self, limit: int = 10) -> List[MemoryEntry]:
        """获取记忆列表"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空所有记忆"""
        pass

    @abstractmethod
    def size(self) -> int:
        """当前记忆条目数"""
        pass

    @abstractmethod
    def estimate_tokens(self) -> int:
        """估算当前记忆占用的 Token 数（近似: len(text)/4）"""
        pass

    @abstractmethod
    def to_context(self) -> str:
        """转换为可注入 Prompt 的上下文文本"""
        pass

    def get_recent(self, limit: int = 5) -> List[MemoryEntry]:
        """获取最近的 N 条记忆（默认实现）"""
        return self.get(limit)

    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        """搜索记忆，返回 (entry, score) 列表（默认实现：空）"""
        return []
