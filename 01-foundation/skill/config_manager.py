import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import json


@dataclass
class LLMConfig:
    """
    LLM 配置类，集中管理所有 LLM 相关配置。
    支持从环境变量、配置文件、代码传入等多层级加载。
    """
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 30
    max_retries: int = 3
    token_budget: int = 1000000
    token_budget_warning_threshold: float = 0.8
    trace_enabled: bool = True

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量加载配置"""
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", ""),
            model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            timeout=int(os.getenv("LLM_TIMEOUT", "30")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            token_budget=int(os.getenv("LLM_TOKEN_BUDGET", "1000000")),
            token_budget_warning_threshold=float(os.getenv("LLM_BUDGET_WARNING_THRESHOLD", "0.8")),
            trace_enabled=os.getenv("LLM_TRACE_ENABLED", "true").lower() == "true",
        )

    @classmethod
    def from_file(cls, file_path: str) -> "LLMConfig":
        """从 JSON 配置文件加载配置"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"配置文件不存在: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
        
        return cls(**config_dict)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "LLMConfig":
        """从字典加载配置"""
        return cls(**config_dict)

    def merge(self, other: "LLMConfig") -> "LLMConfig":
        """
        合并另一个配置，other 中的非空值会覆盖当前配置。
        用于实现配置分层：默认值 < 环境变量 < 配置文件 < 代码传入
        """
        result = LLMConfig()
        for field_name in LLMConfig.__dataclass_fields__.keys():
            current_value = getattr(self, field_name)
            other_value = getattr(other, field_name)
            
            if other_value != LLMConfig.__dataclass_fields__[field_name].default:
                setattr(result, field_name, other_value)
            else:
                setattr(result, field_name, current_value)
        return result
