"""
实体画像（EntityProfile）- 泛化的主体画像

设计理念：
  实际的"主体"不只有"用户"，还有项目、产品、团队、场景等。
  这些主体的画像数据结构同构——都是"结构化事实集合"。
  因此抽象出 EntityProfile 统一处理，entity_type 区分主体类型。

支持的主体类型：
  - user    : 用户
  - project : 项目
  - product : 产品
  - team    : 团队
  - scene   : 场景
  - other   : 其他

数据结构（统一）：
  basic_info   : 基本信息（名称、ID、创建时间等不可变属性）
  attributes   : 属性（用户=性别年龄，项目=预算周期，产品=价格）
  preferences  : 偏好（用户=饮食偏好，项目=技术栈偏好）
  relations    : 关联关系（项目→用户、产品→团队）
  states       : 状态（项目=进行中、产品=已发布，支持过期）
  tags         : 标签集合
  history      : 操作历史（含时间戳和分类）
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import os
from .base_memory import BaseMemory, MemoryEntry


class EntityProfile(BaseMemory):
    ENTITY_TYPES = ["user", "project", "product", "team", "scene", "other"]

    def __init__(
        self,
        entity_id: str,
        entity_type: str = "user",
        storage_path: Optional[str] = None
    ):
        if entity_type not in self.ENTITY_TYPES:
            raise ValueError(f"entity_type 必须是 {self.ENTITY_TYPES} 之一")

        self.entity_id = entity_id
        self.entity_type = entity_type
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), "..", "data", f"entity_{entity_type}_{entity_id}.json"
        )
        self._data: Dict[str, Any] = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "basic_info": {},
            "attributes": {},
            "preferences": {},
            "relations": {},
            "states": {},
            "tags": [],
            "history": []
        }
        self._ensure_storage_dir()
        self.load()

    def _ensure_storage_dir(self) -> None:
        directory = os.path.dirname(self.storage_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    # ---- 基本信息（不可变或低频变更） ----
    def set_basic_info(self, key: str, value: Any) -> None:
        self._data["basic_info"][key] = value
        self.save()

    def get_basic_info(self, key: str, default: Any = None) -> Any:
        return self._data["basic_info"].get(key, default)

    # ---- 属性（实体特征） ----
    def set_attribute(self, key: str, value: Any) -> None:
        self._data["attributes"][key] = value
        self.save()

    def get_attribute(self, key: str, default: Any = None) -> Any:
        return self._data["attributes"].get(key, default)

    # ---- 偏好 ----
    def set_preference(self, key: str, value: Any) -> None:
        self._data["preferences"][key] = value
        self.save()

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self._data["preferences"].get(key, default)

    # ---- 关联关系（实体间） ----
    def add_relation(self, target_entity_id: str, relation_type: str, metadata: Optional[Dict] = None) -> None:
        if target_entity_id not in self._data["relations"]:
            self._data["relations"][target_entity_id] = []
        self._data["relations"][target_entity_id].append({
            "relation": relation_type,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat()
        })
        self.save()

    def get_relations(self, relation_type: Optional[str] = None) -> Dict[str, List[Dict]]:
        if relation_type is None:
            return self._data["relations"]
        return {
            k: v for k, v in self._data["relations"].items()
            if any(r["relation"] == relation_type for r in v)
        }

    # ---- 状态（支持过期） ----
    def set_state(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        state = {"value": value}
        if ttl_seconds:
            state["expires_at"] = (datetime.now().timestamp() + ttl_seconds)
        self._data["states"][key] = state
        self.save()

    def get_state(self, key: str, default: Any = None) -> Any:
        state = self._data["states"].get(key)
        if state is None:
            return default
        # 检查过期
        if "expires_at" in state and datetime.now().timestamp() > state["expires_at"]:
            del self._data["states"][key]
            self.save()
            return default
        return state["value"]

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
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "basic_info": {},
            "attributes": {},
            "preferences": {},
            "relations": {},
            "states": {},
            "tags": [],
            "history": []
        }
        self.save()

    def size(self) -> int:
        return len(self._data["history"])

    def estimate_tokens(self) -> int:
        return int(len(self.to_context()) / 4)

    def to_context(self) -> str:
        if self.entity_type == "user":
            return self._to_user_context()
        elif self.entity_type == "project":
            return self._to_project_context()
        elif self.entity_type == "product":
            return self._to_product_context()
        return self._to_generic_context()

    def _to_user_context(self) -> str:
        lines = ["用户画像:"]
        if self._data["basic_info"]:
            lines.append("  基本信息:")
            for k, v in self._data["basic_info"].items():
                lines.append(f"    {k}: {v}")
        if self._data["preferences"]:
            lines.append("  偏好:")
            for k, v in self._data["preferences"].items():
                lines.append(f"    {k}: {v}")
        if self._data["tags"]:
            lines.append(f"  标签: {', '.join(self._data['tags'])}")
        return "\n".join(lines)

    def _to_project_context(self) -> str:
        lines = [f"项目画像 [{self.entity_id}]:"]
        if self._data["basic_info"]:
            lines.append("  基本信息:")
            for k, v in self._data["basic_info"].items():
                lines.append(f"    {k}: {v}")
        if self._data["attributes"]:
            lines.append("  属性:")
            for k, v in self._data["attributes"].items():
                lines.append(f"    {k}: {v}")
        if self._data["states"]:
            active_states = {
                k: v["value"] for k, v in self._data["states"].items()
                if "expires_at" not in v or v["expires_at"] > datetime.now().timestamp()
            }
            if active_states:
                lines.append("  当前状态:")
                for k, v in active_states.items():
                    lines.append(f"    {k}: {v}")
        if self._data["relations"]:
            lines.append("  关联实体:")
            for entity_id, relations in self._data["relations"].items():
                rel_types = [r["relation"] for r in relations]
                lines.append(f"    {entity_id}: {', '.join(rel_types)}")
        if self._data["tags"]:
            lines.append(f"  标签: {', '.join(self._data['tags'])}")
        return "\n".join(lines)

    def _to_product_context(self) -> str:
        lines = [f"产品画像 [{self.entity_id}]:"]
        if self._data["basic_info"]:
            lines.append("  基本信息:")
            for k, v in self._data["basic_info"].items():
                lines.append(f"    {k}: {v}")
        if self._data["attributes"]:
            lines.append("  属性:")
            for k, v in self._data["attributes"].items():
                lines.append(f"    {k}: {v}")
        if self._data["states"]:
            lines.append("  状态:")
            for k, v in self._data["states"].items():
                lines.append(f"    {k}: {v.get('value', v) if isinstance(v, dict) else v}")
        return "\n".join(lines)

    def _to_generic_context(self) -> str:
        lines = [f"{self.entity_type}画像 [{self.entity_id}]:"]
        for section in ["basic_info", "attributes", "preferences", "states"]:
            data = self._data[section]
            if data:
                lines.append(f"  {section}:")
                for k, v in data.items():
                    value = v.get("value", v) if isinstance(v, dict) else v
                    lines.append(f"    {k}: {value}")
        if self._data["tags"]:
            lines.append(f"  标签: {', '.join(self._data['tags'])}")
        return "\n".join(lines)

    # ---- 持久化 ----
    def save(self) -> None:
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                self._data.update(loaded)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)


# 向后兼容：保留 UserProfile 别名
class UserProfile(EntityProfile):
    """用户画像 - EntityProfile 的 user 类型特化（向后兼容）"""
    def __init__(self, user_id: str = "default", storage_path: Optional[str] = None):
        super().__init__(user_id, "user", storage_path)
