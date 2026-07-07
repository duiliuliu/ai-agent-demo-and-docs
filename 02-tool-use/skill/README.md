# Tool Use Skill 模块

## 说明

本目录包含工具使用模块的核心技能组件。详细文档请参考上级目录的 [README.md](../README.md)。

## 文件结构

```
skill/
├── __init__.py          # 模块导出
├── tool_registry.py     # 工具注册器
├── skill_manager.py     # 技能管理器
├── prompt_manager.py    # Prompt管理器
├── intent_recognizer.py # 意图识别器
├── tool_executor.py     # 工具执行器
└── router.py            # 路由选择器
```

## 快速入门

```python
from skill import (
    tool_registry,
    skill_manager,
    prompt_manager,
    intent_recognizer,
    tool_executor,
    router
)
```

## 核心组件

1. **ToolRegistry**: 工具的注册、卸载、查询
2. **SkillManager**: Skill的注册、卸载、查询
3. **PromptManager**: Prompt模板的注册、渲染
4. **IntentRecognizer**: 用户意图识别与分析
5. **ToolExecutor**: 工具调用执行
6. **Router**: 意图到Skill/工具的路由