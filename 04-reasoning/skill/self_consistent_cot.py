"""
自一致 CoT 与反思机制（Self-Consistent CoT + Reflection）

解决核心问题：CoT 一旦方向偏了，结果会越来越偏

设计三种增强策略：
  A. Self-Consistency（自一致投票）：
     - 对同一问题采样 N 次 CoT
     - 提取所有最终答案，按出现频率投票
     - 选得票最高的答案

  B. Self-Reflection（自我反思）：
     - 第一次 CoT 得到答案
     - 让 LLM 评估："这个推理过程有错误吗？"
     - 若发现错误，第二次 CoT 要求"避免之前的错误"
     - 循环直到通过评估或达到最大反思次数

  C. Multi-Agent Debate（多角色辩论）：
     - Agent A：提出推理和答案（Proposer）
     - Agent B：批判性审查 Agent A 的推理（Critic）
     - Agent A 根据批评修正推理
     - 循环直到达成共识
"""
import re
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .base_reasoner import BaseReasoner, ReasoningType, Step, ReasoningResult
from .cot_reasoner import CoTReasoner


@dataclass
class CotPath:
    path_id: int
    steps: List[Step] = field(default_factory=list)
    final_answer: str = ""
    confidence: float = 0.0


@dataclass
class SelfConsistentResult(ReasoningResult):
    paths: List[CotPath] = field(default_factory=list)
    vote_distribution: Dict[str, int] = field(default_factory=dict)
    selected_path_id: int = -1
    reflection_rounds: int = 0
    debate_rounds: int = 0

    def trace(self) -> str:
        lines = [
            f"推理类型: {self.reasoning_type.value} (自一致 CoT)",
            f"采样路径数: {len(self.paths)}",
            f"投票分布: {self.vote_distribution}",
            f"选中路径: #{self.selected_path_id}",
            f"反思轮数: {self.reflection_rounds}",
            f"辩论轮数: {self.debate_rounds}",
            ""
        ]
        for path in self.paths:
            lines.append(f"--- 路径 #{path.path_id} (confidence={path.confidence:.2f}) ---")
            for step in path.steps:
                lines.append(f"  Step {step.step_id}: {step.thought[:100]}")
            lines.append(f"  答案: {path.final_answer}")
            lines.append("")
        lines.append(f"★ 最终答案: {self.final_answer}")
        return "\n".join(lines)


