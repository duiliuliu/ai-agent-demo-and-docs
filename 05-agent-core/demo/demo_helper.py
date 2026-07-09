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


def create_agent_loop(**kwargs):
    """
    创建 AgentLoop 实例，自动集成前面章节的 LLM 和推理引擎

    环境变量优先级高于传入参数
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "01-foundation", "skill"))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "04-reasoning", "skill"))

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
            if provider == "openai":
                from openai_client import OpenAIClient
                llm_client = OpenAIClient(
                    api_key=api_key or None,
                    base_url=base_url or None,
                    model=model or "gpt-3.5-turbo"
                )
            elif provider == "zhipu":
                from zhipu_client import ZhipuClient
                llm_client = ZhipuClient(
                    api_key=api_key or None,
                    model=model or "glm-4"
                )
            elif provider == "deepseek":
                from deepseek_client import DeepSeekClient
                llm_client = DeepSeekClient(
                    api_key=api_key or None,
                    base_url=base_url or None,
                    model=model or "deepseek-chat"
                )

            if reasoning_type != "simple" and llm_client:
                from cot_reasoner import CoTReasoner
                from react_reasoner import ReActReasoner
                from plan_solve_reasoner import PlanAndSolveReasoner

                adapter = _LLMClientAdapter(llm_client)

                if reasoning_type == "cot":
                    reasoning_engine = CoTReasoner(llm_client=adapter)
                elif reasoning_type == "react":
                    reasoning_engine = ReActReasoner(llm_client=adapter)
                elif reasoning_type == "plan":
                    reasoning_engine = PlanAndSolveReasoner(llm_client=adapter)

        except ImportError as e:
            print(f"[警告] 导入 LLM 模块失败，使用模拟模式: {e}")
            llm_client = None
            reasoning_engine = None
        except Exception as e:
            print(f"[警告] 初始化 LLM 失败，使用模拟模式: {e}")
            llm_client = None
            reasoning_engine = None

    from skill.agent_loop import AgentLoop

    return AgentLoop(
        reasoning_engine=reasoning_engine,
        llm_client=llm_client,
        **kwargs
    )


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
