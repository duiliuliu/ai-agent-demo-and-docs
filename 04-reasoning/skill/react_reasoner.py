"""
ReAct (Reasoning + Acting) 推理器

核心思想：
  Thought → Action → Observation → Thought → Action → ... → Final Answer
  思考、行动、观察三者循环，直到得到最终答案

适用场景：
  - 需要查询实时信息（天气、股票、新闻）
  - 需要调用工具（计算器、搜索、数据库）
  - 多步交互任务
  - 需要观察结果再决定下一步

不适用：
  - 简单直接的问题（用CoT更高效）
  - 任务极复杂需要全局规划（用Plan-and-Solve更合适）

成本：N 次 LLM 调用 + N 次工具调用
优点：可与外部世界交互、可动态决策、可修正错误
局限：可能陷入死循环、需要工具支持

工程关键问题：
  1. 死循环检测：连续几步出现相同 thought/action 时强制停止
  2. 最大步数限制：超过 max_steps 强制结束
  3. 工具调用失败处理：单步失败不应让整个推理崩溃
  4. 工具选择正确性：依赖LLM对工具的理解
  5. LLM编造数据：必须严格限制LLM只输出单步，等待工具返回

实现要点：
  - 使用 ReAct 格式 Prompt，明确要求单步输出
  - LLM 输出格式：只有 Thought + Action + Action Input
  - 解析时只取第一步，忽略LLM自编造的后续内容
  - 调用工具得到真实的 Observation
  - 循环直到输出 Final Answer 或达到最大步数
"""
import re
import time
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from .base_reasoner import BaseReasoner, ReasoningType, Step, ReasoningResult

logger = logging.getLogger(__name__)


