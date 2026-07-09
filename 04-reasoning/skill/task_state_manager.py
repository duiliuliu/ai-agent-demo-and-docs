"""
任务状态管理与持久化（Task State Manager）

解决核心问题：ReAct 和 Plan-and-Solve 的长任务需要状态保存

场景：
  - 一个 Plan-and-Solve 任务执行到第3步，系统崩溃/重启了
  - 一个 ReAct 循环进行了5轮交互，用户暂时离开，30分钟后回来继续
  - 多实例部署时，任务可能在 A 实例启动，在 B 实例继续执行

设计思想：
  - 每个推理任务有一个唯一的 Task ID
  - 任务状态 = 元数据 + 当前步骤 + 历史步骤 + 上下文
  - 每次步骤执行后自动 checkpoint
  - 支持从 checkpoint 恢复（断点续执行）

状态机：
  PENDING → PLANNING → EXECUTING → VERIFYING → COMPLETED
    ↓          ↓          ↓            ↓
  CANCELLED  FAILED    FAILED      FAILED
"""
import json
import os
import time
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .base_reasoner import Step, ReasoningResult


class TaskStatus(Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class TaskCheckpoint:
    task_id: str
    status: TaskStatus
    current_step: int
    total_steps: int
    steps_history: List[Dict[str, Any]]
    context: Dict[str, Any]
    metadata: Dict[str, Any]
    error_info: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "steps_history": self.steps_history,
            "context": self.context,
            "metadata": self.metadata,
            "error_info": self.error_info
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskCheckpoint":
        return cls(
            task_id=data["task_id"],
            status=TaskStatus(data.get("status", "pending")),
            current_step=data.get("current_step", 0),
            total_steps=data.get("total_steps", 0),
            steps_history=data.get("steps_history", []),
            context=data.get("context", {}),
            metadata=data.get("metadata", {}),
            error_info=data.get("error_info")
        )


class TaskStateManager:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or os.path.join(
            os.path.dirname(__file__), "..", "data", "tasks"
        )
        self._ensure_storage_dir()
        self._memory_cache: Dict[str, TaskCheckpoint] = {}

    def _ensure_storage_dir(self) -> None:
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)

    def _checkpoint_path(self, task_id: str) -> str:
        return os.path.join(self.storage_dir, f"{task_id}.json")

    def create_task(
        self,
        user_input: str,
        reasoning_type: str,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None
    ) -> str:
        tid = task_id or f"task_{uuid.uuid4().hex[:12]}"
        checkpoint = TaskCheckpoint(
            task_id=tid,
            status=TaskStatus.PENDING,
            current_step=0,
            total_steps=0,
            steps_history=[],
            context={
                "user_input": user_input,
                "reasoning_type": reasoning_type,
                **(context or {})
            },
            metadata={
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "version": 1
            }
        )
        self._save_checkpoint(checkpoint)
        self._memory_cache[tid] = checkpoint
        return tid

    def start_task(self, task_id: str, total_steps: int = 0) -> bool:
        cp = self._load_checkpoint(task_id)
        if not cp:
            return False
        cp.status = TaskStatus.EXECUTING
        cp.total_steps = total_steps
        cp.metadata["updated_at"] = datetime.now().isoformat()
        cp.metadata["started_at"] = datetime.now().isoformat()
        self._save_checkpoint(cp)
        return True

    def save_step(
        self,
        task_id: str,
        step: Step,
        intermediate_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        cp = self._load_checkpoint(task_id)
        if not cp:
            return False

        cp.steps_history.append({
            "step_id": step.step_id,
            "thought": step.thought,
            "action": step.action,
            "action_input": step.action_input,
            "observation": step.observation,
            "final_answer": step.final_answer,
            "timestamp": datetime.now().isoformat(),
            "intermediate_data": intermediate_data or {}
        })
        cp.current_step = step.step_id
        cp.metadata["updated_at"] = datetime.now().isoformat()
        cp.metadata["version"] = cp.metadata.get("version", 0) + 1

        self._save_checkpoint(cp)
        self._memory_cache[task_id] = cp
        return True

    def complete_task(
        self,
        task_id: str,
        final_answer: str,
        result_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        cp = self._load_checkpoint(task_id)
        if not cp:
            return False

        cp.status = TaskStatus.COMPLETED
        cp.context["final_answer"] = final_answer
        cp.metadata["updated_at"] = datetime.now().isoformat()
        cp.metadata["completed_at"] = datetime.now().isoformat()
        if result_metadata:
            cp.metadata["result"] = result_metadata

        self._save_checkpoint(cp)
        self._memory_cache[task_id] = cp
        return True

    def fail_task(self, task_id: str, error: str) -> bool:
        cp = self._load_checkpoint(task_id)
        if not cp:
            return False

        cp.status = TaskStatus.FAILED
        cp.error_info = error
        cp.metadata["updated_at"] = datetime.now().isoformat()
        cp.metadata["failed_at"] = datetime.now().isoformat()

        self._save_checkpoint(cp)
        self._memory_cache[task_id] = cp
        return True

    def pause_task(self, task_id: str) -> bool:
        cp = self._load_checkpoint(task_id)
        if not cp:
            return False
        cp.status = TaskStatus.PAUSED
        cp.metadata["updated_at"] = datetime.now().isoformat()
        cp.metadata["paused_at"] = datetime.now().isoformat()
        self._save_checkpoint(cp)
        return True

    def cancel_task(self, task_id: str) -> bool:
        cp = self._load_checkpoint(task_id)
        if not cp:
            return False
        cp.status = TaskStatus.CANCELLED
        cp.metadata["updated_at"] = datetime.now().isoformat()
        self._save_checkpoint(cp)
        return True

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        cp = self._load_checkpoint(task_id)
        return cp.status if cp else None

    def get_task_checkpoint(self, task_id: str) -> Optional[TaskCheckpoint]:
        return self._load_checkpoint(task_id)

    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        cp = self._load_checkpoint(task_id)
        return cp.steps_history if cp else []

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        tasks = []
        for filename in os.listdir(self.storage_dir):
            if not filename.endswith(".json"):
                continue
            task_id = filename[:-5]
            cp = self._load_checkpoint(task_id)
            if not cp:
                continue
            if status and cp.status != status:
                continue
            tasks.append({
                "task_id": cp.task_id,
                "status": cp.status.value,
                "current_step": cp.current_step,
                "total_steps": cp.total_steps,
                "created_at": cp.metadata.get("created_at"),
                "updated_at": cp.metadata.get("updated_at")
            })
        tasks.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return tasks[:limit]

    def recover_task(self, task_id: str) -> Optional[TaskCheckpoint]:
        cp = self._load_checkpoint(task_id)
        if not cp:
            return None

        if cp.status not in (TaskStatus.PAUSED, TaskStatus.FAILED, TaskStatus.PENDING):
            return None

        cp.status = TaskStatus.EXECUTING
        cp.metadata["updated_at"] = datetime.now().isoformat()
        cp.metadata["recovered_at"] = datetime.now().isoformat()
        cp.metadata["recovery_count"] = cp.metadata.get("recovery_count", 0) + 1

        self._save_checkpoint(cp)
        return cp

    def can_recover(self, task_id: str) -> bool:
        cp = self._load_checkpoint(task_id)
        if not cp:
            return False
        return cp.status in (TaskStatus.PAUSED, TaskStatus.FAILED, TaskStatus.PENDING)

    def cleanup_old_tasks(self, max_age_days: int = 7) -> int:
        cleaned = 0
        cutoff = time.time() - max_age_days * 86400
        for filename in os.listdir(self.storage_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self.storage_dir, filename)
            try:
                mtime = os.path.getmtime(filepath)
                if mtime < cutoff:
                    os.remove(filepath)
                    cleaned += 1
                    task_id = filename[:-5]
                    self._memory_cache.pop(task_id, None)
            except Exception:
                pass
        return cleaned

    def _save_checkpoint(self, cp: TaskCheckpoint) -> None:
        path = self._checkpoint_path(cp.task_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cp.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_checkpoint(self, task_id: str) -> Optional[TaskCheckpoint]:
        if task_id in self._memory_cache:
            return self._memory_cache[task_id]

        path = self._checkpoint_path(task_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cp = TaskCheckpoint.from_dict(data)
            self._memory_cache[task_id] = cp
            return cp
        except Exception:
            return None


class PersistentReActReasoner:
    def __init__(self, react_reasoner, task_manager: TaskStateManager):
        self.reasoner = react_reasoner
        self.task_manager = task_manager

    def reason(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        resume: bool = False
    ) -> ReasoningResult:
        if resume and task_id and self.task_manager.can_recover(task_id):
            cp = self.task_manager.recover_task(task_id)
        else:
            task_id = self.task_manager.create_task(
                user_input=user_input,
                reasoning_type="react",
                context=context
            )

        self.task_manager.start_task(task_id)
        result = self._execute_with_checkpoints(task_id, user_input, context)
        return result

    def _execute_with_checkpoints(
        self,
        task_id: str,
        user_input: str,
        context: Optional[Dict[str, Any]]
    ) -> ReasoningResult:
        result = self.reasoner.reason(user_input, context)

        if result.success:
            self.task_manager.complete_task(
                task_id,
                result.final_answer or "",
                {
                    "llm_calls": result.total_llm_calls,
                    "tool_calls": result.total_tool_calls,
                    "steps_count": len(result.steps)
                }
            )
        else:
            self.task_manager.fail_task(task_id, result.error or "未知错误")

        for step in result.steps:
            self.task_manager.save_step(task_id, step)

        return result
