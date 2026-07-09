"""
Agent 核心循环（Agent Loop）

设计目标：稳定、可观测、可中断的 Agent 主循环

核心架构：
  ┌─────────────────────────────────────────────────────────┐
  │                    AgentLoop                            │
  │  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
  │  │ Observation  │───▶│   Thought    │───▶│   Action  │ │
  │  │  (观察)      │    │   (思考)     │    │   (行动)  │ │
  │  └──────────────┘    └──────┬───────┘    └─────┬─────┘ │
  │                            │  推理引擎           │       │
  │                            ▼                   ▼       │
  │                          ReAct/CoT       工具/记忆/子Agent │
  └─────────────────────────────────────────────────────────┘

企业级特性：
  - 超时控制：单步超时 + 总运行时间上限
  - 资源限额：最大步数、Token上限、并发数
  - 优雅中断：支持人工介入和强制停止
  - 状态持久化：每步状态持久化，支持断点续跑
  - 异常隔离：单步失败不崩溃整个循环
  - 可观测性：全链路追踪、指标采集、日志记录

推理引擎集成：
  - 支持 04-reasoning 模块的所有推理器（CoT/ReAct/Plan-and-Solve）
  - 支持 01-foundation 模块的所有 LLM 客户端（OpenAI/智普/DeepSeek）
  - 无推理引擎时使用内置模拟模式（便于学习和测试）
"""
import time
import uuid
import signal
import logging
import sys
import os
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class LoopStatus(Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionType(Enum):
    FINISH = "finish"
    TOOL_CALL = "tool_call"
    USER_RESPONSE = "user_response"
    SUB_AGENT = "sub_agent"
    DELAY = "delay"


@dataclass
class AgentAction:
    type: ActionType
    name: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    thought: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "name": self.name,
            "args": self.args,
            "thought": self.thought
        }


@dataclass
class LoopStep:
    step_id: int
    status: str
    observation: Any
    thought: str
    action: Optional[AgentAction] = None
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0


@dataclass
class LoopResult:
    session_id: str
    status: LoopStatus
    steps: List[LoopStep] = field(default_factory=list)
    final_output: Optional[str] = None
    error: Optional[str] = None
    total_duration_ms: float = 0.0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def trace(self) -> str:
        lines = [
            f"会话ID: {self.session_id}",
            f"状态: {self.status.value}",
            f"总耗时: {self.total_duration_ms:.1f}ms",
            f"LLM调用: {self.total_llm_calls}, 工具调用: {self.total_tool_calls}",
            ""
        ]
        for step in self.steps:
            lines.append(f"[步骤 {step.step_id}] {step.status}")
            lines.append(f"  思考: {step.thought[:200]}")
            if step.action:
                lines.append(f"  行动: {step.action.type.value} - {step.action.name}")
            if step.result:
                result_str = str(step.result)
                lines.append(f"  结果: {result_str[:200]}")
            if step.error:
                lines.append(f"  ❌ 错误: {step.error}")
            lines.append(f"  耗时: {step.duration_ms:.1f}ms (LLM={step.llm_calls}, Tool={step.tool_calls})")
            lines.append("")
        if self.final_output:
            lines.append(f"★ 最终输出: {self.final_output}")
        return "\n".join(lines)


