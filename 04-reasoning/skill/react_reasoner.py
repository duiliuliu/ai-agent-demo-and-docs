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

## 严格输出格式

每次只输出以下两种格式之一：

### 格式A - 需要调用工具时：
Thought: <分析当前对话历史，说明下一步需要什么信息>
Action: <工具名称>
Action Input: <JSON参数>

### 格式B - 信息已充足时（直接输出最终答案）：
Thought: <分析对话历史中的Observation，确认已获得所有必要信息>
Final Answer: <基于真实Observation数据的答案>

## 关键规则

1. **检查历史再行动**：输出前必须检查【当前对话历史】中的Observation，如果已有足够数据，直接输出Final Answer
2. **禁止重复调用**：不要重复调用已经成功返回结果的工具（相同参数）
3. **禁止编造数据**：Final Answer必须基于真实的Observation，不能自己编造
4. **任务分解**：将复杂问题分解为子任务，逐个完成
5. **错误处理**：如果工具调用出错，分析错误原因，修正参数后重试，不要放弃

## 终止条件判断

当【当前对话历史】中的Observation已包含回答问题所需的**所有关键数据**时，立即输出Final Answer，不要再调用工具。

示例判断：
- 问题："比较北京和上海的天气"
- 观察：已有"北京25°C"和"上海28°C"
- 结论：数据已充足，直接输出Final Answer

## 错误处理指南

如果 Observation 中包含错误信息（以 [工具错误] 或 [工具执行错误] 开头），请：
1. 仔细阅读错误信息，理解出错原因
2. 分析如何修正参数或选择其他工具
3. 修正后重新调用，不要放弃
4. 如果同一工具同一参数连续出错2次以上，尝试其他方案

常见错误及处理：
- 参数类型错误：检查工具参数应该是单个值，不是列表/字典
- 参数缺失：补充必要的参数
- 工具不存在：检查工具名是否正确

## 可用工具

{tool_descriptions}

## 当前对话历史

{history}

## 用户问题

{question}

---

请分析对话历史中的Observation，判断是否已有足够数据回答问题。如果充足，输出Final Answer；否则输出下一步的Action。"""

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
        self._recent_action_inputs: List[str] = []
        self._loop_detection_window = 3
        self._tool_call_cache: Dict[str, str] = {}
        self._error_count: Dict[str, int] = {}  # 记录各工具连续出错次数

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
        self._recent_action_inputs = []
        self._tool_call_cache = {}
        self._error_count = {}
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

                # 生成当前 action 的缓存 key，用于循环检测
                action_input_str = json.dumps(action_input, sort_keys=True, ensure_ascii=False)

                # 死循环检测：相同工具 + 相同参数 才判定为循环
                if self._is_in_loop(action, action_input_str):
                    step.observation = "[系统] 检测到相同工具相同参数的重复调用，已停止"
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
                self._recent_action_inputs.append(action_input_str)

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

    def _is_in_loop(self, action: str, action_input_str: str) -> bool:
        """检测是否在死循环（相同工具 + 相同参数才算循环）"""
        if len(self._recent_actions) < self._loop_detection_window:
            return False
        
        # 检查最近 N 次是否都是相同工具 + 相同参数
        recent_pairs = list(zip(
            self._recent_actions[-self._loop_detection_window:],
            self._recent_action_inputs[-self._loop_detection_window:]
        ))
        current_pair = (action, action_input_str)
        return all(pair == current_pair for pair in recent_pairs)

    def _execute_tool(self, tool_name: str, tool_input: Dict) -> str:
        """执行工具（带缓存，防止重复调用）"""
        if tool_name not in self.tools:
            available = ", ".join(self.tools.keys())
            return f"[工具错误] 工具 '{tool_name}' 不存在。可用工具：{available}。请检查工具名是否正确。"
        
        cache_key = f"{tool_name}:{json.dumps(tool_input, sort_keys=True, ensure_ascii=False)}"
        
        if cache_key in self._tool_call_cache:
            cached = self._tool_call_cache[cache_key]
            # 如果是错误结果，不缓存，允许重试
            if not cached.startswith("[工具"):
                logger.info(f"[ReActReasoner] 检测到重复工具调用 {tool_name}，返回缓存结果")
                return cached
        
        try:
            result = self.tools[tool_name](**tool_input)
            result_str = str(result)
            self._tool_call_cache[cache_key] = result_str
            self._error_count[tool_name] = 0  # 重置错误计数
            return result_str
        except TypeError as e:
            error_msg = str(e)
            self._error_count[tool_name] = self._error_count.get(tool_name, 0) + 1
            error_count = self._error_count[tool_name]
            
            if "unhashable type: 'list'" in error_msg or "unhashable type: 'dict'" in error_msg:
                suggestion = "参数类型错误：工具期望单个值（如字符串），但传入了列表/字典。请改为单个参数调用，多次调用工具获取多个结果。"
            elif "missing" in error_msg.lower() or "required" in error_msg.lower():
                suggestion = "参数缺失：请检查工具需要哪些参数，补充完整后重试。"
            elif "unexpected keyword argument" in error_msg:
                suggestion = "参数名错误：请检查工具参数名是否正确。"
            else:
                suggestion = "参数不匹配：请检查参数格式是否符合工具要求。"
            
            return f"[工具执行错误] {suggestion} 详细信息：{error_msg} (连续出错 {error_count} 次)"
        except Exception as e:
            self._error_count[tool_name] = self._error_count.get(tool_name, 0) + 1
            error_count = self._error_count[tool_name]
            return f"[工具执行错误] 执行失败：{e} (连续出错 {error_count} 次)。请分析错误原因，修正后重试。"

    def _mock_llm(self, prompt: str, **kwargs) -> str:
        """ReAct 模拟LLM（用于无真实LLM时的测试）"""
        # 简单的模拟逻辑
        if "天气" in prompt:
            return 'Thought: 我需要查询天气\nAction: get_weather\nAction Input: {"city": "北京"}'
        return 'Thought: 我需要更多信息\nFinal Answer: 无法回答'