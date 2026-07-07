import time
import requests
from .base_llm_client import BaseLLMClient, LLMResponse, StreamChunk
from .config_manager import LLMConfig
from typing import Iterator, Callable


class RetryClient(BaseLLMClient):
    """
    带重试和超时的 LLM 客户端装饰器。
    包装任意 BaseLLMClient 实现，添加：
    1. 超时控制
    2. 指数退避重试
    3. Token 预算管理
    """
    
    def __init__(self, client: BaseLLMClient, config: LLMConfig):
        """
        Args:
            client: 被包装的 LLM 客户端
            config: 配置，包含超时、重试次数、Token 预算等
        """
        self.client = client
        self.config = config
        self.token_used = 0
        self.budget_warning_triggered = False
    
    def _check_budget(self, tokens: int) -> bool:
        """
        检查 Token 预算，超过阈值时发出警告
        
        Args:
            tokens: 本次调用预计消耗的 Token 数
        
        Returns:
            bool: 是否允许继续调用
        """
        new_total = self.token_used + tokens
        
        if new_total >= self.config.token_budget:
            print(f"[预算告警] Token 预算已耗尽！当前: {self.token_used}, 新增: {tokens}, 预算: {self.config.token_budget}")
            return False
        
        threshold = self.config.token_budget * self.config.token_budget_warning_threshold
        if new_total >= threshold and not self.budget_warning_triggered:
            print(f"[预算告警] Token 使用接近阈值！当前: {self.token_used}, 新增: {tokens}, 阈值: {int(threshold)}, 预算: {self.config.token_budget}")
            self.budget_warning_triggered = True
        
        return True
    
    def _retry(self, func: Callable[[], LLMResponse]) -> LLMResponse:
        """
        带重试的执行函数
        
        Args:
            func: 要执行的函数
        
        Returns:
            LLMResponse: 执行结果
        
        Raises:
            Exception: 所有重试失败后抛出最后一次异常
        """
        last_exception = None
        
        for attempt in range(1, self.config.max_retries + 1):
            try:
                with requests.Session() as session:
                    session.timeout = self.config.timeout
                    result = func()
                    self.token_used += result.total_tokens
                    return result
            except requests.Timeout:
                last_exception = Exception(f"请求超时 (第 {attempt} 次尝试)")
            except requests.ConnectionError:
                last_exception = Exception(f"连接错误 (第 {attempt} 次尝试)")
            except Exception as e:
                last_exception = e
            
            if attempt < self.config.max_retries:
                backoff = 2 ** (attempt - 1)
                print(f"[重试] 第 {attempt} 次失败，等待 {backoff} 秒后重试...")
                time.sleep(backoff)
        
        raise last_exception or Exception("未知错误")
    
    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        # 预检查预算（粗略估计）
        estimated_tokens = len(prompt) // 4 + 100
        if not self._check_budget(estimated_tokens):
            raise Exception("Token 预算已耗尽")
        
        def call_func():
            return self.client.complete(prompt, **kwargs)
        
        return self._retry(call_func)

    def stream(self, prompt: str, **kwargs) -> Iterator[StreamChunk]:
        # 预检查预算
        estimated_tokens = len(prompt) // 4 + 100
        if not self._check_budget(estimated_tokens):
            raise Exception("Token 预算已耗尽")
        
        token_count = 0
        for chunk in self.client.stream(prompt, **kwargs):
            token_count += 1
            yield chunk
        
        self.token_used += token_count + (len(prompt) // 4)
        return

    def get_supported_models(self) -> list[str]:
        return self.client.get_supported_models()

    def get_budget_status(self) -> dict:
        """
        获取当前预算状态
        
        Returns:
            dict: 预算状态信息
        """
        return {
            "used": self.token_used,
            "budget": self.config.token_budget,
            "remaining": self.config.token_budget - self.token_used,
            "percentage": (self.token_used / self.config.token_budget) * 100,
            "warning_triggered": self.budget_warning_triggered,
        }
