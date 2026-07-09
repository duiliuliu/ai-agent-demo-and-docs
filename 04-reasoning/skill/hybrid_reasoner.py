"""
混合推理器（Hybrid / Multi-Stage Reasoner）

解决核心问题：多种推理方式是否可以综合一起使用？

答案是肯定的，而且往往是必须的。单一推理方式各有局限：
  - CoT：快但无法获取外部信息、无法修正错误
  - ReAct：能交互但缺乏全局规划、可能陷入局部最优
  - Plan-and-Solve：能规划但执行僵硬、计划可能不切实际

设计思想：分阶段、分层次地组合不同推理方式
  "让每种推理方式做它最擅长的事"

三种组合模式：
  1. 串行流水线（Pipeline）：阶段1 → 阶段2 → 阶段3
  2. 分层调度（Hierarchical）：顶层规划 → 中层分解 → 底层执行
  3. 竞争择优（Ensemble）：多种方式并行 → 投票/评估选最佳

架构：
  ┌─────────────────────────────────────────────────────────────┐
│                    MultiStageReasoner                        │
│                                                              │
│  输入: user_input + context                                  │
│    │                                                         │
│    ▼                                                         │
│  Stage 1: CoTPreAnalyzer（CoT 做问题分析）                   │
│    - 判断问题类型、复杂度、所需信息                          │
│    - 输出: 问题分解 + 推理策略建议                           │
│    │                                                         │
│    ▼                                                         │
│  Stage 2: InfoGatherer（ReAct 获取外部信息）                 │
│    - 若需要实时信息/工具查询，用 ReAct 获取                  │
│    - 输出: 收集到的关键信息                                  │
│    │                                                         │
│    ▼                                                         │
│  Stage 3: GlobalPlanner（Plan-and-Solve 做全局规划）         │
│    - 基于已有信息制定完整计划                                │
│    - 输出: 执行计划                                          │
│    │                                                         │
│    ▼                                                         │
│  Stage 4: PlanExecutor（混合执行）                           │
│    - 简单子任务 → CoT                                        │
│    - 需要工具 → ReAct                                        │
│    - 输出: 各子任务结果                                      │
│    │                                                         │
│    ▼                                                         │
│  Stage 5: FinalSynthesizer（CoT 做最终综合）                 │
│    - 整合所有子结果，给出最终答案                            │
│    - 输出: final_answer                                      │
└─────────────────────────────────────────────────────────────┘
"""
import re
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .base_reasoner import BaseReasoner, ReasoningType, Step, ReasoningResult
from .cot_reasoner import CoTReasoner
from .react_reasoner import ReActReasoner
from .plan_solve_reasoner import PlanAndSolveReasoner


class StageType(Enum):
    ANALYZE = "analyze"
    GATHER = "gather"
    PLAN = "plan"
    EXECUTE = "execute"
    SYNTHESIZE = "synthesize"


@dataclass
class StageResult:
    stage_type: StageType
    stage_name: str
    success: bool
    output: Any = None
    steps: List[Step] = field(default_factory=list)
    llm_calls: int = 0
    tool_calls: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_type": self.stage_type.value,
            "stage_name": self.stage_name,
            "success": self.success,
            "output": self.output,
            "steps": [s.to_dict() for s in self.steps],
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "error": self.error
        }


@dataclass
class HybridReasoningResult(ReasoningResult):
    stages: List[StageResult] = field(default_factory=list)
    strategy_used: str = ""

    def trace(self) -> str:
        lines = [
            f"推理类型: {self.reasoning_type.value} (混合推理)",
            f"组合策略: {self.strategy_used}",
            f"总阶段数: {len(self.stages)}",
            ""
        ]
        for i, stage in enumerate(self.stages):
            lines.append(f"=== 阶段 {i+1}: {stage.stage_name} ({stage.stage_type.value}) ===")
            if not stage.success:
                lines.append(f"  [失败] {stage.error}")
            else:
                lines.append(f"  输出: {str(stage.output)[:200]}")
                for step in stage.steps:
                    lines.append(f"  [Step {step.step_id}] {step.thought[:100]}")
                    if step.action:
                        lines.append(f"    Action: {step.action}")
                    if step.observation:
                        lines.append(f"    Observation: {step.observation[:100]}")
            lines.append("")
        lines.append(f"★ 最终答案: {self.final_answer}")
        lines.append(f"统计: LLM={self.total_llm_calls}, 工具={self.total_tool_calls}, 耗时={self.execution_time_ms:.1f}ms")
        return "\n".join(lines)


