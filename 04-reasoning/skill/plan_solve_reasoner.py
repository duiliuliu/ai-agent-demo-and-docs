"""
Plan-and-Solve 推理器

核心思想：
  阶段1（Planning）：先制定完整计划，列出所有需要执行的步骤
  阶段2（Solving）：逐步执行计划中的步骤，根据结果动态调整
  阶段3（Verification）：验证最终结果，给出答案

适用场景：
  - 复杂多步任务
  - 任务需要提前规划（如：旅行规划、研究任务）
  - 用户希望审核执行计划
  - 任务执行顺序有依赖关系

不适用：
  - 简单问题（用CoT更高效）
  - 实时交互查询（用ReAct更灵活）
  - 计划可能频繁变化的任务

成本：1 次规划 LLM + N 次执行 LLM + 1 次验证 LLM
优点：可提前发现错误、用户可审核计划、结构化输出
局限：计划可能不准确、规划成本固定

实现要点：
  - Planning LLM：分析问题，输出步骤列表
  - Solving LLM：逐步执行计划中的步骤
  - Verification LLM：验证结果，给出最终答案
  - 计划可被用户调整（进阶：交互式规划）
"""
import re
import time
from typing import Dict, Any, List, Optional
from .base_reasoner import BaseReasoner, ReasoningType, Step, ReasoningResult