class ReActReasoner(BaseReasoner):
    """Reasoning + Acting 推理器"""

    REACT_PROMPT_TEMPLATE = """你是一个专业的AI助手，需要通过工具获取信息并回答问题。

## 严格输出格式（每次只输出一步！）

Thought: <你对当前情况的分析，说明下一步要做什么>
Action: <工具名称，必须是以下工具之一>
Action Input: <JSON格式的参数，如 {"city": "北京"}>

## 重要规则（必须遵守）

1. **单步输出**：每次只输出一个 Thought + Action + Action Input，然后停止，等待系统返回 Observation
2. **禁止编造**：绝对不要自己填写 Observation 的内容！不要编造数据！所有数据必须来自工具返回
3. **等待结果**：输出 Action 后必须等待工具执行结果，系统会将 Observation 注入到对话中
4. **最终答案**：当工具返回的信息足够回答问题时，输出：
   Thought: 我已经获得了足够的信息来回答问题
   Final Answer: <基于工具返回数据的真实答案>

## 可用工具

{tool_descriptions}

## 当前对话历史

{history}

## 用户问题

{question}

---

现在输出你的第一步思考（只输出 Thought + Action + Action Input，不要输出 Observation）："""

    def __init__(
        self,
        llm_client=None,
        tools: Optional[Dict[str, Callable]] = None,
        tool_descriptions: Optional[Dict[str, str]] = None,
        max_steps: int = 8
    ):
        super().__init__(llm_client, max_steps)
        self.tools = tools or {}
        self.tool_descriptions = tool_descriptions or {}
        self._recent_actions: List[str] = []
        self._loop_detection_window = 3

    def register_tool(self, name: str, func: Callable, description: str = "") -> None:
        """注册工具"""
        self.tools[name] = func
        if description:
            self.tool_descriptions[name] = description

    def reason(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ReasoningResult:
        start_time = time.time()
        result = ReasoningResult(
            reasoning_type=ReasoningType.REACT,
            user_input=user_input
        )
        self._recent_actions = []
        self.reset_call_count()

        if not self.tools:
            result.success = False
            result.error = "ReAct需要至少一个工具，但当前未注册任何工具"
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result

        try:
            # 对话历史，用于多轮推理
            history_lines = []

            for step_id in range(1, self.max_steps + 1):
                # 构建 Prompt
                prompt = self._build_prompt(user_input, history_lines)

                logger.info(f"[ReActReasoner] 第 {step_id} 步，调用 LLM...")

                # 调用 LLM
                llm_response = self.call_llm(prompt)
                result.total_llm_calls = self.get_call_count()

                logger.info(f"[ReActReasoner] 第 {step_id} 步 LLM 响应:\n{llm_response}")

                # 解析 LLM 输出（只取第一步）
                parsed = self._parse_response(llm_response)

                step = Step(
                    step_id=step_id,
                    thought=parsed.get("thought", "")
                )

                # 检查是否得到最终答案
                if parsed.get("final_answer"):
                    step.final_answer = parsed["final_answer"]
                    result.steps.append(step)
                    result.final_answer = parsed["final_answer"]
                    result.success = True
                    logger.info(f"[ReActReasoner] 第 {step_id} 步得到最终答案: {parsed['final_answer']}")
                    break

                # 检查是否有 Action
                action = parsed.get("action")
                action_input = parsed.get("action_input", {})

                if not action:
                    # 没有 Action 也没有 Final Answer，可能是解析失败
                    step.observation = "[系统] 无法解析 LLM 输出，请重新思考"
                    result.steps.append(step)
                    history_lines.append(f"Thought: {parsed.get('thought', '无法解析')}")
                    history_lines.append("Observation: [系统] 无法解析输出，请重新思考")
                    continue

                step.action = action
                step.action_input = action_input

                # 死循环检测
                if self._is_in_loop(action):
                    step.observation = "[系统] 检测到循环，强制终止"
                    result.steps.append(step)
                    result.final_answer = "推理陷入循环，已终止"
                    result.success = False
                    result.error = "loop_detected"
                    break

                # 执行工具
                observation = self._execute_tool(action, action_input)
                step.observation = observation
                result.total_tool_calls += 1
                self._recent_actions.append(action)

                result.steps.append(step)

                # 更新对话历史
                history_lines.append(f"Thought: {parsed.get('thought', '')}")
                history_lines.append(f"Action: {action}")
                history_lines.append(f"Action Input: {json.dumps(action_input, ensure_ascii=False)}")
                history_lines.append(f"Observation: {observation}")
                history_lines.append("")

                logger.info(f"[ReActReasoner] 第 {step_id} 步执行工具 {action}，结果: {observation}")

            else:
                # 达到最大步数
                result.final_answer = result.steps[-1].thought if result.steps else "未得出结论"
                result.error = f"达到最大步数 {self.max_steps}"
                result.success = False

        except Exception as e:
            logger.error(f"[ReActReasoner] 执行异常: {e}")
            result.success = False
            result.error = str(e)

        result.execution_time_ms = (time.time() - start_time) * 1000
        return result

    def _build_prompt(self, question: str, history: List[str]) -> str:
        """构建 Prompt"""
        tool_names = ", ".join(self.tools.keys())
        tool_desc_lines = [f"- {name}: {desc}" for name, desc in self.tool_descriptions.items()]
        if not tool_desc_lines:
            tool_desc_lines = [f"- {name}: 工具 {name}" for name in self.tools.keys()]
        tool_descriptions = "\n".join(tool_desc_lines)

        history_text = "\n".join(history) if history else "（无历史对话，这是第一步）"

        return self.REACT_PROMPT_TEMPLATE.format(
            tool_descriptions=tool_descriptions,
            history=history_text,
            question=question
        )

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        解析 LLM 响应，只提取第一个 Thought/Action/Action Input
        
        关键：忽略 LLM 可能自编造的后续内容
        """
        result = {
            "thought": "",
            "action": None,
            "action_input": None,
            "final_answer": None
        }

        lines = response.strip().split('\n')
        found_thought = False
        found_action = False
        found_action_input = False

        for line in lines:
            line_stripped = line.strip()
            lower_line = line_stripped.lower()

            # 提取第一个 Thought
            if lower_line.startswith('thought:') and not found_thought:
                result["thought"] = line_stripped.split(':', 1)[1].strip()
                found_thought = True

            # 提取第一个 Action
            elif lower_line.startswith('action:') and not found_action:
                action_name = line_stripped.split(':', 1)[1].strip()
                # 只取工具名（去掉可能的额外文字）
                action_name = action_name.split()[0] if action_name else action_name
                result["action"] = action_name
                found_action = True

            # 提取第一个 Action Input
            elif lower_line.startswith('action input:') and not found_action_input:
                input_str = line_stripped.split(':', 1)[1].strip()
                try:
                    # 尝试解析 JSON
                    result["action_input"] = json.loads(input_str)
                except json.JSONDecodeError:
                    # 尝试修复常见的 JSON 格式问题
                    input_str = input_str.replace("'", '"')
                    try:
                        result["action_input"] = json.loads(input_str)
                    except:
                        result["action_input"] = {"raw": input_str}
                found_action_input = True

            # 提取 Final Answer（只有当没有 Action 时才算有效）
            elif lower_line.startswith('final answer:'):
                final_answer_text = line_stripped.split(':', 1)[1].strip()
                result["final_answer"] = final_answer_text

        # 如果有 Action，清空 Final Answer（强制要求先执行工具）
        if result["action"]:
            result["final_answer"] = None

        return result

    def _is_in_loop(self, action: str) -> bool:
        """检测是否在死循环"""
        if len(self._recent_actions) < self._loop_detection_window:
            return False
        recent = self._recent_actions[-self._loop_detection_window:]
        return all(a == action for a in recent)

    def _execute_tool(self, tool_name: str, tool_input: Dict) -> str:
        """执行工具"""
        if tool_name not in self.tools:
            return f"[工具错误] 工具 '{tool_name}' 未注册。可用工具: {list(self.tools.keys())}"
        try:
            result = self.tools[tool_name](tool_input)
            return str(result)
        except Exception as e:
            return f"[工具执行错误] {e}"

    def _mock_llm(self, prompt: str, **kwargs) -> str:
        """ReAct 模拟LLM（用于无真实LLM时的测试）"""
        # 简单的模拟逻辑
        if "天气" in prompt:
            return 'Thought: 我需要查询天气\nAction: get_weather\nAction Input: {"city": "北京"}'
        return 'Thought: 我需要更多信息\nFinal Answer: 无法回答'