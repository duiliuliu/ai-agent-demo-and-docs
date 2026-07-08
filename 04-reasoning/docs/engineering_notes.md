# 04-reasoning 深度问题与设计文档

## 一、推理模块的设计哲学

### 1.1 三种推理方式的本质差异

```
CoT (Chain of Thought)
  本质：单次LLM调用 + Prompt诱导分步思考
  适用：数学题、逻辑推理、简单分析
  成本：低（1次LLM调用）
  局限：无法获取外部信息、无法修正错误

ReAct (Reasoning + Acting)
  本质：思考→行动→观察 的循环
  适用：需要查询工具、多步交互、动态信息获取
  成本：中（N次LLM调用 + N次工具调用）
  优势：可与外部世界交互、可观察错误并修正

Plan-and-Solve
  本质：先制定完整计划，再逐步执行
  适用：复杂多步任务、需要预演的任务
  成本：中（规划1次 + 执行N次）
  优势：可提前发现错误、用户可审核计划
```

### 1.2 关键设计决策

**决策1：抽象出统一的Reasoner接口**
- 不同推理方式有不同的"步骤"结构
- 共同点：接收问题/输入 → 产生步骤序列 → 输出答案
- 抽象出 `BaseReasoner` 统一接口

**决策2：步骤（Step）的统一抽象**
```python
@dataclass
class Step:
    step_id: int
    thought: str
    action: Optional[str] = None          # ReAct 专用
    action_input: Optional[Dict] = None
    observation: Optional[str] = None     # ReAct 专用
    final_answer: Optional[str] = None    # 最后一步设置
```

**决策3：LLM可插拔**
- 推理本质上是LLM的Prompt工程
- LLM可替换：用模拟LLM跑Demo，用真实LLM上线
- 通过 `BaseReasoner.call_llm()` 统一接口

**决策4：与意图识别联动**
- ReasoningRouter 接收 IntentRecognizer 的输出
- 根据意图自动选择推理方式
- 工具通过 ToolRegistry 统一管理

---

## 二、深度挖掘的工程问题

### 2.1 错误恢复机制

#### 问题
- CoT：单次推理，无法修正错误
- ReAct：循环可能陷入死循环或错误循环
- Plan-and-Solve：计划可能不准确，执行可能失败

#### 解决方案

**ReAct 死循环检测**：
```python
def _is_in_loop(self, action: str) -> bool:
    """连续3步调用相同action时强制停止"""
    if len(self._recent_actions) < 3:
        return False
    return all(a == action for a in self._recent_actions[-3:])
```

**错误回退机制**（进阶）：
```python
# 1. 工具调用失败时，ReAct 重新思考
observation = "[工具错误] 工具不可用，请尝试其他方法"
prompt += f"Observation: {observation}\n"

# 2. 计划执行失败时，Plan-and-Solve 调整计划
if step_result.startswith("[错误]"):
    # 用LLM重新规划剩余步骤
    new_plan = self._replan(remaining_steps, failure_reason)
```

**最大步数限制**：
```python
self.max_steps = 8  # 防止 ReAct 无限循环
# 达到 max_steps 时强制结束
```

### 2.2 成本控制

#### 问题
- CoT：1次LLM调用 → 便宜
- ReAct：N次LLM调用 + N次工具调用 → 较贵
- Plan-and-Solve：1规划 + N执行 + 1验证 → 最贵

#### 解决方案

**按需路由**（核心）：
```python
# ReasoningRouter 决定推理方式
if intent == "greeting":     NONE          # 0次LLM
elif intent == "math":       CoT           # 1次LLM
elif intent == "weather":    ReAct         # 2-3次LLM + 1-2次工具
elif intent == "travel":     Plan-and-Solve  # 5-7次LLM
```

**成本对比示例**：
| 任务 | CoT | ReAct | Plan-and-Solve |
|------|-----|-------|----------------|
| 1+1=? | $0.001 (1次) | $0.001 (1次) | $0.003 (3次) |
| 北京天气 | $0.001 (1次,但答不出) | $0.003 (2次+1工具) | $0.005 (3次) |
| 3天旅行规划 | 答不出 | 可能答非所问 | $0.015 (5+1+1次) |

**Token优化**：
- 短期记忆只保留关键步骤
- 长期步骤摘要后入长期记忆
- 工具结果截断（防止Prompt爆炸）

