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

实现要点：
  - 使用 ReAct 格式 Prompt（Few-shot 示例）
  - LLM 输出格式：Thought: / Action: / Action Input: / Observation:
  - 解析 LLM 输出，提取下一步行动
  - 调用工具（或模拟工具）得到 Observation
  - 循环直到输出 Final Answer 或达到最大步数
"""
import re
import time
from typing import Dict, Any, List, Optional, Callable
from .base_reasoner import BaseReasoner, ReasoningType, Step, ReasoningResult


class ReActReasoner(BaseReasoner):
    """Reasoning + Acting 推理器"""

    REACT_PROMPT_TEMPLATE = """你是一个可以使用工具的AI助手。按照以下格式思考和行动：

Thought: 你对当前情况的思考
Action: 你要执行的动作（必须是以下工具之一：{tool_names}）
Action Input: 动作参数（JSON格式）

重要规则：
1. 每次只输出一个 Thought + Action + Action Input，然后等待系统执行工具并返回 Observation
2. 绝对不要自己编造 Observation 的内容，Observation 由系统工具返回
3. 等待真实的 Observation 后再进行下一步思考
4. 当你认为已经得到足够信息时，输出：
   Thought: 我已经得到了最终答案
   Final Answer: 最终答案

可用工具：
{tool_descriptions}

{context}

问题：{question}

现在开始你的第一步思考："""

    REACT_FEWSHOT = """示例：
问题：北京和上海今天哪个城市更暖和？
Thought: 我需要查询北京和上海的天气，然后比较温度。
Action: get_weather
Action Input: {"city": "北京"}
Observation: 北京今天28度，晴
Thought: 现在查询上海的天气
Action: get_weather
Action Input: {"city": "上海"}
Observation: 上海今天32度，晴
Thought: 北京28度，上海32度，上海更暖和。
Final Answer: 上海今天更暖和（32度 vs 28度）

---