class MultiStageReasoner(BaseReasoner):
    def __init__(
        self,
        llm_client=None,
        tools: Optional[Dict[str, Callable]] = None,
        tool_descriptions: Optional[Dict[str, str]] = None,
        max_steps: int = 15,
        enable_stages: Optional[List[StageType]] = None
    ):
        super().__init__(llm_client, max_steps)
        self.tools = tools or {}
        self.tool_descriptions = tool_descriptions or {}

        self.cot = CoTReasoner(llm_client=llm_client)
        self.react = ReActReasoner(
            llm_client=llm_client,
            tools=self.tools,
            tool_descriptions=self.tool_descriptions,
            max_steps=6
        )
        self.plan_solve = PlanAndSolveReasoner(llm_client=llm_client)

        self.enable_stages = enable_stages or [
            StageType.ANALYZE, StageType.GATHER,
            StageType.PLAN, StageType.EXECUTE, StageType.SYNTHESIZE
        ]

    def reason(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> HybridReasoningResult:
        start_time = time.time()
        result = HybridReasoningResult(
            reasoning_type=ReasoningType.COT,
            user_input=user_input,
            stages=[]
        )

        ctx = context or {}
        intermediate_data: Dict[str, Any] = {}

        try:
            if StageType.ANALYZE in self.enable_stages:
                stage1 = self._stage_analyze(user_input, ctx)
                result.stages.append(stage1)
                result.total_llm_calls += stage1.llm_calls
                if not stage1.success:
                    result.success = False
                    result.error = f"分析阶段失败: {stage1.error}"
                    result.execution_time_ms = (time.time() - start_time) * 1000
                    return result
                intermediate_data["analysis"] = stage1.output

            if StageType.GATHER in self.enable_stages:
                needs_gather = self._needs_info_gathering(intermediate_data)
                if needs_gather:
                    stage2 = self._stage_gather(user_input, intermediate_data, ctx)
                    result.stages.append(stage2)
                    result.total_llm_calls += stage2.llm_calls
                    result.total_tool_calls += stage2.tool_calls
                    intermediate_data["gathered_info"] = stage2.output if stage2.success else ""
                else:
                    result.stages.append(StageResult(
                        stage_type=StageType.GATHER,
                        stage_name="信息收集（跳过）",
                        success=True,
                        output="无需外部信息"
                    ))

            if StageType.PLAN in self.enable_stages:
                stage3 = self._stage_plan(user_input, intermediate_data, ctx)
                result.stages.append(stage3)
                result.total_llm_calls += stage3.llm_calls
                if not stage3.success:
                    result.success = False
                    result.error = f"规划阶段失败: {stage3.error}"
                    result.execution_time_ms = (time.time() - start_time) * 1000
                    return result
                intermediate_data["plan"] = stage3.output

            if StageType.EXECUTE in self.enable_stages and "plan" in intermediate_data:
                stage4 = self._stage_execute(user_input, intermediate_data, ctx)
                result.stages.append(stage4)
                result.total_llm_calls += stage4.llm_calls
                result.total_tool_calls += stage4.tool_calls
                intermediate_data["execution_results"] = stage4.output if stage4.success else []
            else:
                result.stages.append(StageResult(
                    stage_type=StageType.EXECUTE,
                    stage_name="执行（跳过）",
                    success=True,
                    output=[]
                ))

            if StageType.SYNTHESIZE in self.enable_stages:
                stage5 = self._stage_synthesize(user_input, intermediate_data, ctx)
                result.stages.append(stage5)
                result.total_llm_calls += stage5.llm_calls
                result.final_answer = stage5.output if stage5.success else None
                result.success = stage5.success
                if not stage5.success:
                    result.error = f"综合阶段失败: {stage5.error}"

            result.strategy_used = self._describe_strategy(result.stages)

        except Exception as e:
            result.success = False
            result.error = str(e)

        result.execution_time_ms = (time.time() - start_time) * 1000
        return result

    def _stage_analyze(self, user_input: str, ctx: Dict) -> StageResult:
        prompt = f"""请分析以下问题，输出：
1. 问题类型（math/logic/factual/creative/comparison）
2. 复杂度（simple/moderate/complex）
3. 是否需要外部信息（天气/搜索/计算等）
4. 建议的解决步骤（3-5步）

问题：{user_input}

分析："""
        response = self.call_llm(prompt)
        analysis = self._parse_analysis(response)

        return StageResult(
            stage_type=StageType.ANALYZE,
            stage_name="问题分析",
            success=True,
            output=analysis,
            steps=[Step(step_id=1, thought=response[:500])],
            llm_calls=1
        )

    def _stage_gather(self, user_input: str, data: Dict, ctx: Dict) -> StageResult:
        react_result = self.react.reason(user_input, ctx)
        return StageResult(
            stage_type=StageType.GATHER,
            stage_name="信息收集",
            success=react_result.success,
            output=react_result.final_answer,
            steps=react_result.steps,
            llm_calls=react_result.total_llm_calls,
            tool_calls=react_result.total_tool_calls,
            error=react_result.error
        )

    def _stage_plan(self, user_input: str, data: Dict, ctx: Dict) -> StageResult:
        extra_context = ""
        if "gathered_info" in data:
            extra_context = f"\n已收集到的信息：{data['gathered_info']}\n"
        if "analysis" in data:
            extra_context += f"\n问题分析：{data['analysis']}\n"

        plan_ctx = dict(ctx)
        plan_ctx["context"] = plan_ctx.get("context", "") + extra_context

        plan_result = self.plan_solve.reason(user_input, plan_ctx)
        plan_steps = []
        if plan_result.steps:
            plan_steps = self._extract_plan_from_steps(plan_result.steps)

        return StageResult(
            stage_type=StageType.PLAN,
            stage_name="全局规划",
            success=plan_result.success,
            output=plan_steps,
            steps=plan_result.steps,
            llm_calls=plan_result.total_llm_calls,
            error=plan_result.error
        )

    def _stage_execute(self, user_input: str, data: Dict, ctx: Dict) -> StageResult:
        plan = data.get("plan", [])
        if not plan:
            return StageResult(
                stage_type=StageType.EXECUTE,
                stage_name="计划执行",
                success=True,
                output=[]
            )

        all_steps = []
        total_llm = 0
        total_tool = 0
        sub_results = []

        for i, sub_task in enumerate(plan[:5]):
            sub_reasoner = self._choose_sub_reasoner(sub_task)
            sub_ctx = dict(ctx)
            sub_ctx["context"] = f"这是整体任务的一部分。整体问题：{user_input}。当前子任务：{sub_task}"

            sub_result = sub_reasoner.reason(sub_task, sub_ctx)
            sub_results.append({
                "task": sub_task,
                "answer": sub_result.final_answer,
                "success": sub_result.success
            })
            all_steps.extend(sub_result.steps)
            total_llm += sub_result.total_llm_calls
            total_tool += sub_result.total_tool_calls

        return StageResult(
            stage_type=StageType.EXECUTE,
            stage_name="计划执行",
            success=True,
            output=sub_results,
            steps=all_steps,
            llm_calls=total_llm,
            tool_calls=total_tool
        )

    def _stage_synthesize(self, user_input: str, data: Dict, ctx: Dict) -> StageResult:
        parts = [f"原始问题：{user_input}"]
        if "analysis" in data:
            parts.append(f"问题分析：{data['analysis']}")
        if "gathered_info" in data:
            parts.append(f"收集到的信息：{data['gathered_info']}")
        if "execution_results" in data:
            for r in data["execution_results"]:
                parts.append(f"- {r['task']}: {r['answer']}")

        synthesize_prompt = "\n".join(parts) + "\n\n请综合以上所有信息，给出完整、清晰的最终答案。"
        syn_result = self.cot.reason(synthesize_prompt, ctx)

        return StageResult(
            stage_type=StageType.SYNTHESIZE,
            stage_name="结果综合",
            success=syn_result.success,
            output=syn_result.final_answer,
            steps=syn_result.steps,
            llm_calls=syn_result.total_llm_calls,
            error=syn_result.error
        )

    def _needs_info_gathering(self, data: Dict) -> bool:
        analysis = data.get("analysis", {})
        if isinstance(analysis, dict):
            return analysis.get("needs_external_info", True)
        return bool(self.tools)

    def _choose_sub_reasoner(self, sub_task: str) -> BaseReasoner:
        task_lower = sub_task.lower()
        if any(kw in task_lower for kw in ["查询", "搜索", "查", "天气", "计算", "工具"]):
            return self.react
        return self.cot

    def _parse_analysis(self, response: str) -> Dict[str, Any]:
        analysis = {}
        type_match = re.search(r"问题类型[：:]\s*(\w+)", response, re.IGNORECASE)
        if type_match:
            analysis["type"] = type_match.group(1)
        complexity_match = re.search(r"复杂度[：:]\s*(\w+)", response, re.IGNORECASE)
        if complexity_match:
            analysis["complexity"] = complexity_match.group(1)
        needs_match = re.search(r"(?:是否需要外部信息|外部信息)[：:]\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
        if needs_match:
            analysis["needs_external_info"] = "是" in needs_match.group(1) or "yes" in needs_match.group(1).lower()
        return analysis

    def _extract_plan_from_steps(self, steps: List[Step]) -> List[str]:
        plan_steps = []
        for step in steps:
            if step.observation:
                lines = step.observation.split("\n")
                for line in lines:
                    line = line.strip()
                    if re.match(r"^\d+[.、]\s*", line):
                        plan_steps.append(re.sub(r"^\d+[.、]\s*", "", line))
        return plan_steps

    def _describe_strategy(self, stages: List[StageResult]) -> str:
        names = [s.stage_name for s in stages if s.success]
        return " → ".join(names)

    def _mock_llm(self, prompt: str, **kwargs) -> str:
        if "请分析以下问题" in prompt:
            return self._mock_analyze(prompt)
        if "请综合以上所有信息" in prompt:
            return self._mock_synthesize(prompt)
        return CoTReasoner()._mock_llm(prompt, **kwargs)

    def _mock_analyze(self, prompt: str) -> str:
        question_match = re.search(r"问题[：:]\s*(.+?)(?:\n|$)", prompt)
        question = question_match.group(1).strip() if question_match else "未知问题"

        if "旅行" in question or "trip" in question.lower():
            return """1. 问题类型：planning
2. 复杂度：complex
3. 是否需要外部信息：是（需要查询天气、景点、交通等）
4. 建议步骤：
   1. 确定目的地和时间
   2. 查询目的地天气和最佳景点
   3. 规划每日行程
   4. 估算预算
   5. 整理完整方案"""

        if "比较" in question or "对比" in question or "vs" in question.lower():
            return """1. 问题类型：comparison
2. 复杂度：moderate
3. 是否需要外部信息：是（可能需要查询最新数据）
4. 建议步骤：
   1. 确定比较维度
   2. 收集各对象信息
   3. 逐维度对比
   4. 总结优劣"""

        if re.search(r"\d+\s*[+\-×x*/]\s*\d+", question):
            return """1. 问题类型：math
2. 复杂度：simple
3. 是否需要外部信息：否
4. 建议步骤：
   1. 解析表达式
   2. 执行计算
   3. 验证结果"""

        return """1. 问题类型：factual
2. 复杂度：moderate
3. 是否需要外部信息：是
4. 建议步骤：
   1. 理解问题核心
   2. 收集相关信息
   3. 整理回答"""

    def _mock_synthesize(self, prompt: str) -> str:
        if "旅行" in prompt or "trip" in prompt.lower():
            return """基于以上分析，我为您整理了完整方案：
1. 目的地和天气已确认适宜
2. 行程已按天数合理分配
3. 预算在可控范围内
最终答案：旅行方案已制定完成，包含行程、住宿、预算等详细信息。"""

        if "比较" in prompt or "对比" in prompt:
            return """综合以上各维度对比：
- 性能方面：A 更优
- 价格方面：B 更优
- 生态方面：A 更优
最终答案：根据您的需求，如果重视性能和生态选 A，如果重视性价比选 B。"""

        return """综合以上所有信息，最终答案如下：
基于收集到的资料和逐步分析，问题的答案是已明确。
最终答案：基于以上推理，这是最终答案。"""
