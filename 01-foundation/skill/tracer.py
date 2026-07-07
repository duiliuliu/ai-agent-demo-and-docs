import time
import logging
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TraceRecord:
    """
    单次 LLM 调用的追踪记录
    """
    trace_id: str
    timestamp: datetime
    provider: str
    model: str
    prompt: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    response: str
    status: str = "success"
    error: Optional[str] = None


class Tracer:
    """
    追踪器：记录每次 LLM 调用的详细信息，包括 token 消耗、延迟、日志等。
    支持输出到控制台、文件、以及后续扩展到第三方监控系统。
    """
    
    def __init__(self, enabled: bool = True, log_file: Optional[str] = None):
        self.enabled = enabled
        self.token_usage = 0
        self.call_count = 0
        self.total_latency_ms = 0
        
        self.logger = logging.getLogger("llm_tracer")
        self.logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(trace_id)s - %(message)s"
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def start(self) -> str:
        """
        开始一次追踪，生成唯一 trace_id
        
        Returns:
            str: 追踪 ID
        """
        if not self.enabled:
            return ""
        return str(uuid.uuid4())

    def record(self, trace_id: str, record: TraceRecord):
        """
        记录追踪信息
        
        Args:
            trace_id: 追踪 ID
            record: 追踪记录
        """
        if not self.enabled:
            return
            
        self.token_usage += record.total_tokens
        self.call_count += 1
        self.total_latency_ms += record.latency_ms
        
        if record.status == "success":
            self.logger.info(
                f"LLM Call - Provider: {record.provider}, "
                f"Model: {record.model}, "
                f"Tokens: {record.total_tokens} (prompt={record.prompt_tokens}, completion={record.completion_tokens}), "
                f"Latency: {record.latency_ms:.2f}ms",
                extra={"trace_id": trace_id}
            )
        else:
            self.logger.error(
                f"LLM Call Failed - Error: {record.error}",
                extra={"trace_id": trace_id}
            )

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            Dict[str, Any]: 统计信息字典
        """
        avg_latency = self.total_latency_ms / self.call_count if self.call_count > 0 else 0
        return {
            "call_count": self.call_count,
            "total_tokens": self.token_usage,
            "average_latency_ms": avg_latency,
        }

    def reset_stats(self):
        """重置统计信息"""
        self.token_usage = 0
        self.call_count = 0
        self.total_latency_ms = 0