"""

    def __init__(
        self,
        llm_client=None,
        tools: Optional[Dict[str, Callable]] = None,
        tool_descriptions: Optional[Dict[str, str]] = None,
        max_steps: int = 8
    ):
        super().__init__(llm_client, max_steps)
        # 工具注册表：tool_name -> callable(input_dict) -> str
        self.tools = tools or {}
        # 工具描述：tool_name -> description
        self.tool_descriptions = tool_descriptions or {}
        # 死循环检测：最近 N 步的 action 列表
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
            # 构建初始 Prompt
            prompt = self._build_initial_prompt(user_input, context or {})

            for step_id in range(1, self.max_steps + 1):
                # 调用 LLM 思考下一步
                llm_response = self.call_llm(prompt)
                result.total_llm_calls = self.get_call_count()

                # 解析 LLM 输出
                parsed = self._parse_response(llm_response)

                step = Step(
                    step_id=step_id,
                    thought=parsed["thought"]
                )

                # 是否已得到最终答案
                if parsed["final_answer"]:
                    step.final_answer = parsed["final_answer"]
                    result.steps.append(step)
                    result.final_answer = parsed["final_answer"]
                    result.success = True
                    break

                # 否则需要执行 Action
                if parsed["action"]:
                    step.action = parsed["action"]
                    step.action_input = parsed["action_input"]

                    # 死循环检测
                    if self._is_in_loop(parsed["action"]):
                        step.observation = "[系统提示] 检测到循环，强制终止以避免无限循环"
                        result.steps.append(step)
                        result.final_answer = f"推理陷入循环，已在第{step_id}步终止"
                        result.success = False
                        result.error = "loop_detected"
                        break

                    # 执行工具
                    observation = self._execute_tool(
                        parsed["action"],
                        parsed["action_input"] or {}
                    )
                    step.observation = observation
                    result.total_tool_calls += 1
                    self._recent_actions.append(parsed["action"])

                result.steps.append(step)

                # 更新 Prompt，追加这一轮的交互
                prompt += f"\nThought: {parsed['thought']}\n"
                if parsed["action"]:
                    prompt += f"Action: {parsed['action']}\n"
                    prompt += f"Action Input: {parsed['action_input']}\n"
                    prompt += f"Observation: {step.observation}\n"

            else:
                # 循环正常结束（达到 max_steps）
                result.final_answer = result.steps[-1].thought if result.steps else "未得出结论"
                result.error = f"达到最大步数 {self.max_steps}"
                result.success = False

        except Exception as e:
            result.success = False
            result.error = str(e)

        result.execution_time_ms = (time.time() - start_time) * 1000
        return result

    def _build_initial_prompt(self, question: str, context: Dict) -> str:
        tool_names = ", ".join(self.tools.keys())
        tool_desc_lines = []
        for name, desc in self.tool_descriptions.items():
            tool_desc_lines.append(f"- {name}: {desc}")
        tool_descriptions = "\n".join(tool_desc_lines) if tool_desc_lines else "（无工具描述）"

        context_text = context.get("context", "")
        return self.REACT_PROMPT_TEMPLATE.format(
            tool_names=tool_names,
            tool_descriptions=tool_descriptions,
            context=context_text,
            question=question
        )

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应，只提取第一个 Thought/Action/Action Input 或 Final Answer"""
        result = {
            "thought": "",
            "action": None,
            "action_input": None,
            "final_answer": None
        }

        lines = response.strip().split('\n')
        first_thought = None
        first_action = None
        first_action_input = None
        first_final_answer = None

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # 只提取第一个 Thought
            if line_stripped.lower().startswith('thought:') and first_thought is None:
                first_thought = line_stripped.split(':', 1)[1].strip()

            # 只提取第一个 Action
            elif line_stripped.lower().startswith('action:') and first_action is None:
                first_action = line_stripped.split(':', 1)[1].strip()

            # 只提取第一个 Action Input
            elif line_stripped.lower().startswith('action input:') and first_action_input is None:
                input_str = line_stripped.split(':', 1)[1].strip()
                try:
                    import json
                    first_action_input = json.loads(input_str)
                except Exception:
                    first_action_input = {"raw": input_str}

            # 提取 Final Answer（这个可以覆盖，因为只应该出现一次）
            elif line_stripped.lower().startswith('final answer:'):
                first_final_answer = line_stripped.split(':', 1)[1].strip()

        # 优先级：如果有 Final Answer 且没有待执行的 Action，则返回最终答案
        if first_final_answer and not first_action:
            result["final_answer"] = first_final_answer
            if first_thought:
                result["thought"] = first_thought
            return result

        # 否则返回第一个 Thought/Action/Action Input
        result["thought"] = first_thought or ""
        result["action"] = first_action
        result["action_input"] = first_action_input

        # 如果有 Final Answer 但也有 Action，说明 LLM 编造了结果，忽略 Final Answer
        # 强制要求先执行 Action
        return result

    def _is_in_loop(self, action: str) -> bool:
        """检测是否在死循环（连续相同action）"""
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
        """ReAct 模拟LLM：智能选择工具"""
        # 提取问题
        question_match = re.search(r"问题[：:]\s*(.+?)(?:\n|$)", prompt)
        if not question_match:
            return "Thought: 我无法理解问题。\nFinal Answer: 未知"
        question = question_match.group(1).strip()

        # 检查是否已经实际有 Observation 出现（不是模板说明）
        # 模板说明是"Observation: 动作执行结果（系统会填入）"
        # 真实 Observation 后面跟的是工具返回的结果
        # 用中文逗号后的内容判断：如果 Observation 后是中文或英文具体值而非"动作执行结果"，则为真实observation
        template_pattern = r"Observation\s*[:：]\s*动作执行结果"
        has_observation = bool(re.search(template_pattern, prompt))
        # 反向：再检查是否真的出现了非模板的 observation
        all_observations = re.findall(r"Observation\s*[:：]\s*([^\n]+)", prompt)
        real_observations = [o for o in all_observations if "动作执行结果" not in o]
        if real_observations:
            has_observation = True
        else:
            has_observation = False

        # 智能选择工具
        # 天气查询（关键词：天气、weather、温度、暖和、热、凉）
        weather_signals = ["天气", "weather", "温度", "暖和", "热", "凉", "下雨", "下雪", "晴天"]
        is_weather_query = (
            any(s in question for s in weather_signals)
            or any(s in question.lower() for s in ["weather", "temperature"])
        )
        if is_weather_query:
            if "get_weather" in self.tools:
                # 提取问题中所有城市
                all_cities = self._extract_all_cities(question)
                if not all_cities:
                    all_cities = ["北京"]

                if not has_observation:
                    # 第一次：查询第一个城市
                    return f"""Thought: 我需要查询城市天气来回答问题。
Action: get_weather
Action Input: {{"city": "{all_cities[0]}"}}"""
                else:
                    # 已查询过一些城市
                    # 提取已查询的城市（兼容单/双引号）
                    queried_cities = re.findall(r"['\"]city['\"]:\s*['\"]([^'\"]+)['\"]", prompt)
                    # 是否需要继续查询（多城市比较）
                    needs_more = (
                        ("比较" in question or "哪个" in question or "vs" in question.lower() or len(all_cities) > 1)
                        and len(set(queried_cities)) < len(all_cities)
                    )
                    if needs_more:
                        # 查询下一个未查询的城市
                        for c in all_cities:
                            if c not in queried_cities:
                                return f"""Thought: 我需要继续查询{c}的天气。
Action: get_weather
Action Input: {{"city": "{c}"}}"""
                    # 已有足够信息，给出最终答案
                    return f"Thought: 我已查询到所有需要的信息，现在给出最终答案。\nFinal Answer: {self._summarize_weather(prompt)}"

        # 搜索类
        if any(kw in question for kw in ["搜索", "查", "什么是", "search", "find"]):
            if "search" in self.tools and not has_observation:
                return f"""Thought: 我需要搜索相关信息。
Action: search
Action Input: {{"query": "{question}"}}"""
            elif has_observation:
                return f"Thought: 我已搜索到相关信息。\nFinal Answer: 根据搜索结果，{self._mock_search_answer(question)}"

        # 计算类
        calc_signals = ["计算", "等于多少", "等于几", "多少钱", "总共", "总价", "乘以", "除以", "加上", "减去"]
        is_calc = (
            re.search(r"\d+\s*[+\-×x*/÷=]\s*\d+", question)
            or any(kw in question for kw in calc_signals)
        )
        if is_calc:
            if "calculator" in self.tools and not has_observation:
                # 优先提取数字运算符表达式
                expr_match = re.search(r"(\d+\s*[+\-×x*/÷]\s*\d+(?:\s*[+\-×x*/÷]\s*\d+)*)", question)
                if expr_match:
                    expr = expr_match.group(1)
                else:
                    # 中文式算式转换
                    expr = question
                    for cn, sym in [("乘以", "*"), ("乘", "*"), ("除以", "/"), ("除", "/"),
                                     ("加上", "+"), ("加", "+"), ("减去", "-"), ("减", "-")]:
                        expr = expr.replace(cn, sym)
                    # 提取数字和运算符
                    import re as _re
                    tokens = _re.findall(r"\d+|[+\-*/]", expr)
                    expr = " ".join(tokens)
                return f"""Thought: 我需要计算这个表达式。
Action: calculator
Action Input: {{"expression": "{expr}"}}"""
            elif has_observation:
                return f"Thought: 我已计算出结果。\nFinal Answer: {self._mock_calc_answer(prompt)}"

        # 默认：尝试最终答案
        if not has_observation and self.tools:
            tool_name = list(self.tools.keys())[0]
            return f"""Thought: 我尝试使用工具{tool_name}。
Action: {tool_name}
Action Input: {{"query": "{question}"}}"""

        return f"Thought: 基于已有信息回答问题。\nFinal Answer: 针对'{question}'的回答。"

    def _extract_first_city(self, question: str) -> str:
        cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安"]
        for c in cities:
            if c in question:
                return c
        return "北京"

    def _extract_all_cities(self, question: str) -> list:
        """提取问题中出现的所有城市，按问题中出现的顺序"""
        cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安"]
        result = []
        seen = set()
        # 在问题中查找每个城市出现的位置，按位置排序
        positions = []
        for c in cities:
            pos = question.find(c)
            if pos != -1 and c not in seen:
                positions.append((pos, c))
                seen.add(c)
        positions.sort()  # 按出现位置排序
        return [c for _, c in positions]

    def _summarize_weather(self, prompt: str) -> str:
        observations = re.findall(r"Observation:\s*([^\n]+)", prompt)
        if not observations:
            return "未获取到天气信息"
        return f"基于查询：{'；'.join(observations[:3])}。"

    def _mock_search_answer(self, question: str) -> str:
        return f"关于'{question}'，搜索结果显示这是相关信息。"

    def _mock_calc_answer(self, prompt: str) -> str:
        observations = re.findall(r"Observation:\s*(\d+)", prompt)
        if observations:
            return f"计算结果为 {observations[-1]}"
        return "无法计算"
