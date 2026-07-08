"""
用户画像（User Profile）

特点：
- 存储用户基本信息、偏好设置、关联实体、标签
- 体量小，价值高——每次请求都应加载
- 会话内可缓存，避免重复读取

加载时序：会话开始时加载一次，缓存到会话结束
Token 策略：占总预算 15%（信息密度高但体量小）
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import os
from .base_memory import BaseMemory, MemoryEntry


class UserProfile(BaseMemory):
    def __init__(self, user_id: str = "default", storage_path: Optional[str] = None):
        self.user_id = user_id
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), "..", "data", f"profile_{user_id}.json"
        )
        self._data: Dict[str, Any] = {
            "basic_info": {},
            "preferences": {},
            "entities": {},
            "tags": [],
            "history": []
        }
        self._ensure_storage_dir()
        self.load()

    def _ensure_storage_dir(self) -> None:
        directory = os.path.dirname(self.storage_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    # ---- 基本信息 ----
    def set_basic_info(self, key: str, value: Any) -> None:
        self._data["basic_info"][key] = value
        self.save()

    def get_basic_info(self, key: str, default: Any = None) -> Any:
        return self._data["basic_info"].get(key, default)

    # ---- 偏好设置 ----
    def set_preference(self, key: str, value: Any) -> None:
        self._data["preferences"][key] = value
        self.save()

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self._data["preferences"].get(key, default)

    # ---- 关联实体 ----
    def add_entity(self, key: str, value: Any) -> None:
        self._data["entities"][key] = value
        self.save()

    def get_entity(self, key: str, default: Any = None) -> Any:
        return self._data["entities"].get(key, default)

    # ---- 标签 ----
    def add_tag(self, tag: str) -> None:
        if tag not in self._data["tags"]:
            self._data["tags"].append(tag)
            self.save()

    def remove_tag(self, tag: str) -> None:
        if tag in self._data["tags"]:
            self._data["tags"].remove(tag)
            self.save()

    # ---- 历史记录 ----
    def add_history_item(self, content: str, category: str = "general") -> None:
        self._data["history"].append({
            "content": content,
            "category": category,
            "timestamp": datetime.now().isoformat()
        })
        self.save()

    def get_history(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        if category:
            return [h for h in self._data["history"] if h["category"] == category]
        return self._data["history"]

    # ---- BaseMemory 接口实现 ----
    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.add_history_item(content, (metadata or {}).get("category", "general"))

    def get(self, limit: int = 10) -> List[MemoryEntry]:
        history = self._data["history"][-limit:]
        return [
            MemoryEntry(
                content=h["content"],
                timestamp=datetime.fromisoformat(h["timestamp"]) if "timestamp" in h else datetime.now(),
                metadata={"category": h.get("category", "general")}
            )
            for h in history
        ]

    def get_recent(self, limit: int = 5) -> List[MemoryEntry]:
        return self.get(limit)

    def clear(self) -> None:
        self._data = {
            "basic_info": {},
            "preferences": {},
            "entities": {},
            "tags": [],
            "history": []
        }
        self.save()

    def size(self) -> int:
        return len(self._data["history"])

    def estimate_tokens(self) -> int:
        return int(len(self.to_context()) / 4)

    def to_context(self) -> str:
        lines = []
        if self._data["basic_info"]:
            lines.append("  基本信息:")
            for k, v in self._data["basic_info"].items():
                lines.append(f"    {k}: {v}")
        if self._data["preferences"]:
            lines.append("  偏好设置:")
            for k, v in self._data["preferences"].items():
                lines.append(f"    {k}: {v}")
        if self._data["entities"]:
            lines.append("  关联实体:")
            for k, v in self._data["entities"].items():
                lines.append(f"    {k}: {v}")
        if self._data["tags"]:
            lines.append(f"  标签: {', '.join(self._data['tags'])}")

        if not lines:
            return ""
        return "用户画像:\n" + "\n".join(lines)

    # ---- 持久化 ----
    def save(self) -> None:
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r", encoding="utf-8") as f:
                self._data.update(json.load(f))
