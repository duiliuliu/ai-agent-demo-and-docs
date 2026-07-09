# Agent 核心循环深度设计文档

## 一、架构概述

### 1.1 设计目标

Agent 核心循环是单 Agent 的运行时心脏，负责将 Observation（观察）、Thought（思考）、Action（行动）串联成一个稳定、可观测、可中断的自闭环。

**核心目标：**
- **稳定性**：异常隔离、资源限额、优雅降级
- **可观测性**：全链路追踪、指标采集、结构化日志
- **可配置性**：灵活的终止条件、可插拔的组件、自适应策略
- **可恢复性**：状态持久化、断点续跑、快照恢复

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AgentLoop 主循环                             │
│                                                                     │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│  │   Observation    │───▶│     Thought      │───▶│    Action    │  │
│  │    (观察)        │    │     (思考)       │    │   (行动)     │  │
│  │                  │    │                  │    │              │  │
│  │ • 用户输入       │    │ • 推理引擎       │    │ • 回复用户   │  │
│  │ • 工具返回       │    │ • 决策逻辑       │    │ • 调用工具   │  │
│  │ • 系统事件       │    │ • 上下文分析     │    │ • 调用子Agent│  │
│  └────────┬─────────┘    └────────┬─────────┘    └──────┬───────┘  │
│           │                       │                      │          │
│           │                       │                      ▼          │
│           │                       │           ┌──────────────────┐  │
│           │                       │           │    Environment   │  │
│           │                       │           │     (环境)       │  │
│           │                       │           └────────┬─────────┘  │
│           │                       │                      │          │
│           └───────────────────────┴──────────────────────┘          │
│                              (观察结果反馈)                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        辅助组件层                                    │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Termination      │  │ Context          │  │ Observability    │  │
│  │ Checker          │  │ Manager          │  │ Hooks            │  │
│  │                  │  │                  │  │                  │  │
│  │ • 步数上限       │  │ • 上下文管理     │  │ • 生命周期钩子   │  │
│  │ • 时间上限       │  │ • 快照管理       │  │ • 指标采集       │  │
│  │ • 成本控制       │  │ • 记忆交互       │  │ • 日志记录       │  │
│  │ • 质量阈值       │  │ • 版本管理       │  │ • 审计追踪       │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 核心组件职责

| 组件 | 职责 | 核心能力 |
|------|------|----------|
| **AgentLoop** | 主循环调度器 | OTA循环、步骤执行、异常处理 |
| **TerminationChecker** | 终止条件判定 | 多维度终止检测、智能趋势分析 |
| **ContextManager** | 上下文管理 | 状态快照、记忆交互、上下文压缩 |
| **Observability Hooks** | 可观测性 | 生命周期钩子、指标采集、审计日志 |

---

## 二、AgentLoop 核心设计

### 2.1 状态机设计

```
NOT_STARTED → RUNNING → COMPLETED
              ↓   ↓      ↓
            PAUSED FAILED CANCELLED
```

**状态转换规则：**

| 当前状态 | 触发条件 | 目标状态 |
|----------|----------|----------|
| NOT_STARTED | 调用 run() | RUNNING |
| RUNNING | 任务完成 | COMPLETED |
| RUNNING | 发生错误 | FAILED |
| RUNNING | 用户中断 | CANCELLED |
| RUNNING | 调用 pause() | PAUSED |
| PAUSED | 调用 resume() | RUNNING |
| FAILED | 调用 recover() | RUNNING |

### 2.2 步骤执行流程

每个步骤包含四个阶段：

```
Step N:
  ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
  │ Observe    │───▶│ Think      │───▶│ Decide     │───▶│ Execute    │
  │ (观察)     │    │ (思考)     │    │ (决策)     │    │ (执行)     │
  └────────────┘    └────────────┘    └────────────┘    └────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
  收集外部信息        推理引擎处理        确定行动类型        执行行动
  用户输入/工具返回   生成思考内容        finish/tool/sub    获取执行结果
```

### 2.3 异常隔离机制

**设计原则：单步失败不崩溃整个循环**

```python
def _execute_step(self, step_id, user_input, context):
    try:
        observation = self._observe(user_input, context)
        thought = self._think(observation, context)
        action = self._decide_action(thought, context)
        result = self._execute_action(action)
        return LoopStep(status="completed", ...)
    except Exception as e:
        logger.error(f"步骤 {step_id} 执行失败: {e}")
        return LoopStep(status="failed", error=str(e), ...)
```

**异常处理策略：**
1. **捕获所有异常**：防止单步异常传播到循环层面
2. **记录详细信息**：记录错误类型、错误信息、上下文
3. **继续执行**：除非配置为致命错误，否则继续下一步
4. **累计失败次数**：用于质量阈值检测

