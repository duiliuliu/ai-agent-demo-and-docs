"""
CoT (Chain of Thought) 推理器

核心思想：
  通过 Prompt 引导 LLM 逐步思考，把复杂问题分解为多个简单步骤。
  关键 Prompt 模板："Let's think step by step"

适用场景：
  - 数学题、逻辑推理
  - 简单分析任务
  - 不需要外部信息的推理

不适用：
  - 需要实时信息（天气、股票）
  - 需要查询数据库
  - 需要执行外部操作

成本：1 次 LLM 调用
优点：简单、Token 少、延迟低
局限：单次推理，无法获取外部信息、无法修正错误

实现方式：
  1. 构建 CoT Prompt（Few-shot 示例 + 问题）
  2. 单次 LLM 调用，要求分步思考
  3. 解析输出，提取步骤和最终答案
"""
import re
import time
from typing import Dict, Any, List, Optional
from .base_reasoner import BaseReasoner, ReasoningType, Step, ReasoningResult


class CoTReasoner(BaseReasoner):
    """Chain of Thought 推理器"""

    COT_PROMPT_TEMPLATE = """你是一个善于逐步推理的AI助手。请一步一步地思考问题，给出详细的推理过程，最后给出最终答案。

问题：{question}

让我们一步一步地思考：

{context}
"""

    COT_FEWSHOT = """示例：
问题：一个苹果5元，三个苹果多少钱？
思考：
1. 题目说一个苹果5元
2. 需要买3个
3. 总价 = 5 × 3 = 15元
最终答案：15元

---

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
            reasoning_type=ReasoningType.COT,
            user_input=user_input
        )
        self.reset_call_count()

        try:
            # 构建 Prompt
            context_text = (context or {}).get("context", "")
            prompt = self._build_prompt(user_input, context_text)

            # 单次 LLM 调用
            llm_response = self.call_llm(prompt)
            result.total_llm_calls = self.get_call_count()

            # 解析响应，提取步骤
            steps = self._parse_response(llm_response)
            result.steps = steps

            # 提取最终答案
            if steps:
                result.final_answer = steps[-1].final_answer or self._extract_final_answer(llm_response)

            result.success = result.final_answer is not None
            if not result.success:
                result.error = "未能从LLM响应中提取最终答案"

        except Exception as e:
            result.success = False
            result.error = str(e)

        result.execution_time_ms = (time.time() - start_time) * 1000
        return result

    def _build_prompt(self, question: str, context: str) -> str:
        return self.COT_PROMPT_TEMPLATE.format(
            question=question,
            context=context
        )

    def _parse_response(self, response: str) -> List[Step]:
        """解析 LLM 响应，提取步骤"""
        steps = []
        lines = response.strip().split("\n")
        current_step = 1
        current_thought_lines: List[str] = []
        final_answer = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测步骤标记 "1." "2." 或 "步骤1" "Step 1"
            step_match = re.match(r"^(?:步骤|Step)?\s*(\d+)[.、:：]\s*(.+)", line, re.IGNORECASE)
            if step_match:
                # 保存之前的步骤
                if current_thought_lines:
                    steps.append(Step(
                        step_id=current_step,
                        thought="\n".join(current_thought_lines)
                    ))
                    current_step += 1
                    current_thought_lines = []
                current_thought_lines.append(step_match.group(2))
            elif "最终答案" in line or "Final Answer" in line.lower():
                # 提取最终答案
                answer = re.sub(r"^(?:最终答案|Final Answer)\s*[:：]?\s*", "", line, flags=re.IGNORECASE).strip()
                final_answer = answer
            else:
                current_thought_lines.append(line)

        # 保存最后一个思考步骤
        if current_thought_lines:
            steps.append(Step(
                step_id=current_step,
                thought="\n".join(current_thought_lines)
            ))

        # 把最终答案附加到最后一步
        if steps and final_answer:
            steps[-1].final_answer = final_answer

        return steps

    def _extract_final_answer(self, response: str) -> Optional[str]:
        """从响应中提取最终答案"""
        # 尝试匹配 "最终答案:" 后的内容
        match = re.search(r"(?:最终答案|Final Answer)\s*[:：]\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # 兜底：取最后一行非空内容
        lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
        return lines[-1] if lines else None

    def _mock_llm(self, prompt: str, **kwargs) -> str:
        """CoT 模拟LLM：基于问题模式生成合理的推理步骤"""
        # 提取问题
        question_match = re.search(r"问题[：:]\s*(.+?)(?:\n|$)", prompt)
        if not question_match:
            return "无法解析问题。\n最终答案：未知"
        question = question_match.group(1).strip()

        # 数学题
        if re.search(r"\d+\s*[+\-×x*/÷]\s*\d+", question):
            return self._mock_math(question)
        # 逻辑题
        if any(kw in question for kw in ["为什么", "如何", "怎么", "how", "why"]):
            return self._mock_explanation(question)
        # 比较类
        if any(kw in question for kw in ["比较", "区别", "vs", "对比"]):
            return self._mock_comparison(question)
        # 默认
        return self._mock_default(question)

    def _mock_math(self, question: str) -> str:
        """模拟数学题推理"""
        expr_match = re.search(r"(\d+)\s*([+\-×x*/÷])\s*(\d+)", question)
        if not expr_match:
            return "我需要计算这个表达式。\n最终答案：未知"
        a, op, b = int(expr_match.group(1)), expr_match.group(2), int(expr_match.group(3))
        op_map = {"+": a + b, "-": a - b, "×": a * b, "x": a * b, "*": a * b, "/": a // b if b != 0 else 0, "÷": a // b if b != 0 else 0}
        result = op_map.get(op, 0)
        return f"""1. 我看到这是一个算术表达式：{a} {op} {b}
2. 我需要计算 {a} {op} {b} 的值
3. {a} {op} {b} = {result}
4. 所以最终结果是 {result}
最终答案：{result}"""

    def _mock_explanation(self, question: str) -> str:
        """模拟解释类推理"""
        return f"""1. 我需要理解用户的问题：{question}
2. 分析问题的关键点
3. 整理相关的知识
4. 组织成清晰的解释
最终答案：基于以上分析，这是一个需要详细解释的问题。"""

    def _mock_comparison(self, question: str) -> str:
        """模拟对比类推理"""
        return f"""1. 我需要比较的对象：{question}
2. 列出比较的几个维度
3. 逐一分析各维度
4. 总结对比结果
最终答案：两者各有优势，取决于具体场景。"""

    def _mock_default(self, question: str) -> str:
        """默认模拟"""
        return f"""1. 我需要回答用户的问题：{question}
2. 分析问题的核心
3. 给出回答
最终答案：这是一个需要根据具体情况回答的问题。"""