### 2.3 可解释性

#### 问题
- 推理过程是黑盒的，用户难以理解
- 出错时难以定位问题
- 用户对AI决策的信任度低

#### 解决方案

**步骤追踪（trace）**：
```python
result.trace()  # 返回可读的推理轨迹
"""
推理类型: react

[步骤 1]
  思考: 我需要查询北京天气
  行动: get_weather({'city': '北京'})
  观察: 北京今天28度，晴

[步骤 2]
  思考: 我需要继续查询上海天气
  行动: get_weather({'city': '上海'})
  观察: 上海今天32度，晴

[步骤 3]
  ★ 最终答案: 上海更暖和
"""
```

**Plan-and-Solve 计划可审核**：
```python
plan = """
1. 确定旅行目的地和时间
2. 查询目的地天气
3. 规划每日行程
4. 估算预算
5. 整理最终方案
"""
# 用户可审核计划，调整后再执行
```

**可解释的决策日志**：
```python
result.metadata = {
    "intent": "weather_query",
    "reasoning_type": "react",
    "tools_used": ["get_weather"],
    "step_count": 3,
    "decision_points": [
        {"step": 1, "decision": "查询北京天气", "reason": "用户问了北京"},
        {"step": 2, "decision": "查询上海天气", "reason": "用户问了比较"},
    ]
}
```

### 2.4 工具选择正确性

#### 问题
- ReAct 中 LLM 需要选择正确的工具
- 工具描述不清晰 → 选错工具
- 工具参数理解错误 → 调用失败

#### 解决方案

**清晰的工具描述**：
```python
router.register_tool(
    "get_weather",
    get_weather,
    "查询指定城市的实时天气，返回温度和天气状况"
)
```

**Few-shot 示例引导**（进阶）：
```python
# 在 Prompt 中提供工具调用示例
REACT_FEWSHOT = """
示例：
问题：北京今天热吗？
Thought: 我需要查询北京天气
Action: get_weather
Action Input: {"city": "北京"}
...
"""
```

**工具调用校验**：
```python
# ReAct 中校验工具是否注册
if tool_name not in self.tools:
    return f"[工具错误] 工具 '{tool_name}' 未注册"

# 校验工具参数
try:
    result = self.tools[tool_name](**tool_input)
except TypeError as e:
    return f"[参数错误] {e}"
```

### 2.5 状态管理（多轮推理）

#### 问题
- 多轮对话中，推理状态如何保持
- 上一轮的工具调用结果是否影响下一轮
- 跨轮次的"已查询"信息如何传递

#### 解决方案

**会话级Reasoner**：
```python
class StatefulReActReasoner(ReActReasoner):
    def __init__(self):
        super().__init__()
        self._session_cache = {}  # 会话级缓存

    def reason(self, user_input, session_id, context=None):
        # 加载会话历史工具调用
        past_calls = self._session_cache.get(session_id, [])
        # 当前推理可以利用历史信息
        ...
        # 保存当前工具调用
        self._session_cache[session_id] = past_calls + current_calls
```

**上下文传递**：
```python
# 通过 context 传递历史信息
context = {
    "history_observations": ["北京28度", "上海32度"],
    "past_actions": [("get_weather", {"city": "北京"})]
}
result = react.reason(user_input, context=context)
```

### 2.6 超时与资源限制

#### 问题
- ReAct 可能跑很久（多步循环）
- Plan-and-Solve 计划可能很复杂
- LLM 调用可能超时

#### 解决方案

**多级限制**：
```python
# 1. 步数限制
self.max_steps = 8

# 2. 时间限制（进阶）
import signal
def timeout_handler(signum, frame):
    raise TimeoutError("推理超时")
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)  # 30秒超时
```

**降级策略**（超时后）：
```python
try:
    result = react.reason(user_input, timeout=30)
except TimeoutError:
    # 降级到 CoT（更快但能力弱）
    result = cot.reason(user_input)
```

### 2.7 结果合并与置信度

#### 问题（进阶）
- 多个推理路径可能产生不同结果
- 哪个结果更可信？
- 如何量化推理的置信度？

#### 解决方案

**多路径投票**（进阶）：
```python
# 同一个问题用3种方式推理
r1 = cot.reason(question)
r2 = react.reason(question)
r3 = plan_solve.reason(question)

# 投票决定最终答案
final_answer = majority_vote([r1.final_answer, r2.final_answer, r3.final_answer])
```