class PlanAndSolveReasoner(BaseReasoner):
    """Plan-and-Solve 推理器"""

    PLANNING_PROMPT = """你是一个善于规划任务的AI助手。请分析用户的问题，制定一个详细的执行计划。

问题：{question}

请按以下格式输出计划：
Plan:
1. 第一步：[具体行动]
2. 第二步：[具体行动]
3. 第三步：[具体行动]
...

{context}
"""

    SOLVING_PROMPT = """你正在执行以下计划：
{plan}

当前进度：已完成前 {completed} 步，共 {total} 步
已完成的步骤结果：
{results}

下一步：{next_step}

请思考如何执行这一步，并给出这一步的结果。

{context}

请按以下格式输出：
Thought: [你的思考]
Result: [这一步的结果]
"""

    VERIFICATION_PROMPT = """基于以下信息，请验证并给出最终答案：

问题：{question}

执行计划：
{plan}

各步骤结果：
{results}

请验证以上结果是否正确回答了问题，然后给出最终答案。

{context}

请按以下格式输出：
Verification: [验证过程的简短说明]
Final Answer: [最终答案]
"""

    def __init__(self, llm_client=None, max_steps: int = 10):
        super().__init__(llm_client, max_steps)

    def reason(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ReasoningResult:
        start_time = time.time()
        result = ReasoningResult(
            reasoning_type=ReasoningType.PLAN_AND_SOLVE,
            user_input=user_input
        )
        self.reset_call_count()
        ctx = context or {}

        try:
            # 阶段1：制定计划
            plan_step, plan = self._planning_phase(user_input, ctx, result)
            if not plan:
                result.success = False
                result.error = "规划阶段未能生成有效计划"
                result.execution_time_ms = (time.time() - start_time) * 1000
                return result

            # 阶段2：逐步执行
            step_results = self._solving_phase(plan, ctx, result)

            # 阶段3：验证并给出最终答案
            final_answer = self._verification_phase(
                user_input, plan, step_results, ctx, result
            )
            result.final_answer = final_answer
            result.success = final_answer is not None

        except Exception as e:
            result.success = False
            result.error = str(e)

        result.execution_time_ms = (time.time() - start_time) * 1000
        return result

    def _planning_phase(
        self,
        user_input: str,
        context: Dict,
        result: ReasoningResult
    ) -> tuple:
        """规划阶段：生成执行计划"""
        prompt = self.PLANNING_PROMPT.format(
            question=user_input,
            context=context.get("context", "")
        )
        llm_response = self.call_llm(prompt)
        result.total_llm_calls = self.get_call_count()

        # 解析计划
        plan = self._parse_plan(llm_response)

        # 记录规划步骤
        plan_text = "\n".join([f"  {i+1}. {step}" for i, step in enumerate(plan)])
        result.steps.append(Step(
            step_id=1,
            thought=f"规划阶段：分析问题并制定执行计划",
            observation=plan_text
        ))

        return result.steps[0], plan

    def _solving_phase(
        self,
        plan: List[str],
        context: Dict,
        result: ReasoningResult
    ) -> List[str]:
        """求解阶段：逐步执行计划"""
        step_results = []

        for i, plan_step in enumerate(plan):
            if i + 2 > self.max_steps:
                # 超过最大步数
                result.steps.append(Step(
                    step_id=i + 2,
                    thought=f"达到最大步数限制，停止执行"
                ))
                break

            results_text = "\n".join([
                f"  步骤{j+1}: {r}" for j, r in enumerate(step_results)
            ]) if step_results else "（无）"

            prompt = self.SOLVING_PROMPT.format(
                plan="\n".join([f"  {j+1}. {s}" for j, s in enumerate(plan)]),
                completed=i,
                total=len(plan),
                results=results_text,
                next_step=plan_step,
                context=context.get("context", "")
            )

            llm_response = self.call_llm(prompt)
            result.total_llm_calls += 1

            # 解析本步结果
            step_result = self._parse_step_result(llm_response)
            step_results.append(step_result)

            result.steps.append(Step(
                step_id=i + 2,
                thought=f"执行步骤 {i+1}: {plan_step}",
                observation=step_result
            ))

        return step_results

    def _verification_phase(
        self,
        user_input: str,
        plan: List[str],
        step_results: List[str],
        context: Dict,
        result: ReasoningResult
    ) -> Optional[str]:
        """验证阶段：验证并给出最终答案"""
        plan_text = "\n".join([f"  {i+1}. {step}" for i, step in enumerate(plan)])
        results_text = "\n".join([
            f"  步骤{i+1}: {r}" for i, r in enumerate(step_results)
        ])

        prompt = self.VERIFICATION_PROMPT.format(
            question=user_input,
            plan=plan_text,
            results=results_text,
            context=context.get("context", "")
        )
        llm_response = self.call_llm(prompt)
        result.total_llm_calls = self.get_call_count()

        # 解析最终答案
        final_answer = self._parse_final_answer(llm_response)

        result.steps.append(Step(
            step_id=len(result.steps) + 1,
            thought="验证阶段：验证结果并给出最终答案",
            observation=final_answer or llm_response,
            final_answer=final_answer
        ))

        return final_answer

    def _parse_plan(self, response: str) -> List[str]:
        """解析计划"""
        plan = []
        # 匹配 "1. xxx" 或 "步骤1: xxx" 等格式
        for match in re.finditer(r"(?:^|\n)\s*(?:\d+[.、])\s*(.+?)(?=\n\s*\d+[.、]|\n*$|\Z)", response, re.MULTILINE):
            step = match.group(1).strip()
            if step and len(step) > 2:
                plan.append(step)
        return plan

    def _parse_step_result(self, response: str) -> str:
        """解析单步结果"""
        result_match = re.search(r"Result\s*[:：]\s*(.+?)(?:\n|$)", response, re.IGNORECASE | re.DOTALL)
        if result_match:
            return result_match.group(1).strip()
        return response.strip()

    def _parse_final_answer(self, response: str) -> Optional[str]:
        """解析最终答案"""
        match = re.search(r"Final Answer\s*[:：]\s*(.+?)(?:\n|$)", response, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return response.strip()[:200]

    def _mock_llm(self, prompt: str, **kwargs) -> str:
        """Plan-and-Solve 模拟LLM"""
        # 规划阶段
        if "Plan:" in prompt or "请按以下格式输出计划" in prompt:
            return self._mock_planning(prompt)
        # 验证阶段
        if "Verification:" in prompt or "请验证以上结果" in prompt:
            return self._mock_verification(prompt)
        # 求解阶段
        return self._mock_solving(prompt)

    def _mock_planning(self, prompt: str) -> str:
        """模拟规划阶段"""
        question_match = re.search(r"问题[：:]\s*(.+?)(?:\n|$)", prompt)
        question = question_match.group(1).strip() if question_match else "未知问题"

        # 旅行规划类
        if any(kw in question for kw in ["旅行", "旅游", "trip", "travel"]):
            return """Plan:
1. 确定旅行目的地和时间
2. 查询目的地天气
3. 规划每日行程
4. 估算预算
5. 整理最终方案"""

        # 研究类
        if any(kw in question for kw in ["研究", "分析", "对比", "research", "compare"]):
            return """Plan:
1. 明确研究目标和范围
2. 收集相关资料
3. 分析和对比关键维度
4. 得出结论"""

        # 计算/求解类
        if re.search(r"\d+\s*[+\-×x*/÷]\s*\d+", question):
            return """Plan:
1. 解析表达式
2. 执行计算
3. 验证结果"""

        # 默认
        return """Plan:
1. 分析问题需求
2. 收集相关信息
3. 整理和组织信息
4. 得出结论"""

    def _mock_solving(self, prompt: str) -> str:
        """模拟求解阶段"""
        next_step_match = re.search(r"下一步[：:]\s*(.+?)(?:\n|$)", prompt)
        next_step = next_step_match.group(1).strip() if next_step_match else "执行步骤"

        return f"""Thought: 我需要执行这一步：{next_step}
Result: 已完成'{next_step}'的分析和处理，得到相应结果。"""

    def _mock_verification(self, prompt: str) -> str:
        """模拟验证阶段"""
        question_match = re.search(r"问题[：:]\s*(.+?)(?:\n|$)", prompt)
        question = question_match.group(1).strip() if question_match else "未知问题"

        # 提取所有步骤结果
        results = re.findall(r"步骤\d+:\s*([^\n]+)", prompt)
        results_summary = "；".join(results) if results else "已完成所有步骤"

        return f"""Verification: 验证了所有执行步骤的结果，逻辑一致且完整。
Final Answer: 基于以上步骤的结果，问题的答案是：{results_summary}。"""