### 2.4 资源限额设计

| 资源类型 | 配置参数 | 默认值 | 用途 |
|----------|----------|--------|------|
| 步数 | max_steps | 10 | 防止无限循环 |
| 时间 | max_total_time_seconds | 300 | 防止长时间运行 |
| LLM调用 | max_llm_calls | 50 | 控制API成本 |
| 工具调用 | max_tool_calls | 20 | 控制外部依赖 |

---

## 三、TerminationChecker 深度设计

### 3.1 终止条件体系

```
                    ┌─────────────────────────────────────┐
                    │         TerminationChecker          │
                    └───────────────────┬─────────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
        ▼                               ▼                               ▼
┌───────────────┐           ┌─────────────────┐           ┌─────────────────┐
│  硬性终止     │           │    软性终止     │           │   智能终止      │
├───────────────┤           ├─────────────────┤           ├─────────────────┤
│ • 步数上限    │           │ • 成本超限      │           │ • 连续失败      │
│ • 时间上限    │           │ • LLM调用超限   │           │ • 无进展循环    │
│ • 用户中断    │           │ • 工具调用超限   │           │ • 低置信度      │
│ • 致命错误    │           │ • 质量阈值      │           │ • 重复操作      │
└───────────────┘           └─────────────────┘           └─────────────────┘
```

### 3.2 智能终止检测

**SmartTerminationChecker** 扩展了标准终止检查器，增加了进度趋势检测：

```python
def _check_progress_trend(self):
    if len(self._history) < self._trend_window:
        return TerminationReason.NONE
    
    recent_results = self._history[-self._trend_window:]
    
    # 检测连续失败
    success_rate = sum(1 for r in recent_results if r.get("success", False)) / len(recent_results)
    if success_rate == 0:
        return TerminationReason.QUALITY_THRESHOLD
    
    # 检测无进展
    has_progress = any(
        r.get("progress", 0) > 0 or r.get("new_information", False)
        for r in recent_results
    )
    if not has_progress:
        logger.warning("连续多步无进展")
    
    return TerminationReason.NONE
```

### 3.3 终止原因分类

**正常终止（预期内）：**
- `TASK_COMPLETED`：任务正常完成
- `MAX_STEPS_REACHED`：达到步数上限
- `TIME_LIMIT_EXCEEDED`：超过时间限制
- `USER_INTERRUPTED`：用户主动中断

**异常终止（需要关注）：**
- `FATAL_ERROR`：发生致命错误
- `QUALITY_THRESHOLD`：质量不达标
- `COST_LIMIT_EXCEEDED`：成本或资源超限

---

## 四、ContextManager 深度设计

### 4.1 上下文结构

```
Context = {
    "session_id": "会话唯一标识",
    "user_input": "原始用户输入",
    "history": [      # 对话历史
        {"step_id": 1, "thought": "...", "action": "...", "result": "..."},
        ...
    ],
    "memory": {       # 长期记忆
        "relevant_facts": [...],
        "previous_interactions": [...]
    },
    "config": {},     # 配置参数
    "metadata": {     # 元数据
        "created_at": "2024-01-01T00:00:00",
        "version": 1,
        "updated_at": "2024-01-01T00:00:01"
    }
}
```

### 4.2 快照机制

**快照创建时机：**
- 循环开始时（step_id=0）
- 每步执行完成后
- 循环暂停或终止时

**快照格式：**
```python
class ContextSnapshot:
    snapshot_id: str      # 快照唯一标识
    step_id: int          # 对应的步骤ID
    timestamp: str        # 创建时间
    context: Dict         # 完整上下文
    metadata: Dict        # 附加元数据
```

**持久化策略：**
- 内存缓存：最近的 N 个快照
- 磁盘持久化：所有快照序列化到文件
- 过期清理：定期清理过期快照（默认7天）

### 4.3 上下文压缩

**问题：** 随着循环进行，history 不断增长，导致上下文过大

**解决方案：**
1. **截断策略**：保留最近的 N 条记录
2. **摘要策略**：将旧记录摘要化
3. **混合策略**：保留最近详细记录 + 旧记录摘要

```python
def _compress_history(self):
    if len(self._context["history"]) <= self.max_history_length:
        return
    
    keep_count = self.max_history_length // 2
    recent = self._context["history"][-keep_count:]
    older = self._context["history"][:-keep_count]
    
    summary = self._summarize_history(older)
    
    self._context["history"] = [
        {"type": "compressed_summary", "content": summary, "original_count": len(older)}
    ] + recent
```

