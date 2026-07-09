"""
上下文管理与快照模块（Context Manager）

设计目标：管理 Agent 单次运行的上下文生命周期，支持状态快照和恢复

核心问题：
  - 上下文随着循环进行不断增长，需要控制大小
  - 需要支持从任意步骤恢复执行
  - 需要支持上下文的版本管理和回滚
  - 多轮对话中，上下文需要与记忆模块交互

设计思想：
  - Context = 静态配置 + 动态状态 + 历史记录
  - 每次步骤后自动生成快照
  - 快照可序列化，支持持久化到磁盘/数据库
  - 支持上下文压缩（旧步骤摘要化）
"""
import json
import os
import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ContextSnapshot:
    snapshot_id: str
    step_id: int
    timestamp: str
    context: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "step_id": self.step_id,
            "timestamp": self.timestamp,
            "context": self.context,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextSnapshot":
        return cls(
            snapshot_id=data["snapshot_id"],
            step_id=data["step_id"],
            timestamp=data["timestamp"],
            context=data["context"],
            metadata=data.get("metadata", {})
        )


class ContextManager:
    def __init__(
        self,
        memory_store=None,
        max_history_length: int = 20,
        max_context_size_bytes: int = 1024 * 1024,
        auto_snapshot: bool = True,
        snapshot_dir: Optional[str] = None
    ):
        self.memory_store = memory_store
        self.max_history_length = max_history_length
        self.max_context_size_bytes = max_context_size_bytes
        self.auto_snapshot = auto_snapshot
        self.snapshot_dir = snapshot_dir or os.path.join(
            os.path.dirname(__file__), "..", "data", "contexts"
        )

        self._context: Dict[str, Any] = {}
        self._snapshots: Dict[str, ContextSnapshot] = {}
        self._session_id: Optional[str] = None

        self._ensure_snapshot_dir()

    def _ensure_snapshot_dir(self) -> None:
        if not os.path.exists(self.snapshot_dir):
            os.makedirs(self.snapshot_dir)

    def initialize(self, user_input: str, session_id: Optional[str] = None) -> None:
        self._session_id = session_id or f"ctx_{uuid.uuid4().hex[:12]}"
        self._context = {
            "session_id": self._session_id,
            "user_input": user_input,
            "history": [],
            "memory": {},
            "config": {},
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": 1
            }
        }
        self._snapshots = {}

        if self.auto_snapshot:
            self.save_snapshot(step_id=0)

        logger.debug(f"上下文已初始化: session={self._session_id}")

    def get_context(self) -> Dict[str, Any]:
        return self._context

    def update(self, key: str, value: Any) -> None:
        self._context[key] = value
        self._context["metadata"]["version"] = self._context["metadata"].get("version", 0) + 1

    def update_history(self, step: Dict[str, Any]) -> None:
        if "history" not in self._context:
            self._context["history"] = []

        self._context["history"].append(step)

        if len(self._context["history"]) > self.max_history_length:
            self._compress_history()

        self._context["metadata"]["version"] = self._context["metadata"].get("version", 0) + 1

    def _compress_history(self) -> None:
        if len(self._context["history"]) <= self.max_history_length:
            return

        keep_count = self.max_history_length // 2
        recent = self._context["history"][-keep_count:]

        older = self._context["history"][:-keep_count]
        summary = self._summarize_history(older)

        self._context["history"] = [
            {"type": "compressed_summary", "content": summary, "original_count": len(older)}
        ] + recent

        logger.debug(f"历史记录已压缩: {len(older)} → 1 条摘要")

    def _summarize_history(self, history: List[Dict[str, Any]]) -> str:
        summaries = []
        for step in history:
            thought = step.get("thought", "")[:50]
            action = step.get("action", {}).get("name", "unknown")
            summaries.append(f"步骤{step.get('step_id')}: {thought} → {action}")
        return "; ".join(summaries)

    def load_from_memory(self) -> None:
        if self.memory_store:
            try:
                memory_data = self.memory_store.retrieve(
                    self._context.get("user_input", ""),
                    limit=5
                )
                self._context["memory"] = {
                    "relevant_facts": memory_data.get("facts", []),
                    "previous_interactions": memory_data.get("interactions", [])
                }
                logger.debug(f"从记忆加载了 {len(self._context['memory'].get('relevant_facts', []))} 条事实")
            except Exception as e:
                logger.error(f"从记忆加载失败: {e}")

    def save_to_memory(self) -> None:
        if self.memory_store:
            try:
                key_points = self._extract_key_points()
                for point in key_points:
                    self.memory_store.store(point)
                logger.debug(f"保存了 {len(key_points)} 条关键点到记忆")
            except Exception as e:
                logger.error(f"保存到记忆失败: {e}")

    def _extract_key_points(self) -> List[str]:
        points = []
        for step in self._context.get("history", []):
            result = step.get("result", "")
            if isinstance(result, str) and len(result) > 10:
                points.append(result[:200])
        return points

    def save_snapshot(self, step_id: int, metadata: Optional[Dict[str, Any]] = None) -> str:
        snapshot = ContextSnapshot(
            snapshot_id=f"snapshot_{uuid.uuid4().hex[:8]}",
            step_id=step_id,
            timestamp=datetime.now().isoformat(),
            context=self._context.copy(),
            metadata=metadata or {}
        )

        self._snapshots[snapshot.snapshot_id] = snapshot

        if self.auto_snapshot:
            self._persist_snapshot(snapshot)

        logger.debug(f"快照已保存: {snapshot.snapshot_id} (step={step_id})")
        return snapshot.snapshot_id

    def _persist_snapshot(self, snapshot: ContextSnapshot) -> None:
        filename = f"{self._session_id}_{snapshot.snapshot_id}.json"
        path = os.path.join(self.snapshot_dir, filename)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"快照持久化失败: {e}")

    def load_snapshot(self, snapshot_id: str) -> bool:
        if snapshot_id in self._snapshots:
            snapshot = self._snapshots[snapshot_id]
            self._context = snapshot.context.copy()
            logger.debug(f"从内存加载快照: {snapshot_id}")
            return True

        filename = f"*{snapshot_id}.json"
        for f in os.listdir(self.snapshot_dir):
            if snapshot_id in f:
                path = os.path.join(self.snapshot_dir, f)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    snapshot = ContextSnapshot.from_dict(data)
                    self._context = snapshot.context.copy()
                    self._snapshots[snapshot_id] = snapshot
                    logger.debug(f"从磁盘加载快照: {snapshot_id}")
                    return True
                except Exception as e:
                    logger.error(f"加载快照失败: {e}")

        return False

    def get_snapshot_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "snapshot_id": s.snapshot_id,
                "step_id": s.step_id,
                "timestamp": s.timestamp,
                "version": s.context.get("metadata", {}).get("version", 0)
            }
            for s in self._snapshots.values()
        ]

    def validate_context(self) -> Dict[str, Any]:
        issues = []
        context_str = json.dumps(self._context)
        size_bytes = len(context_str.encode("utf-8"))

        if size_bytes > self.max_context_size_bytes:
            issues.append(f"上下文过大: {size_bytes / 1024:.1f}KB > {self.max_context_size_bytes / 1024:.1f}KB")

        if "user_input" not in self._context or not self._context["user_input"]:
            issues.append("缺少用户输入")

        if len(self._context.get("history", [])) == 0:
            issues.append("历史记录为空")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "size_bytes": size_bytes,
            "history_length": len(self._context.get("history", [])),
            "version": self._context.get("metadata", {}).get("version", 0)
        }

    def cleanup(self) -> None:
        self._context = {}
        self._snapshots = {}
        logger.debug("上下文已清理")


class EnhancedContextManager(ContextManager):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._on_update: List[Callable] = []

    def add_update_callback(self, callback: Callable) -> None:
        self._on_update.append(callback)

    def update(self, key: str, value: Any) -> None:
        old_value = self._context.get(key)
        super().update(key, value)

        for callback in self._on_update:
            try:
                callback(key=key, old_value=old_value, new_value=value)
            except Exception as e:
                logger.error(f"更新回调失败: {e}")

    def update_history(self, step: Dict[str, Any]) -> None:
        super().update_history(step)

        for callback in self._on_update:
            try:
                callback(key="history", old_value=None, new_value=step)
            except Exception as e:
                logger.error(f"历史更新回调失败: {e}")

    def get_context_summary(self) -> Dict[str, Any]:
        history = self._context.get("history", [])
        return {
            "session_id": self._session_id,
            "user_input": self._context.get("user_input", "")[:100],
            "total_steps": len(history),
            "last_step_time": history[-1].get("timestamp") if history else None,
            "context_size_bytes": len(json.dumps(self._context).encode("utf-8")),
            "memory_facts_count": len(self._context.get("memory", {}).get("relevant_facts", [])),
            "version": self._context.get("metadata", {}).get("version", 0)
        }
