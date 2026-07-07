# 02-tool-use - 工具使用模块

## 概述

本模块实现了一个完整的工具使用框架，包括：

1. **意图识别** - 分析用户输入，提取意图和槽位信息
2. **信息补全** - 多轮对话补齐缺失参数
3. **工具调用** - 执行注册的工具函数
4. **路由选择** - 根据意图路由到对应的Skill和工具

## 核心组件

### 1. ToolRegistry (工具注册器)

- **文件**: `skill/tool_registry.py`
- **功能**: 管理工具的注册、卸载、查询
- **特性**: 支持参数自动推断

```python
from skill import tool_registry

def get_weather(city: str) -> str:
    return f"{city}天气晴朗"

tool_registry.register_tool(
    name="get_weather",
    func=get_weather,
    description="查询天气",
    parameters={"city": {"type": "str", "required": True}}
)
```

### 2. SkillManager (技能管理器)

- **文件**: `skill/skill_manager.py`
- **功能**: 管理Skill的注册、卸载、查询
- **特性**: 支持按意图/工具查询关联Skill

```python
from skill import skill_manager

class WeatherSkill:
    def process(self, city: str) -> str:
        return f"WeatherSkill处理: {city}"

skill_manager.register_skill(
    name="weather_skill",
    skill_instance=WeatherSkill(),
    description="天气查询技能",
    required_tools=["get_weather"],
    supported_intents=["weather"]
)
```

### 3. PromptManager (Prompt管理器)

- **文件**: `skill/prompt_manager.py`
- **功能**: 管理Prompt模板的注册、渲染
- **内置Prompt**: `intent_recognition` - 意图识别模板

```python
from skill import prompt_manager

prompt_manager.register_prompt(
    name="my_prompt",
    template="Hello {name}",
    required_vars=["name"]
)

rendered = prompt_manager.render_prompt("my_prompt", name="World")
```

### 4. IntentRecognizer (意图识别器)

- **文件**: `skill/intent_recognizer.py`
- **功能**: 分析用户输入，输出结构化意图分析结果
- **输出结构**:
  - `intent`: 主意图、次意图、是否新话题
  - `provided_info`: 已提供槽位、原始提及
  - `missing_info`: 缺失参数（必需/可选）、歧义字段
  - `confidence`: 置信度（综合/意图/槽位）
  - `execution`: 是否可执行、下一步动作、建议回复

```python
from skill import intent_recognizer

analysis = intent_recognizer.recognize(
    user_message="查北京天气",
    conversation_history=[],
    available_skills=["weather", "book_flight"]
)

print(analysis.intent.get("primary"))      # weather
print(analysis.execution.get("can_proceed")) # True
```

### 5. ToolExecutor (工具执行器)

- **文件**: `skill/tool_executor.py`
- **功能**: 执行已注册的工具
- **特性**: 参数校验、错误处理

```python
from skill import tool_executor

result = tool_executor.execute("get_weather", city="北京")
print(result.success)  # True
print(result.result)   # 北京天气晴朗
```

### 6. Router (路由选择器)

- **文件**: `skill/router.py`
- **功能**: 根据意图路由到对应的Skill和工具
- **特性**: 路由验证、置信度传递

```python
from skill import router

router.register_route(
    intent="weather",
    skill_name="weather_skill",
    prompt_name="intent_recognition",
    tool_names=["get_weather"]
)

route = router.route(intent_analysis)
print(route.skill_name)  # weather_skill
```

## Demo 列表

| Demo | 文件 | 说明 |
|------|------|------|
| Demo 1 | `demo/01_simple_tool_call.py` | 简单工具调用 |
| Demo 2 | `demo/02_intent_recognition.py` | 意图识别 |
| Demo 3 | `demo/03_multi_round_info_completion.py` | 多轮信息补全 |
| Demo 4 | `demo/04_skill_tool_router.py` | Skill和工具路由 |
| Demo 5 | `demo/05_advanced_management.py` | 进阶管理功能 |

## 运行 Demo

```bash
cd /workspace/02-tool-use

# 运行简单工具调用
python demo/01_simple_tool_call.py

# 运行意图识别
python demo/02_intent_recognition.py

# 运行多轮信息补全
python demo/03_multi_round_info_completion.py

# 运行Skill和工具路由
python demo/04_skill_tool_router.py

# 运行进阶管理功能
python demo/05_advanced_management.py
```

## 完整流程

```
用户输入 → IntentRecognizer → 意图分析
                                    ↓
                           信息完整？──否──→ 追问用户
                              ↓是
                           Router → 路由选择
                                    ↓
                           Skill + Tool → 执行
                                    ↓
                              返回结果
```

## 设计要点

### 意图识别维度

| 维度 | 作用 |
|------|------|
| intent | 回答"用户想办什么" |
| provided_info | 回答"已经给了哪些信息" |
| missing_info | 回答"还缺哪些信息"，含歧义检测 |
| confidence | 回答"置信度够不够"，含分级和理由 |
| execution | 回答"能不能继续执行"，含下一步动作 |

### 置信度分级

- **high**: ≥0.85
- **medium**: 0.6-0.85
- **low**: <0.6

### 下一步动作

- **execute**: 信息充分，直接执行
- **ask_user**: 缺少必要信息，需追问
- **clarify**: 信息有歧义，需确认
- **escalate**: 超出能力范围，转人工

## 扩展建议

1. **接入真实LLM**: 在 `IntentRecognizer` 中接入真实LLM客户端替代mock实现
2. **动态工具加载**: 支持从配置文件动态加载工具和Skill
3. **权限控制**: 在Skill和工具注册时添加权限校验
4. **监控日志**: 为工具调用添加详细日志记录
5. **缓存机制**: 对重复查询结果进行缓存优化