### 4.4 记忆交互

**加载流程：**
```
循环开始 → ContextManager.initialize() → load_from_memory() → 检索相关事实 → 注入上下文
```

**存储流程：**
```
循环结束 → 提取关键信息 → ContextManager.save_to_memory() → 存储到记忆模块
```

---

## 五、可观测性设计

### 5.1 生命周期钩子

| 钩子 | 触发时机 | 参数 | 用途 |
|------|----------|------|------|
| `on_loop_start` | 循环开始时 | session_id, user_input | 初始化监控、记录开始时间 |
| `on_loop_end` | 循环结束时 | session_id, status | 汇总指标、记录结束时间 |
| `on_step_start` | 步骤开始时 | step_id | 记录步骤开始时间 |
| `on_step_end` | 步骤结束时 | step (LoopStep) | 记录步骤耗时、状态 |

**使用示例：**
```python
metrics = LoopMetricsCollector()

loop = AgentLoop(
    on_loop_start=metrics.on_loop_start,
    on_loop_end=metrics.on_loop_end,
    on_step_start=metrics.on_step_start,
    on_step_end=metrics.on_step_end
)
```

### 5.2 指标体系

**会话级指标：**
- `total_sessions`：总会话数
- `success_rate`：会话成功率
- `avg_session_duration_ms`：平均会话耗时
- `status_distribution`：状态分布

**步骤级指标：**
- `total_steps`：总步骤数
- `avg_step_duration_ms`：平均步骤耗时
- `total_llm_calls`：总LLM调用数
- `total_tool_calls`：总工具调用数

**资源级指标：**
- `memory_usage_bytes`：内存使用量
- `token_consumption`：Token消耗
- `cost_estimate`：成本估算

### 5.3 全链路追踪

**追踪ID设计：**
- `session_id`：会话唯一标识（格式：`session_<uuid>`）
- `step_id`：步骤序号（从1开始递增）
- `trace_id`：请求追踪ID（跨服务场景）

**追踪数据：**
```
session_id: session_a1b2c3d4e5f6
step_id: 1
timestamp: 2024-01-01T00:00:01
observation: {"user_input": "..."}
thought: "..."
action: {"type": "tool_call", "name": "search", "args": {...}}
result: "..."
duration_ms: 123.45
```

---

## 六、企业工程问题与解决方案

### 6.1 超时控制

**问题：** Agent 循环可能因工具调用或 LLM 响应慢而长时间阻塞

**解决方案：**

| 超时类型 | 配置参数 | 处理策略 |
|----------|----------|----------|
| 单步超时 | `step_timeout_seconds` | 超时后跳过该步，继续下一步 |
| 总时间超时 | `max_total_time_seconds` | 超时后终止循环，返回已有结果 |
| LLM调用超时 | 独立配置 | 超时后使用降级响应 |
| 工具调用超时 | 独立配置 | 超时后记录错误，继续执行 |

**实现示例：**
```python
def _execute_action_with_timeout(self, action, timeout_seconds):
    def _execute():
        return self._execute_action(action)
    
    try:
        result = asyncio.wait_for(asyncio.to_thread(_execute), timeout=timeout_seconds)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"行动执行超时: {action.name}")
        return {"error": f"执行超时（{timeout_seconds}s）"}
```

### 6.2 并发安全

**问题：** 多线程或多进程环境下，共享状态可能导致数据不一致

**解决方案：**

1. **线程安全设计**：
   - 使用线程锁保护共享状态
   - 避免在循环执行期间修改配置

2. **进程隔离**：
   - 每个会话使用独立的 AgentLoop 实例
   - 状态持久化到磁盘，避免内存共享

3. **乐观锁**：
   - 使用 version 字段防止并发更新冲突
   - 更新前检查版本，冲突时重试

### 6.3 资源耗尽防护

**问题：** 大量并发请求可能导致资源耗尽

**解决方案：**

1. **请求限流**：
   - 使用令牌桶或漏桶算法限制并发数
   - 设置最大并发会话数

2. **内存管理**：
   - 定期清理过期上下文
   - 限制单个上下文大小

3. **降级策略**：
   - 高负载时减少推理步数
   - 高负载时使用轻量级推理引擎

### 6.4 故障恢复

**问题：** 系统崩溃或重启后，正在执行的任务会丢失

**解决方案：**

1. **状态持久化**：
   - 每步执行后自动保存快照
   - 快照包含完整上下文和状态

2. **断点续跑**：
   - 系统重启后恢复未完成的任务
   - 从最近的快照继续执行

3. **任务队列**：
   - 使用消息队列管理任务
   - 支持任务重试和死信处理

