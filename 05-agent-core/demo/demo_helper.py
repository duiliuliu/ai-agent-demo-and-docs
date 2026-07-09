"""
Demo 辅助工具：LLM 配置和环境变量读取

支持的 LLM 提供商：
  - mock: 模拟模式（默认，无需配置）
  - openai: OpenAI API
  - zhipu: 智谱AI
  - deepseek: DeepSeek

配置方式（环境变量）：
  LLM_PROVIDER: mock / openai / zhipu / deepseek
  LLM_API_KEY: API Key
  LLM_BASE_URL: API 基础 URL（可选）
  LLM_MODEL: 模型名称（可选）
  REASONING_TYPE: simple / cot / react / plan
"""
import os
import sys
import importlib.util
from typing import Optional


def get_env_config():
    """从环境变量获取 LLM 配置"""
    return {
        "provider": os.environ.get("LLM_PROVIDER", "mock"),
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "base_url": os.environ.get("LLM_BASE_URL", ""),
        "model": os.environ.get("LLM_MODEL", ""),
        "reasoning_type": os.environ.get("REASONING_TYPE", "simple")
    }


def _load_module_from_path(module_name: str, module_path: str):
    """从指定路径加载模块，避免包名冲突"""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_foundation_package():
    """加载 01-foundation 的 skill 包为 foundation_skill"""
    foundation_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "01-foundation")
    )
    skill_dir = os.path.join(foundation_root, "skill")

    if "foundation_skill" in sys.modules:
        return sys.modules["foundation_skill"]

    import types

    pkg = types.ModuleType("foundation_skill")
    pkg.__path__ = [skill_dir]
    pkg.__package__ = "foundation_skill"
    sys.modules["foundation_skill"] = pkg

    modules_to_load = [
        "base_llm_client",
        "config_manager",
        "tracer",
        "openai_client",
        "zhipu_client",
        "deepseek_client",
    ]

    for mod_name in modules_to_load:
        mod_path = os.path.join(skill_dir, f"{mod_name}.py")
        if os.path.exists(mod_path):
            spec = importlib.util.spec_from_file_location(
                f"foundation_skill.{mod_name}",
                mod_path,
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"foundation_skill.{mod_name}"] = module
            module.__package__ = "foundation_skill"
            spec.loader.exec_module(module)
            setattr(pkg, mod_name, module)

    return pkg


def _load_reasoning_package():
    """加载 04-reasoning 的 skill 包为 reasoning_skill"""
    reasoning_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "04-reasoning")
    )
    skill_dir = os.path.join(reasoning_root, "skill")

    if "reasoning_skill" in sys.modules:
        return sys.modules["reasoning_skill"]

    import types

    pkg = types.ModuleType("reasoning_skill")
    pkg.__path__ = [skill_dir]
    pkg.__package__ = "reasoning_skill"
    sys.modules["reasoning_skill"] = pkg

    modules_to_load = [
        "base_reasoner",
        "cot_reasoner",
        "react_reasoner",
        "plan_solve_reasoner",
        "self_consistent_cot",
        "hybrid_reasoner",
        "reasoning_router",
        "task_state_manager",
    ]

    for mod_name in modules_to_load:
        mod_path = os.path.join(skill_dir, f"{mod_name}.py")
        if os.path.exists(mod_path):
            spec = importlib.util.spec_from_file_location(
                f"reasoning_skill.{mod_name}",
                mod_path,
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"reasoning_skill.{mod_name}"] = module
            module.__package__ = "reasoning_skill"
            spec.loader.exec_module(module)
            setattr(pkg, mod_name, module)

    return pkg


def create_agent_loop(**kwargs):
    """
    创建 AgentLoop 实例，自动集成前面章节的 LLM 和推理引擎

    环境变量优先级高于传入参数
    """
    config = get_env_config()

    provider = kwargs.pop("llm_provider", config["provider"])
    reasoning_type = kwargs.pop("reasoning_type", config["reasoning_type"])
    api_key = kwargs.pop("api_key", config["api_key"])
    base_url = kwargs.pop("base_url", config["base_url"])
    model = kwargs.pop("model", config["model"])

    llm_client = None
    reasoning_engine = None

    if provider != "mock":
        try:
            foundation = _load_foundation_package()
            LLMConfig = foundation.config_manager.LLMConfig

            llm_config = LLMConfig(
                api_key=api_key or None,
                base_url=base_url or None,
                model=model or _default_model(provider),
            )

            if provider == "openai":
                llm_client = foundation.openai_client.OpenAIClient(llm_config)
            elif provider == "zhipu":
                llm_client = foundation.zhipu_client.ZhipuClient(llm_config)
            elif provider == "deepseek":
                llm_client = foundation.deepseek_client.DeepSeekClient(llm_config)

            if reasoning_type != "simple" and llm_client:
                reasoning = _load_reasoning_package()
                adapter = _LLMClientAdapter(llm_client)

                if reasoning_type == "cot":
                    reasoning_engine = reasoning.cot_reasoner.CoTReasoner(llm_client=adapter)
                elif reasoning_type == "react":
                    reasoning_engine = reasoning.react_reasoner.ReActReasoner(llm_client=adapter)
                elif reasoning_type == "plan":
                    reasoning_engine = reasoning.plan_solve_reasoner.PlanAndSolveReasoner(llm_client=adapter)

        except ImportError as e:
            print(f"[警告] 导入 LLM 模块失败，使用模拟模式: {e}")
            import traceback
            traceback.print_exc()
            llm_client = None
            reasoning_engine = None
        except Exception as e:
            print(f"[警告] 初始化 LLM 失败，使用模拟模式: {e}")
            import traceback
            traceback.print_exc()
            llm_client = None
            reasoning_engine = None

    from skill.agent_loop import AgentLoop

    return AgentLoop(
        reasoning_engine=reasoning_engine,
        llm_client=llm_client,
        **kwargs
    )


def _default_model(provider: str) -> str:
    models = {
        "openai": "gpt-3.5-turbo",
        "zhipu": "glm-4",
        "deepseek": "deepseek-chat",
    }
    return models.get(provider, "gpt-3.5-turbo")


class _LLMClientAdapter:
    """将 01-foundation 的 LLM 客户端适配为 04-reasoning 期望的接口"""

    def __init__(self, llm_client):
        self.client = llm_client

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.complete(prompt, **kwargs)
        if hasattr(response, 'content'):
            return response.content
        return str(response)


def print_config_info():
    """打印当前配置信息"""
    config = get_env_config()
    print("=" * 60)
    print("LLM 配置信息")
    print("=" * 60)
    print(f"  提供商: {config['provider']}")
    print(f"  推理类型: {config['reasoning_type']}")
    if config["provider"] != "mock":
        print(f"  API Key: {'已配置' if config['api_key'] else '未配置'}")
        print(f"  Base URL: {config['base_url'] or '默认'}")
        print(f"  Model: {config['model'] or '默认'}")
    print()