class SelfConsistentCoT(BaseReasoner):
    def __init__(
        self,
        llm_client=None,
        num_samples: int = 3,
        max_reflection_rounds: int = 2,
        max_debate_rounds: int = 2,
        consistency_threshold: float = 0.6
    ):
        super().__init__(llm_client)
        self.num_samples = num_samples
        self.max_reflection_rounds = max_reflection_rounds
        self.max_debate_rounds = max_debate_rounds
        self.consistency_threshold = consistency_threshold
        self.cot = CoTReasoner(llm_client=llm_client)

    def reason(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        mode: str = "self_consistency"
    ) -> SelfConsistentResult:
        start_time = time.time()
        result = SelfConsistentResult(
            reasoning_type=ReasoningType.COT,
            user_input=user_input
        )

        try:
            if mode == "self_consistency":
                self._run_self_consistency(user_input, context, result)
            elif mode == "reflection":
                self._run_reflection(user_input, context, result)
            elif mode == "debate":
                self._run_debate(user_input, context, result)
            else:
                result.success = False
                result.error = f"未知的模式: {mode}"
        except Exception as e:
            result.success = False
            result.error = str(e)

        result.execution_time_ms = (time.time() - start_time) * 1000
        return result

    def _run_self_consistency(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]],
        result: SelfConsistentResult
    ) -> None:
        paths = []
        answers = []

        for i in range(self.num_samples):
            variant_prompt = f"{user_input}\n\n（推理路径 #{i+1}）"
            cot_result = self.cot.reason(variant_prompt, context)

            answer = self._extract_final_answer(cot_result.final_answer or "")
            path = CotPath(
                path_id=i + 1,
                steps=cot_result.steps,
                final_answer=answer
            )
            paths.append(path)
            answers.append(answer)
            result.total_llm_calls += cot_result.total_llm_calls

        vote_dist = {}
        for ans in answers:
            vote_dist[ans] = vote_dist.get(ans, 0) + 1

        best_answer = max(vote_dist.items(), key=lambda x: x[1])
        best_count = best_answer[1]
        total = len(answers)
        confidence = best_count / total

        selected_path = None
        for path in paths:
            if path.final_answer == best_answer[0]:
                selected_path = path
                path.confidence = confidence
                break

        result.paths = paths
        result.vote_distribution = vote_dist
        result.selected_path_id = selected_path.path_id if selected_path else -1
        result.final_answer = best_answer[0]
        result.success = True

        if confidence < self.consistency_threshold:
            result.error = f"一致性不足: 最高票仅 {confidence:.0%}，建议人工复核"

    def _run_reflection(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]],
        result: SelfConsistentResult
    ) -> None:
        current_prompt = user_input
        current_answer = ""
        all_paths = []

        for round_num in range(self.max_reflection_rounds + 1):
            cot_result = self.cot.reason(current_prompt, context)
            result.total_llm_calls += cot_result.total_llm_calls

            answer = self._extract_final_answer(cot_result.final_answer or "")
            path = CotPath(
                path_id=round_num + 1,
                steps=cot_result.steps,
                final_answer=answer
            )
            all_paths.append(path)

            if round_num == 0:
                current_answer = answer

            if round_num < self.max_reflection_rounds:
                evaluation = self._evaluate_reasoning(
                    user_input, cot_result.steps, answer
                )
                result.total_llm_calls += 1

                if evaluation["has_error"]:
                    current_prompt = self._build_correction_prompt(
                        user_input, cot_result.steps, evaluation["criticism"]
                    )
                    result.reflection_rounds += 1
                else:
                    current_answer = answer
                    break
            else:
                current_answer = answer

        result.paths = all_paths
        result.final_answer = current_answer
        result.success = True

    def _evaluate_reasoning(
        self,
        question: str,
        steps: List[Step],
        answer: str
    ) -> Dict[str, Any]:
        reasoning_text = "\n".join([
            f"Step {s.step_id}: {s.thought}"
            for s in steps
        ])

        eval_prompt = f"""请批判性地评估以下推理过程。

问题：{question}

推理过程：
{reasoning_text}

最终答案：{answer}

请回答：
1. 这个推理过程有错误吗？（是/否）
2. 如果有错误，请指出错误在哪一步，并说明原因。
3. 如果没有错误，请回答"无错误"。

评估："""

        response = self.call_llm(eval_prompt)
        has_error = "是" in response[:100] or "yes" in response[:100].lower()
        if not has_error:
            has_error = "无错误" not in response and "正确" not in response

        return {
            "has_error": has_error,
            "criticism": response
        }

    def _build_correction_prompt(
        self,
        original_question: str,
        steps: List[Step],
        criticism: str
    ) -> str:
        return f"""{original_question}

注意：之前的推理中存在以下问题，请避免这些错误：
{criticism[:500]}

请重新推理："""

    def _run_debate(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]],
        result: SelfConsistentResult
    ) -> None:
        proposer_answer = ""
        proposer_reasoning = ""
        all_paths = []

        for round_num in range(self.max_debate_rounds + 1):
            if round_num == 0:
                proposer_prompt = f"""你是一位擅长推理的助手。请仔细推理以下问题：

{user_input}

请给出完整的逐步推理过程。"""
            else:
                proposer_prompt = f"""你是一位擅长推理的助手。请仔细推理以下问题：

{user_input}

在上一轮中，有批评者指出了你的推理存在以下问题：
{proposer_reasoning[:800]}

请修正这些问题，重新给出推理。"""

            cot_result = self.cot.reason(proposer_prompt, context)
            result.total_llm_calls += cot_result.total_llm_calls

            proposer_answer = self._extract_final_answer(cot_result.final_answer or "")
            proposer_reasoning_text = "\n".join([
                f"Step {s.step_id}: {s.thought}" for s in cot_result.steps
            ])

            path = CotPath(
                path_id=round_num * 2 + 1,
                steps=cot_result.steps,
                final_answer=proposer_answer
            )
            all_paths.append(path)

            if round_num < self.max_debate_rounds:
                critic_prompt = f"""你是一位严格的批评者。请审查以下推理过程，找出其中的错误、漏洞或不合理之处。

问题：{user_input}

推理过程：
{proposer_reasoning_text}

最终答案：{proposer_answer}

请详细列出所有问题（如果有）。如果没有问题，请明确说明"推理正确"。"""

                criticism = self.call_llm(critic_prompt)
                result.total_llm_calls += 1

                proposer_reasoning = criticism
                result.debate_rounds += 1

                if "推理正确" in criticism or "没有问题" in criticism:
                    break

        result.paths = all_paths
        result.final_answer = proposer_answer
        result.success = True

    def _extract_final_answer(self, text: str) -> str:
        patterns = [
            r"最终答案[：:]\s*(.+?)(?:\n|$)",
            r"答案[：:]\s*(.+?)(?:\n|$)",
            r"Answer[：:]\s*(.+?)(?:\n|$)",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return lines[-1] if lines else text.strip()

    def _mock_llm(self, prompt: str, **kwargs) -> str:
        if "请批判性地评估" in prompt or "你是一位严格的批评者" in prompt:
            return self._mock_evaluator(prompt)
        if "（推理路径" in prompt:
            return self._mock_variant_cot(prompt)
        return self.cot._mock_llm(prompt, **kwargs)

    def _mock_evaluator(self, prompt: str) -> str:
        if "1 + 1 = 3" in prompt or "明显错误" in prompt:
            return """1. 是
2. 错误在最后一步，1+1 应该等于 2，不是 3。
3. 加法计算错误。"""

        if "15 * 8" in prompt and "等于 100" in prompt:
            return """1. 是
2. 15 * 8 = 120，不是 100。
3. 乘法计算错误。"""

        return """1. 否
2. 无错误
3. 推理过程正确，逻辑清晰。"""

    def _mock_variant_cot(self, prompt: str) -> str:
        m = re.search(r"推理路径 #(\d+)", prompt)
        path_id = int(m.group(1)) if m else 1

        if path_id <= 2:
            return """让我一步步思考：
1. 首先，分析问题条件
2. 然后，应用公式
3. 最后，得到结果
最终答案：42"""
        else:
            return """让我一步步思考：
1. 首先，分析问题条件
2. 然后，应用公式（但用了不同的方法）
3. 最后，得到结果
最终答案：40"""