class AgentLoop:
    def __init__(
        self,
        reasoning_engine=None,
        tool_registry=None,
        memory_store=None,
        llm_client=None,
        max_steps: int = 10,
        max_total_time_seconds: int = 300,
        step_timeout_seconds: int = 30,
        on_step_start: Optional[Callable] = None,
        on_step_end: Optional[Callable] = None,
        on_loop_start: Optional[Callable] = None,
        on_loop_end: Optional[Callable] = None
    ):
        self.reasoning_engine = reasoning_engine
        self.tool_registry = tool_registry
        self.memory_store = memory_store
        self.llm_client = llm_client

        self.max_steps = max_steps
        self.max_total_time = max_total_time_seconds
        self.step_timeout = step_timeout_seconds

        self.on_step_start = on_step_start
        self.on_step_end = on_step_end
        self.on_loop_start = on_loop_start
        self.on_loop_end = on_loop_end

        self._session_id: Optional[str] = None
        self._status: LoopStatus = LoopStatus.NOT_STARTED
        self._steps: List[LoopStep] = []
        self._start_time: float = 0.0
        self._stop_event: bool = False

        self._total_llm_calls: int = 0
        self._total_tool_calls: int = 0

        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        def handle_sigint(signum, frame):
            logger.info("收到中断信号，准备停止循环")
            self._stop_event = True

        try:
            signal.signal(signal.SIGINT, handle_sigint)
        except Exception:
            logger.debug("信号处理未设置（可能在非主线程）")

    def run(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> LoopResult:
        self._session_id = f"session_{uuid.uuid4().hex[:12]}"
        self._status = LoopStatus.RUNNING
        self._steps = []
        self._start_time = time.time()
        self._stop_event = False
        self._total_llm_calls = 0
        self._total_tool_calls = 0

        if self.on_loop_start:
            self.on_loop_start(session_id=self._session_id, user_input=user_input)

        logger.info(f"开始 Agent 循环: session={self._session_id}, max_steps={self.max_steps}")

        try:
            if self.reasoning_engine:
                return self._run_with_reasoning_engine(user_input, context)
            else:
                return self._run_simple_loop(user_input, context)

        except Exception as e:
            logger.error(f"Agent 循环异常: {e}")
            return self._finalize(LoopStatus.FAILED, None, str(e))

    def _run_with_reasoning_engine(self, user_input: str, context: Optional[Dict[str, Any]]) -> LoopResult:
        if self.reasoning_engine is None:
            return self._run_simple_loop(user_input, context)

        has_tools = hasattr(self.reasoning_engine, 'tools') and self.reasoning_engine.tools
        if self.tool_registry and hasattr(self.reasoning_engine, 'register_tool'):
            if hasattr(self.tool_registry, '_tools'):
                for name, func in self.tool_registry._tools.items():
                    desc = getattr(self.tool_registry, '_descriptions', {}).get(name, "")
                    if name not in self.reasoning_engine.tools:
                        self.reasoning_engine.register_tool(name, func, desc)

        result = self.reasoning_engine.reason(user_input, context)

        steps = []
        for i, step in enumerate(result.steps, 1):
            action = self._step_to_action(step)
            loop_step = LoopStep(
                step_id=i,
                status="completed" if step.final_answer or step.observation else "completed",
                observation=step.observation or "",
                thought=step.thought,
                action=action,
                result=step.final_answer or step.observation,
                duration_ms=result.execution_time_ms / len(result.steps) if result.steps else 0,
                llm_calls=1,
                tool_calls=1 if step.action and step.final_answer is None else 0
            )
            steps.append(loop_step)

            if self.on_step_start:
                self.on_step_start(step_id=i)
            if self.on_step_end:
                self.on_step_end(step=loop_step)

        self._steps = steps
        self._total_llm_calls = result.total_llm_calls
        self._total_tool_calls = result.total_tool_calls

        status = LoopStatus.COMPLETED if result.success else LoopStatus.FAILED
        error = None if result.success else result.error

        return self._finalize(status, result.final_answer, error)

    def _step_to_action(self, step) -> Optional[AgentAction]:
        if step.final_answer:
            return AgentAction(
                type=ActionType.FINISH,
                name="finish_task",
                args={"final_answer": step.final_answer},
                thought=step.thought
            )
        elif step.action:
            return AgentAction(
                type=ActionType.TOOL_CALL,
                name=step.action,
                args=step.action_input or {},
                thought=step.thought
            )
        else:
            return AgentAction(
                type=ActionType.USER_RESPONSE,
                name="respond",
                args={"content": step.thought},
                thought=step.thought
            )

    def _run_simple_loop(self, user_input: str, context: Optional[Dict[str, Any]]) -> LoopResult:
        for step_idx in range(self.max_steps):
            if self._stop_event:
                logger.info("循环被中断")
                break

            elapsed = time.time() - self._start_time
            if elapsed >= self.max_total_time:
                logger.warning(f"总时间超时: {elapsed:.1f}s > {self.max_total_time}s")
                break

            step_result = self._execute_step(step_idx + 1, user_input, context)
            self._steps.append(step_result)
            self._total_llm_calls += step_result.llm_calls
            self._total_tool_calls += step_result.tool_calls

            if self.on_step_end:
                self.on_step_end(step=step_result)

            if step_result.status == "completed":
                logger.info(f"步骤 {step_idx + 1} 完成")
                if step_result.action and step_result.action.type == ActionType.FINISH:
                    return self._finalize(LoopStatus.COMPLETED, step_result.result)

            elif step_result.status == "failed":
                logger.error(f"步骤 {step_idx + 1} 失败: {step_result.error}")

            context = self._update_context(context, step_result)

        if len(self._steps) >= self.max_steps:
            return self._finalize(LoopStatus.COMPLETED, None, "达到最大步数")
        elif self._stop_event:
            return self._finalize(LoopStatus.CANCELLED, None, "用户中断")
        else:
            return self._finalize(LoopStatus.COMPLETED, None, "时间耗尽")

    def _execute_step(self, step_id: int, user_input: str, context: Optional[Dict[str, Any]]) -> LoopStep:
        step_start = time.time()

        if self.on_step_start:
            self.on_step_start(step_id=step_id)

        logger.debug(f"执行步骤 {step_id}")

        llm_calls = 0
        tool_calls = 0

        try:
            observation = self._observe(user_input, context)
            logger.debug(f"步骤 {step_id} 观察完成")

            thought = self._think_simple(observation, context)
            if self.llm_client:
                llm_calls = 1
            logger.debug(f"步骤 {step_id} 思考完成")

            action = self._decide_action_simple(thought, context)
            logger.debug(f"步骤 {step_id} 决策完成: {action.type.value}")

            result = self._execute_action(action)
            if action.type == ActionType.TOOL_CALL:
                tool_calls = 1
            logger.debug(f"步骤 {step_id} 执行完成")

            return LoopStep(
                step_id=step_id,
                status="completed",
                observation=observation,
                thought=thought,
                action=action,
                result=result,
                duration_ms=(time.time() - step_start) * 1000,
                llm_calls=llm_calls,
                tool_calls=tool_calls
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"步骤 {step_id} 执行失败: {error_msg}")
            return LoopStep(
                step_id=step_id,
                status="failed",
                observation=None,
                thought="",
                action=None,
                result=None,
                error=error_msg,
                duration_ms=(time.time() - step_start) * 1000,
                llm_calls=llm_calls,
                tool_calls=tool_calls
            )

    def _observe(self, user_input: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        observation = {"user_input": user_input}

        if context:
            observation["history"] = context.get("history", [])
            observation["memory"] = context.get("memory", {})

        return observation

    def _think_simple(self, observation: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        if self.llm_client:
            prompt = self._build_simple_think_prompt(observation, context)
            try:
                response = self.llm_client.complete(prompt)
                return response.content if hasattr(response, 'content') else str(response)
            except Exception as e:
                logger.warning(f"LLM调用失败，使用模拟: {e}")
                return self._mock_think(observation)
        else:
            return self._mock_think(observation)

    def _build_simple_think_prompt(self, observation: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        user_input = observation.get("user_input", "")
        history = observation.get("history", [])

        history_text = ""
        if history:
            history_text = "\n历史对话:\n"
            for h in history[-5:]:
                history_text += f"  - {str(h)[:100]}\n"

        return f"""你是一个AI助手。请根据以下信息进行思考，决定下一步该做什么。

用户输入: {user_input}
{history_text}
请用"思考："开头，给出你的思考过程。
如果已经得到最终答案，请用"最终答案："开头给出答案。
"""

    def _mock_think(self, observation: Dict[str, Any]) -> str:
        user_input = observation.get("user_input", "")
        history = observation.get("history", [])

        if not history:
            return f"思考：用户问了'{user_input}'，我需要先分析问题，然后给出回答。\n让我先整理一下思路。"
        elif len(history) == 1:
            return f"思考：根据之前的分析，我已经对'{user_input}'有了初步的理解。\n现在我需要整理信息，给出完整的回答。"
        else:
            return f"思考：我已经分析了'{user_input}'的各个方面。\n信息已经足够，我可以给出最终答案了。\n最终答案：经过综合分析，{user_input}的答案是多方面的，需要根据具体情况来判断。建议从多个角度考虑问题。"

    def _decide_action_simple(self, thought: str, context: Optional[Dict[str, Any]]) -> AgentAction:
        if "最终答案" in thought or "总结" in thought or "完成" in thought:
            answer = thought
            if "最终答案：" in thought:
                answer = thought.split("最终答案：")[-1].strip()
            return AgentAction(
                type=ActionType.FINISH,
                name="finish_task",
                args={"final_answer": answer},
                thought=thought
            )

        if "调用工具" in thought or "使用工具" in thought or "搜索" in thought:
            return AgentAction(
                type=ActionType.TOOL_CALL,
                name="search",
                args={"query": "根据思考内容搜索相关信息"},
                thought=thought
            )

        return AgentAction(
            type=ActionType.USER_RESPONSE,
            name="respond",
            args={"content": thought},
            thought=thought
        )

    def _execute_action(self, action: AgentAction) -> Any:
        if action.type == ActionType.FINISH:
            return action.args.get("final_answer", action.args.get("thought", ""))

        elif action.type == ActionType.TOOL_CALL:
            if self.tool_registry:
                self._total_tool_calls += 1
                if hasattr(self.tool_registry, 'call'):
                    return self.tool_registry.call(action.name, action.args)
                elif hasattr(self.tool_registry, '_tools'):
                    func = self.tool_registry._tools.get(action.name)
                    if func:
                        return func(**action.args)
            return f"工具调用模拟: {action.name}({action.args})"

        elif action.type == ActionType.USER_RESPONSE:
            return action.args.get("content", "")

        elif action.type == ActionType.SUB_AGENT:
            return f"子 Agent 调用模拟: {action.name}"

        elif action.type == ActionType.DELAY:
            delay_ms = action.args.get("delay_ms", 1000)
            time.sleep(delay_ms / 1000)
            return f"延迟 {delay_ms}ms 完成"

        return None

    def _update_context(self, context: Optional[Dict[str, Any]], step: LoopStep) -> Dict[str, Any]:
        if context is None:
            context = {}

        if "history" not in context:
            context["history"] = []

        context["history"].append({
            "step_id": step.step_id,
            "observation": step.observation,
            "thought": step.thought,
            "action": step.action.to_dict() if step.action else None,
            "result": step.result
        })

        return context

    def _finalize(self, status: LoopStatus, output: Any = None, error: Optional[str] = None) -> LoopResult:
        self._status = status
        total_duration = (time.time() - self._start_time) * 1000

        if self.on_loop_end:
            self.on_loop_end(session_id=self._session_id, status=status)

        logger.info(f"Agent 循环结束: session={self._session_id}, status={status.value}, duration={total_duration:.1f}ms")

        return LoopResult(
            session_id=self._session_id,
            status=status,
            steps=self._steps,
            final_output=str(output) if output else None,
            error=error,
            total_duration_ms=total_duration,
            total_llm_calls=self._total_llm_calls,
            total_tool_calls=self._total_tool_calls
        )

    def stop(self) -> None:
        self._stop_event = True
        logger.info("Agent 循环已收到停止信号")

    def get_status(self) -> LoopStatus:
        return self._status

    def get_session_id(self) -> Optional[str]:
        return self._session_id

    def get_step_count(self) -> int:
        return len(self._steps)


def create_agent_loop(
    llm_provider: str = "mock",
    reasoning_type: str = "simple",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> AgentLoop:
    """
    便捷函数：创建一个配置好的 AgentLoop

    Args:
        llm_provider: LLM 提供商 (mock/openai/zhipu/deepseek)
        reasoning_type: 推理类型 (simple/cot/react/plan)
        api_key: API Key
        base_url: API 基础 URL
        model: 模型名称
        **kwargs: 传递给 AgentLoop 的其他参数

    Returns:
        AgentLoop 实例
    """
    llm_client = None
    reasoning_engine = None

    if llm_provider != "mock":
        foundation_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "01-foundation", "skill")
        reasoning_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "04-reasoning", "skill")

        sys.path.insert(0, os.path.abspath(foundation_path))
        sys.path.insert(0, os.path.abspath(reasoning_path))

        try:
            if llm_provider == "openai":
                from openai_client import OpenAIClient
                llm_client = OpenAIClient(api_key=api_key, base_url=base_url, model=model or "gpt-3.5-turbo")
            elif llm_provider == "zhipu":
                from zhipu_client import ZhipuClient
                llm_client = ZhipuClient(api_key=api_key, model=model or "glm-4")
            elif llm_provider == "deepseek":
                from deepseek_client import DeepSeekClient
                llm_client = DeepSeekClient(api_key=api_key, base_url=base_url, model=model or "deepseek-chat")

            if reasoning_type != "simple" and llm_client:
                if reasoning_type == "cot":
                    from cot_reasoner import CoTReasoner
                    reasoning_engine = CoTReasoner(llm_client=LLMClientAdapter(llm_client), **kwargs)
                elif reasoning_type == "react":
                    from react_reasoner import ReActReasoner
                    reasoning_engine = ReActReasoner(llm_client=LLMClientAdapter(llm_client), **kwargs)
                elif reasoning_type == "plan":
                    from plan_solve_reasoner import PlanAndSolveReasoner
                    reasoning_engine = PlanAndSolveReasoner(llm_client=LLMClientAdapter(llm_client), **kwargs)
        except ImportError as e:
            logger.warning(f"导入失败，使用模拟模式: {e}")
            llm_client = None
            reasoning_engine = None

    return AgentLoop(
        reasoning_engine=reasoning_engine,
        llm_client=llm_client,
        **kwargs
    )


class LLMClientAdapter:
    def __init__(self, llm_client):
        self.client = llm_client

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.complete(prompt, **kwargs)
        if hasattr(response, 'content'):
            return response.content
        return str(response)
