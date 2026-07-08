"""
推理模块的基类和数据结构

设计理念：
  三种推理方式（CoT/ReAct/Plan-and-Solve）有共同点：
  - 接收问题 → 产生步骤序列 → 输出答案
  - 都是LLM的Prompt工程，只是Prompt结构和循环方式不同

统一抽象：
  Reasoner 接收 user_input + context，产生 ReasoningResult（包含 steps + final_answer）
  Step 是单个推理步骤的抽象
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum


class ReasoningType(Enum):
    """推理方式类型"""
    COT = "cot"                      # Chain of Thought
    REACT = "react"                  # Reasoning + Acting
    PLAN_AND_SOLVE = "plan_and_solve"  # Plan and Solve
    NONE = "none"                    # 不需要推理


@dataclass
class Step:
    """单个推理步骤"""
    step_id: int
    thought: str                            # 思考过程
    action: Optional[str] = None            # 行动（ReAct 专用）
    action_input: Optional[Dict[str, Any]] = None  # 行动参数
    observation: Optional[str] = None       # 观察结果（ReAct 专用）
    final_answer: Optional[str] = None      # 最终答案（最后一步设置）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "final_answer": self.final_answer
        }


@dataclass
class ReasoningResult:
    """推理结果"""
    reasoning_type: ReasoningType
    user_input: str
    steps: List[Step] = field(default_factory=list)
    final_answer: Optional[str] = None
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reasoning_type": self.reasoning_type.value,
            "user_input": self.user_input,
            "steps": [s.to_dict() for s in self.steps],
            "final_answer": self.final_answer,
            "total_llm_calls": self.total_llm_calls,
            "total_tool_calls": self.total_tool_calls,
            "execution_time_ms": self.execution_time_ms,
            "success": self.success,
            "error": self.error
        }

    def trace(self) -> str:
        """生成可读的推理轨迹"""
        lines = [f"推理类型: {self.reasoning_type.value}", ""]
        for step in self.steps:
            lines.append(f"[步骤 {step.step_id}]")
            lines.append(f"  思考: {step.thought}")
            if step.action:
                lines.append(f"  行动: {step.action}({step.action_input})")
            if step.observation:
                lines.append(f"  观察: {step.observation}")
            if step.final_answer:
                lines.append(f"  ★ 最终答案: {step.final_answer}")
            lines.append("")
        lines.append(f"统计: LLM调用={self.total_llm_calls}, 工具调用={self.total_tool_calls}, 耗时={self.execution_time_ms:.1f}ms")
        return "\n".join(lines)


class BaseReasoner(ABC):
    """推理器基类"""

    def __init__(self, llm_client: Optional[Any] = None, max_steps: int = 10):
        """
        参数：
          llm_client: LLM 客户端（None 时使用模拟LLM）
          max_steps  : 最大推理步数（防止ReAct死循环）
        """
        self.llm_client = llm_client
        self.max_steps = max_steps

    @abstractmethod
    def reason(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ReasoningResult:
        """执行推理，返回结果"""
        pass

    def call_llm(self, prompt: str, **kwargs) -> str:
        """
        调用 LLM（带模拟 fallback）
        Demo 模式下子类可以重写此方法以使用模拟LLM
        """
        if self.llm_client is None:
            result = self._mock_llm(prompt, **kwargs)
        else:
            try:
                result = self.llm_client.generate(prompt, **kwargs)
            except Exception as e:
                result = f"[LLM Error: {e}]"
        # 统计 LLM 调用次数（子类可重写 _mock_llm 以访问更细粒度的统计）
        if not hasattr(self, "_llm_call_count"):
            self._llm_call_count = 0
        self._llm_call_count += 1
        return result

    def _mock_llm(self, prompt: str, **kwargs) -> str:
        """模拟 LLM（用于 Demo）"""
        return "[Mock LLM Response]"

    def _mock_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """模拟工具执行（用于 Demo）"""
        return f"[Mock Tool Result for {tool_name}({tool_input})]"

    def reset_call_count(self) -> None:
        """重置调用计数"""
        self._llm_call_count = 0

    def get_call_count(self) -> int:
        """获取 LLM 调用次数"""
        return getattr(self, "_llm_call_count", 0)
