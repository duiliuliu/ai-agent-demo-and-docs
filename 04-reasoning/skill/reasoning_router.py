"""
推理路由（Reasoning Router）

核心职责：
  根据用户输入和意图识别结果，自动选择最合适的推理方式

路由策略（基于意图类型 + 输入特征）：
  - 普通闲聊/简单问答 → 不需要推理（直接回答）
  - 数学题/逻辑题/简单分析 → CoT
  - 需要工具查询/多步交互 → ReAct
  - 复杂多步任务/需要规划 → Plan-and-Solve

设计理念：
  不同的任务用不同的推理方式，避免"用 ReAct 做 1+1"
  按需选择，控制成本，提升效率
"""
from typing import Dict, Any, List, Optional
from enum import Enum
from .base_reasoner import BaseReasoner, ReasoningType, ReasoningResult
from .cot_reasoner import CoTReasoner
from .react_reasoner import ReActReasoner
from .plan_solve_reasoner import PlanAndSolveReasoner


class TaskComplexity(Enum):
    """任务复杂度"""
    SIMPLE = "simple"          # 简单 - 不需要推理
    MODERATE = "moderate"      # 中等 - CoT
    COMPLEX = "complex"        # 复杂 - ReAct
    VERY_COMPLEX = "very_complex"  # 非常复杂 - Plan-and-Solve


class ToolRegistry:
    """工具注册器（与 02-tool-use 联动）"""

    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._descriptions: Dict[str, str] = {}

    def register(self, name: str, func, description: str = "") -> None:
        self._tools[name] = func
        if description:
            self._descriptions[name] = description

    def get(self, name: str):
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_descriptions(self) -> Dict[str, str]:
        return dict(self._descriptions)


class ReasoningRouter:
    """推理路由：基于意图和任务复杂度选择推理方式"""

    # 路由规则：意图 -> 推理方式
    ROUTING_RULES = {
        # 闲聊类 - 不需要推理
        "chat": ReasoningType.NONE,
        "greeting": ReasoningType.NONE,
        "thanks": ReasoningType.NONE,
        # 简单问答 - CoT
        "qa": ReasoningType.COT,
        "math": ReasoningType.COT,
        "logic": ReasoningType.COT,
        # 工具查询类 - ReAct
        "weather_query": ReasoningType.REACT,
        "search": ReasoningType.REACT,
        "data_query": ReasoningType.REACT,
        "calculation": ReasoningType.REACT,
        # 复杂任务 - Plan-and-Solve
        "task_planning": ReasoningType.PLAN_AND_SOLVE,
        "research": ReasoningType.PLAN_AND_SOLVE,
        "travel_plan": ReasoningType.PLAN_AND_SOLVE,
        "complex_analysis": ReasoningType.PLAN_AND_SOLVE,
    }

    # 关键词模式：检测任务复杂度
    COMPLEX_KEYWORDS = [
        "规划", "计划", "研究", "分析", "对比", "评估", "方案",
        "如何做", "帮我做", "从...到...", "步骤",
        "plan", "research", "analyze", "compare", "evaluate"
    ]

    TOOL_KEYWORDS = [
        "天气", "查询", "搜索", "搜索", "现在", "今天", "最新",
        "多少钱", "怎么走", "在哪",
        "weather", "search", "now", "today", "latest", "find"
    ]

    def __init__(
        self,
        llm_client=None,
        tool_registry: Optional[ToolRegistry] = None
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry or ToolRegistry()

        # 初始化各推理器
        self.cot = CoTReasoner(llm_client=llm_client)
        self.react = ReActReasoner(llm_client=llm_client, tools={}, max_steps=8)
        self.plan_solve = PlanAndSolveReasoner(llm_client=llm_client)

        self._register_tools_to_react()

    def _register_tools_to_react(self):
        """把工具注册表中的工具同步到 ReAct"""
        for name in self.tool_registry.list_tools():
            tool = self.tool_registry.get(name)
            desc = self.tool_registry.get_descriptions().get(name, "")
            self.react.register_tool(name, tool, desc)

    def register_tool(self, name: str, func, description: str = "") -> None:
        """注册工具（同时同步到ReAct）"""
        self.tool_registry.register(name, func, description)
        self.react.register_tool(name, func, description)

    def decide_reasoning_type(
        self,
        user_input: str,
        intent: Optional[str] = None
    ) -> ReasoningType:
        """
        决定使用哪种推理方式

        参数：
          user_input: 用户输入
          intent    : 意图识别结果（来自 02-tool-use 的 IntentRecognizer）

        返回：ReasoningType
        """
        # 1. 如果有明确的意图，优先用规则
        if intent and intent in self.ROUTING_RULES:
            return self.ROUTING_RULES[intent]

        # 2. 否则基于关键词推断
        user_input_lower = user_input.lower()

        # 2.1 检测复杂任务关键词 → Plan-and-Solve
        if any(kw in user_input_lower for kw in self.COMPLEX_KEYWORDS):
            return ReasoningType.PLAN_AND_SOLVE

        # 2.2 检测工具查询关键词 → ReAct
        if any(kw in user_input_lower for kw in self.TOOL_KEYWORDS):
            if self.tool_registry.list_tools():
                return ReasoningType.REACT

        # 2.3 检测数学/逻辑 → CoT
        if re.search(r"\d+\s*[+\-×x*/÷=]\s*\d+", user_input) or \
           any(kw in user_input for kw in ["为什么", "如何", "怎么理解"]):
            return ReasoningType.COT

        # 2.4 短输入/闲聊 → 不需要推理
        if len(user_input.strip()) < 5:
            return ReasoningType.NONE

        # 3. 默认 CoT
        return ReasoningType.COT

    def reason(
        self,
        user_input: str,
        intent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ReasoningResult:
        """
        根据路由决策执行推理

        参数：
          user_input: 用户输入
          intent    : 意图（可选）
          context   : 上下文（可包含记忆等）

        返回：ReasoningResult
        """
        # 决定推理方式
        reasoning_type = self.decide_reasoning_type(user_input, intent)

        if reasoning_type == ReasoningType.NONE:
            # 不需要推理，直接返回
            return ReasoningResult(
                reasoning_type=ReasoningType.NONE,
                user_input=user_input,
                final_answer=f"已收到：{user_input}",
                success=True,
                metadata={"intent": intent, "skip_reason": "simple_chat"}
            )

        # 选择对应推理器
        if reasoning_type == ReasoningType.COT:
            return self.cot.reason(user_input, context)
        elif reasoning_type == ReasoningType.REACT:
            return self.react.reason(user_input, context)
        elif reasoning_type == ReasoningType.PLAN_AND_SOLVE:
            return self.plan_solve.reason(user_input, context)

        # 兜底
        return self.cot.reason(user_input, context)


# 延迟导入 re
import re
