"""
终止条件判定模块（Termination Checker）

设计目标：统一管理 Agent 循环的所有退出条件，确保循环在合适时机终止

核心问题：
  - Agent 循环如果不设置终止条件，可能无限运行
  - 不同场景需要不同的终止策略
  - 需要区分"正常完成"和"异常终止"

终止条件类型：
  1. 任务完成：推理引擎返回"完成"信号
  2. 步数上限：达到预设的最大循环次数
  3. 时间上限：总运行时间超过阈值
  4. 人工中断：用户主动停止
  5. 致命错误：发生无法恢复的异常
  6. 质量阈值：连续失败次数超过限制
  7. 成本控制：LLM调用次数或Token消耗超限
"""
import time
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TerminationReason(Enum):
    NONE = "none"
    TASK_COMPLETED = "task_completed"
    MAX_STEPS_REACHED = "max_steps_reached"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    USER_INTERRUPTED = "user_interrupted"
    FATAL_ERROR = "fatal_error"
    QUALITY_THRESHOLD = "quality_threshold"
    COST_LIMIT_EXCEEDED = "cost_limit_exceeded"


@dataclass
class TerminationConfig:
    max_steps: int = 10
    max_time_seconds: int = 300
    max_llm_calls: int = 50
    max_tool_calls: int = 20
    max_consecutive_failures: int = 3
    max_total_cost: float = 10.0
    min_confidence_threshold: float = 0.3


@dataclass
class TerminationState:
    step_count: int = 0
    start_time: float = 0.0
    llm_call_count: int = 0
    tool_call_count: int = 0
    consecutive_failures: int = 0
    total_cost: float = 0.0
    last_confidence: float = 1.0