**置信度评分**：
```python
@dataclass
class ReasoningResult:
    confidence: float = 1.0  # 0-1，推理的置信度

# 计算置信度
# - CoT 答出 = 0.7
# - ReAct 工具调用成功 = 0.9
# - Plan-and-Solve 验证通过 = 0.95
```

---

## 三、生产环境的进阶方案

### 3.1 Self-Consistency（自一致性）

对同一个问题采样多次，取出现最多的答案：
```python
results = [cot.reason(question) for _ in range(5)]
final_answer = majority_vote([r.final_answer for r in results])
```

### 3.2 Tree of Thoughts（思维树）

不是线性推理，而是探索多条路径：
```python
class TreeOfThoughtsReasoner:
    def reason(self, question):
        # 1. 生成多个候选 thought
        thoughts = self._generate_thoughts(question, n=3)
        # 2. 评估每个 thought 的价值
        scores = [self._evaluate(t) for t in thoughts]
        # 3. 选择最佳路径继续
        best = thoughts[scores.index(max(scores))]
        # 4. 递归扩展
        return self._recurse(best)
```

### 3.3 Reflection（反思）

让 LLM 评估自己的输出，发现错误并重试：
```python
result = react.reason(question)
if result.confidence < 0.7:
    # 让 LLM 反思
    reflection = llm.generate(f"评估这个回答的问题：{result.final_answer}")
    # 重新推理
    result = react.reason(question, hint=reflection)
```

### 3.4 与记忆系统深度结合

```python
@dataclass
class ReasoningContext:
    user_input: str
    short_term_memory: ShortTermMemory    # 短期记忆
    long_term_memory: LongTermMemory      # 长期记忆
    entity_profile: EntityProfile         # 实体画像
    tools: Dict                          # 工具
    plan: Optional[List[str]]             # 已有计划（继续执行）

def reason_with_memory(self, user_input):
    # 1. 加载相关记忆
    context = self.memory.inject(user_input)

    # 2. 执行推理
    result = self.reasoner.reason(user_input, context=context)

    # 3. 把推理结果入长期记忆
    self.memory.add_long_term(f"用户问：{user_input}，答：{result.final_answer}")

    return result
```

---

## 四、推理模块的监控指标

### 4.1 性能指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| 推理成功率 | 完成推理的比例 | >95% |
| 平均LLM调用次数 | 每次推理调用LLM的次数 | <5 |
| 平均工具调用次数 | 每次推理调用工具的次数 | <3 |
| 推理耗时 | P50/P95/P99延迟 | <3s / <10s / <30s |
| 死循环率 | 触发死循环检测的比例 | <1% |

### 4.2 质量指标

| 指标 | 说明 |
|------|------|
| 答案准确率 | 在测试集上的正确率 |
| 工具选择正确率 | ReAct选对工具的比例 |
| 计划合理性 | Plan-and-Solve计划的合理程度 |
| 用户满意度 | 人工评估 |

### 4.3 成本指标

| 指标 | 说明 |
|------|------|
| 单次推理平均成本 | 美元 |
| 推理方式分布 | CoT/ReAct/Plan-and-Solve的比例 |
| Token使用 | 输入+输出平均Token数 |

---

## 五、与前几章的联动

### 5.1 与 01-foundation（基础）

推理模块的 LLM 调用走 BaseLLMClient，支持不同LLM切换。

### 5.2 与 02-tool-use（工具使用）

- 工具通过 ToolRegistry 统一管理
- IntentRecognizer 输出 intent → ReasoningRouter 选择推理方式
- ReAct 的 Action 直接调用工具

### 5.3 与 03-memory（记忆系统）

- 推理时加载短期记忆（当前对话）+长期记忆（历史事实）+实体画像
- 推理结果可以入长期记忆
- 长期记忆压缩避免 Prompt 爆炸

### 5.4 完整的 Agent 循环

```
用户输入
  ↓
[02] 意图识别 → intent
  ↓
[03] 记忆加载 → context (短期+长期+画像)
  ↓
[04] 推理路由 → 选择 CoT/ReAct/Plan-and-Solve
  ↓
执行推理 → result
  ↓
[02] 工具调用（如需）
  ↓
[03] 记忆更新 → 短期/长期/画像
  ↓
返回答案给用户
```