---

## 七、场景适配指南

### 7.1 场景分类与配置建议

| 场景类型 | 特点 | 推荐配置 | 注意事项 |
|----------|------|----------|----------|
| **简单问答** | 单步完成，无需工具 | `max_steps=1-3`，低超时 | 快速响应，无需复杂推理 |
| **信息检索** | 需要工具调用 | `max_steps=3-5`，中等超时 | 工具调用次数可能较多 |
| **复杂推理** | 需要多步推理 | `max_steps=5-10`，较高超时 | 可能需要多次重试 |
| **长期任务** | 耗时较长 | `max_steps=10-20`，高超时 | 需要状态持久化 |
| **实时交互** | 低延迟要求 | `max_steps=1-3`，超低超时 | 优先响应速度 |

### 7.2 示例场景：自动化运维

```
运维 Agent 工作流程：
1. Observation: 接收告警信息
2. Thought: 分析可能原因（网络、磁盘、服务宕机）
3. Action: 调用日志查询工具
4. Observation: 获取日志结果
5. Thought: 定位根因
6. Action: 调用修复工具（重启服务）
7. Observation: 修复结果
8. Thought: 验证修复成功
9. Action: finish_task
```

**配置建议：**
- `max_steps=10`：需要多步诊断和修复
- `max_time_seconds=600`：允许较长诊断时间
- `max_consecutive_failures=2`：两次失败后升级人工处理

**安全考虑：**
- 修复工具需要双重确认
- 所有操作记录审计日志
- 设置操作白名单，禁止高危操作

### 7.3 示例场景：代码生成

```
代码生成 Agent 工作流程：
1. Observation: 接收需求描述
2. Thought: 分析需求，规划代码结构
3. Action: 调用代码搜索工具（查找相似实现）
4. Observation: 获取搜索结果
5. Thought: 编写代码
6. Action: 调用代码验证工具
7. Observation: 验证结果
8. Thought: 修复问题（如果有）
9. Action: finish_task
```

**配置建议：**
- `max_steps=8`：包含搜索、编写、验证、修复
- `max_time_seconds=300`：代码生成可能耗时
- 启用智能终止检测：避免无限循环修复

---

## 八、稳定性保障

### 8.1 监控告警

**关键指标告警：**

| 指标 | 阈值 | 告警级别 |
|------|------|----------|
| 会话失败率 | > 5% | WARNING |
| 平均步骤耗时 | > 5s | WARNING |
| LLM调用失败率 | > 3% | CRITICAL |
| 内存使用率 | > 80% | WARNING |

**告警通知方式：**
- 飞书/钉钉消息通知
- 邮件通知
- 电话通知（紧急情况）

### 8.2 灰度发布

**策略：**
1. **金丝雀发布**：新功能先发布到小比例用户
2. **A/B测试**：对比新旧版本效果
3. **回滚机制**：发现问题时快速回滚

**监控重点：**
- 成功率变化
- 响应时间变化
- 资源消耗变化

### 8.3 容量规划

**计算资源需求：**
- QPS = 并发数 / 平均响应时间
- 内存需求 = 单会话内存 * 最大并发数
- LLM调用量 = QPS * 平均每会话LLM调用数

**扩展策略：**
- 水平扩展：增加实例数量
- 垂直扩展：增加单实例资源
- 缓存优化：减少重复计算

---

## 九、代码优化建议

### 9.1 性能优化

1. **异步执行**：使用 asyncio 实现异步步骤执行
2. **缓存机制**：缓存重复的推理结果
3. **批处理**：批量调用 LLM 减少网络开销

### 9.2 代码质量

1. **类型注解**：完善类型提示，提高代码可读性
2. **单元测试**：覆盖核心逻辑和边界条件
3. **文档完善**：每个模块和函数都有文档

### 9.3 架构演进

1. **插件化设计**：将推理引擎、工具、记忆模块设计为可插拔组件
2. **配置中心**：支持动态配置更新
3. **分布式追踪**：集成 OpenTelemetry 实现跨服务追踪

---

## 十、总结

Agent 核心循环是 Agent 系统的运行时心脏，其设计质量直接影响系统的稳定性、可观测性和扩展性。本文档从架构设计、组件实现、企业工程问题、场景适配等多个维度进行了深入分析，提供了完整的设计方案和最佳实践。

**核心要点：**
1. **稳定第一**：异常隔离、资源限额、优雅降级
2. **可观测**：全链路追踪、指标采集、结构化日志
3. **可恢复**：状态持久化、断点续跑、快照恢复
4. **可扩展**：插件化设计、灵活配置、自适应策略