class TerminationChecker:
    def __init__(self, config: Optional[TerminationConfig] = None):
        self.config = config or TerminationConfig()
        self.state = TerminationState()
        self._checks: Dict[str, Callable] = {
            "steps": self._check_max_steps,
            "time": self._check_time_limit,
            "llm_calls": self._check_llm_calls,
            "tool_calls": self._check_tool_calls,
            "failures": self._check_consecutive_failures,
            "cost": self._check_cost_limit,
            "confidence": self._check_confidence_threshold
        }

    def initialize(self) -> None:
        self.state = TerminationState()
        self.state.start_time = time.time()
        logger.debug("终止检查器已初始化")

    def check(self, step_result: Dict[str, Any]) -> TerminationReason:
        self.state.step_count += 1

        if "llm_calls" in step_result:
            self.state.llm_call_count += step_result["llm_calls"]
        if "tool_calls" in step_result:
            self.state.tool_call_count += step_result["tool_calls"]
        if "cost" in step_result:
            self.state.total_cost += step_result["cost"]
        if "confidence" in step_result:
            self.state.last_confidence = step_result["confidence"]
        if "success" in step_result:
            if step_result["success"]:
                self.state.consecutive_failures = 0
            else:
                self.state.consecutive_failures += 1

        for check_name, check_func in self._checks.items():
            reason = check_func()
            if reason != TerminationReason.NONE:
                logger.info(f"终止条件触发: {reason.value} ({check_name})")
                return reason

        return TerminationReason.NONE

    def _check_max_steps(self) -> TerminationReason:
        if self.state.step_count >= self.config.max_steps:
            return TerminationReason.MAX_STEPS_REACHED
        return TerminationReason.NONE

    def _check_time_limit(self) -> TerminationReason:
        elapsed = time.time() - self.state.start_time
        if elapsed >= self.config.max_time_seconds:
            return TerminationReason.TIME_LIMIT_EXCEEDED
        return TerminationReason.NONE

    def _check_llm_calls(self) -> TerminationReason:
        if self.state.llm_call_count >= self.config.max_llm_calls:
            return TerminationReason.COST_LIMIT_EXCEEDED
        return TerminationReason.NONE

    def _check_tool_calls(self) -> TerminationReason:
        if self.state.tool_call_count >= self.config.max_tool_calls:
            return TerminationReason.COST_LIMIT_EXCEEDED
        return TerminationReason.NONE

    def _check_consecutive_failures(self) -> TerminationReason:
        if self.state.consecutive_failures >= self.config.max_consecutive_failures:
            return TerminationReason.QUALITY_THRESHOLD
        return TerminationReason.NONE

    def _check_cost_limit(self) -> TerminationReason:
        if self.state.total_cost >= self.config.max_total_cost:
            return TerminationReason.COST_LIMIT_EXCEEDED
        return TerminationReason.NONE

    def _check_confidence_threshold(self) -> TerminationReason:
        if self.state.last_confidence < self.config.min_confidence_threshold:
            return TerminationReason.QUALITY_THRESHOLD
        return TerminationReason.NONE

    def set_user_interrupt(self) -> TerminationReason:
        logger.info("用户中断请求")
        return TerminationReason.USER_INTERRUPTED

    def set_fatal_error(self, error: str) -> TerminationReason:
        logger.error(f"致命错误: {error}")
        return TerminationReason.FATAL_ERROR

    def set_task_completed(self) -> TerminationReason:
        logger.info("任务完成")
        return TerminationReason.TASK_COMPLETED

    def get_state(self) -> Dict[str, Any]:
        return {
            "step_count": self.state.step_count,
            "elapsed_time_seconds": time.time() - self.state.start_time,
            "llm_call_count": self.state.llm_call_count,
            "tool_call_count": self.state.tool_call_count,
            "consecutive_failures": self.state.consecutive_failures,
            "total_cost": self.state.total_cost,
            "last_confidence": self.state.last_confidence,
            "remaining_steps": self.config.max_steps - self.state.step_count,
            "remaining_time_seconds": max(0, self.config.max_time_seconds - (time.time() - self.state.start_time))
        }

    def get_termination_message(self, reason: TerminationReason) -> str:
        messages = {
            TerminationReason.NONE: "未终止",
            TerminationReason.TASK_COMPLETED: "任务已完成",
            TerminationReason.MAX_STEPS_REACHED: f"达到最大步数限制 ({self.config.max_steps})",
            TerminationReason.TIME_LIMIT_EXCEEDED: f"超过时间限制 ({self.config.max_time_seconds}s)",
            TerminationReason.USER_INTERRUPTED: "用户主动中断",
            TerminationReason.FATAL_ERROR: "发生致命错误",
            TerminationReason.QUALITY_THRESHOLD: f"连续失败次数超过限制 ({self.config.max_consecutive_failures})",
            TerminationReason.COST_LIMIT_EXCEEDED: f"成本或调用次数超过限制"
        }
        return messages.get(reason, "未知终止原因")

    def is_normal_termination(self, reason: TerminationReason) -> bool:
        return reason in (
            TerminationReason.TASK_COMPLETED,
            TerminationReason.MAX_STEPS_REACHED,
            TerminationReason.TIME_LIMIT_EXCEEDED,
            TerminationReason.USER_INTERRUPTED
        )


class SmartTerminationChecker(TerminationChecker):
    def __init__(self, config: Optional[TerminationConfig] = None):
        super().__init__(config)
        self._history: list = []
        self._trend_window = 5

    def check(self, step_result: Dict[str, Any]) -> TerminationReason:
        self._history.append(step_result)
        if len(self._history) > self._trend_window:
            self._history = self._history[-self._trend_window:]

        trend_reason = self._check_progress_trend()
        if trend_reason != TerminationReason.NONE:
            return trend_reason

        return super().check(step_result)

    def _check_progress_trend(self) -> TerminationReason:
        if len(self._history) < self._trend_window:
            return TerminationReason.NONE

        recent_results = self._history[-self._trend_window:]
        success_rate = sum(1 for r in recent_results if r.get("success", False)) / len(recent_results)

        if success_rate == 0:
            logger.warning(f"连续 {self._trend_window} 步失败，可能陷入死循环")
            return TerminationReason.QUALITY_THRESHOLD

        has_progress = any(
            r.get("progress", 0) > 0 or r.get("new_information", False)
            for r in recent_results
        )
        if not has_progress:
            logger.warning(f"连续 {self._trend_window} 步无进展，可能在重复相同操作")

        return TerminationReason.NONE
