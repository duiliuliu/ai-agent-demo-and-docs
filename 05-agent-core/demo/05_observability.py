"""
Demo 05: Agent 循环可观测性与监控

场景：展示如何监控 Agent 循环的执行过程
目标：理解企业级可观测性的设计和实现

核心知识点：
  1. 生命周期钩子（Hook）机制
  2. 指标采集和监控
  3. 全链路追踪
  4. 日志记录和审计

运行方式：
  python demo/05_observability.py
"""
import sys
import os
import time
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill.agent_loop import AgentLoop, LoopStep
from skill.context_manager import EnhancedContextManager


class LoopMetricsCollector:
    def __init__(self):
        self.metrics = {
            "total_sessions": 0,
            "total_steps": 0,
            "avg_step_duration_ms": 0,
            "total_llm_calls": 0,
            "total_tool_calls": 0,
            "success_rate": 0,
            "step_durations": [],
            "status_distribution": {}
        }
        self._session_start_time = 0
        self._step_count = 0
        self._success_count = 0

    def on_loop_start(self, **kwargs):
        self._session_start_time = time.time()
        self._step_count = 0
        self._success_count = 0
        self.metrics["total_sessions"] += 1
        print(f"[监控] 会话开始: session={kwargs.get('session_id')}")

    def on_loop_end(self, **kwargs):
        session_duration = (time.time() - self._session_start_time) * 1000
        status = kwargs.get("status", {}).value if hasattr(kwargs.get("status"), "value") else str(kwargs.get("status"))

        self.metrics["status_distribution"][status] = (
            self.metrics["status_distribution"].get(status, 0) + 1
        )

        if self._step_count > 0:
            self.metrics["avg_step_duration_ms"] = sum(self.metrics["step_durations"]) / len(self.metrics["step_durations"])
            self.metrics["success_rate"] = self._success_count / self._step_count

        print(f"[监控] 会话结束: session={kwargs.get('session_id')}, status={status}, duration={session_duration:.1f}ms")

    def on_step_start(self, **kwargs):
        self._step_start_time = time.time()
        print(f"[监控] 步骤开始: step_id={kwargs.get('step_id')}")

    def on_step_end(self, **kwargs):
        step: LoopStep = kwargs.get("step")
        step_duration = (time.time() - self._step_start_time) * 1000

        self.metrics["total_steps"] += 1
        self.metrics["step_durations"].append(step_duration)
        self.metrics["total_llm_calls"] += step.result.get("llm_calls", 0) if isinstance(step.result, dict) else 0
        self.metrics["total_tool_calls"] += step.result.get("tool_calls", 0) if isinstance(step.result, dict) else 0

        if step.status == "completed":
            self._success_count += 1

        print(f"[监控] 步骤结束: step_id={step.step_id}, status={step.status}, duration={step_duration:.1f}ms")

    def get_report(self) -> Dict[str, Any]:
        return {
            "总会话数": self.metrics["total_sessions"],
            "总步骤数": self.metrics["total_steps"],
            "平均步骤耗时(ms)": round(self.metrics["avg_step_duration_ms"], 1),
            "总LLM调用": self.metrics["total_llm_calls"],
            "总工具调用": self.metrics["total_tool_calls"],
            "成功率": f"{self.metrics['success_rate'] * 100:.1f}%" if self._step_count > 0 else "N/A",
            "状态分布": self.metrics["status_distribution"]
        }


class AuditLogger:
    def __init__(self):
        self.logs = []

    def log(self, level: str, message: str, **kwargs):
        log_entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            **kwargs
        }
        self.logs.append(log_entry)
        print(f"[审计][{level.upper()}] {message}")

    def get_logs(self):
        return self.logs


def demo_observability():
    print("=" * 60)
    print("Demo 05: Agent 循环可观测性与监控")
    print("=" * 60)
    print()

    metrics_collector = LoopMetricsCollector()
    audit_logger = AuditLogger()

    loop = AgentLoop(
        max_steps=3,
        on_loop_start=metrics_collector.on_loop_start,
        on_loop_end=metrics_collector.on_loop_end,
        on_step_start=metrics_collector.on_step_start,
        on_step_end=metrics_collector.on_step_end
    )

    user_input = "帮我分析一下今天的天气情况"

    print(f"用户输入: {user_input}")
    print()

    audit_logger.log("info", "开始处理用户请求", user_input=user_input)

    result = loop.run(user_input)

    audit_logger.log("info", "处理完成", session_id=result.session_id, status=result.status.value)

    print()
    print("-" * 60)
    print("执行结果:")
    print("-" * 60)
    print(result.trace())
    print()

    print("=" * 60)
    print("监控报告")
    print("=" * 60)
    report = metrics_collector.get_report()
    for key, value in report.items():
        print(f"  {key}: {value}")
    print()

    print("=" * 60)
    print("可观测性机制解析")
    print("=" * 60)
    print("""
1. 生命周期钩子（Hook）机制：
   - on_loop_start: 循环开始时触发
   - on_loop_end: 循环结束时触发
   - on_step_start: 步骤开始时触发
   - on_step_end: 步骤结束时触发
   - 用途：注入监控、日志、审计等逻辑

2. 指标采集：
   - 会话级指标：会话数、成功率、平均耗时
   - 步骤级指标：步骤数、步骤耗时、LLM调用数、工具调用数
   - 状态分布：各状态的会话数量

3. 全链路追踪：
   - 每个会话有唯一ID
   - 每步有唯一ID
   - 步骤之间有先后关系
   - 便于追踪问题和性能分析

4. 审计日志：
   - 记录关键操作和事件
   - 包含时间戳、级别、消息、上下文
   - 便于安全审计和合规检查

5. 企业级监控建议：
   - 集成 Prometheus/Grafana 进行指标可视化
   - 集成 OpenTelemetry 进行分布式追踪
   - 集成 ELK 进行日志分析
   - 设置告警规则（如成功率低于阈值时告警）

关键设计原则：
  - 可观测性应该是可插拔的（通过钩子机制）
  - 指标应该是标准化的（便于跨系统比较）
  - 日志应该是结构化的（便于机器分析）
  - 追踪应该是全链路的（从用户请求到最终响应）
  - 监控应该是实时的（便于及时发现问题）
""")


if __name__ == "__main__":
    demo_observability()
