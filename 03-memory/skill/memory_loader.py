"""
记忆加载器（Memory Loader）

核心职责：决定「什么时候加载什么记忆、以什么方式加载」

设计理念：
  不是所有记忆都每次全量加载——那样 Token 消耗巨大且噪声多。
  应根据对话上下文、意图、轮次动态决策。

加载策略（LoadStrategy）：
  FULL       — 全量加载（短期记忆：当前对话窗口全部注入）
  PARTIAL    — 部分加载（长期记忆：只取最近 N 条，不全量）
  ON_DEMAND  — 按需加载（向量记忆：仅当用户有查询意图时触发搜索）
  CACHED     — 缓存加载（用户画像：会话内只读一次，缓存复用）
  SKIP       — 跳过（条件不满足时不加载，节省 Token）

加载时序（LoadOrder）：
  1. 用户画像  → CACHED  （小而关键，最先加载）
  2. 长期记忆  → PARTIAL （取最近 N 条历史事实）
  3. 向量记忆  → ON_DEMAND（基于用户输入搜索相关记忆）
  4. 短期记忆  → FULL    （当前对话上下文，最后加载保证最新）

工程关注点：
- 向量搜索是 O(N) 的，大量记忆时需异步或预计算索引
- 用户画像缓存需考虑失效策略（用户修改偏好后需刷新）
- 短期记忆应在最后加载，确保对话上下文在 Prompt 末尾（近因效应）
"""
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class LoadStrategy(Enum):
    """记忆加载策略"""
    FULL = "full"           # 全量加载
    PARTIAL = "partial"      # 部分加载（最近 N 条）
    ON_DEMAND = "on_demand" # 按需加载（搜索触发）
    CACHED = "cached"        # 缓存加载（会话内只读一次）
    SKIP = "skip"            # 跳过不加载


@dataclass
class LoadDecision:
    """单次加载决策结果"""
    memory_type: str          # short_term / long_term / user_profile / vector
    strategy: LoadStrategy   # 加载策略
    priority: int            # 优先级（数字越小越先加载）
    token_budget: int        # 分配的 Token 预算
    reason: str              # 决策原因（可追溯）


class MemoryLoader:
    """记忆加载决策器：根据上下文决定加载哪些记忆、如何加载"""

    # 默认 Token 预算分配比例
    DEFAULT_RATIOS = {
        "short_term": 0.50,   # 50% 短期记忆
        "long_term": 0.25,    # 25% 长期记忆
        "user_profile": 0.15, # 15% 用户画像
        "vector": 0.10,       # 10% 向量记忆
    }

    # 默认部分加载数量
    DEFAULT_PARTIAL_LIMIT = 5

    def __init__(self, total_token_budget: int = 4000):
        self.total_token_budget = total_token_budget
        self._ratios = dict(self.DEFAULT_RATIOS)
        self._partial_limit = self.DEFAULT_PARTIAL_LIMIT
        self._profile_cache: Optional[str] = None  # 用户画像缓存
        self._cache_valid: bool = False

    def decide(
        self,
        user_input: str,
        conversation_round: int = 0,
        is_new_session: bool = False,
        available_memories: Optional[Dict[str, int]] = None
    ) -> List[LoadDecision]:
        """
        根据当前上下文做出加载决策

        参数：
          user_input        — 用户当前输入
          conversation_round — 当前是第几轮对话（从 0 开始）
          is_new_session    — 是否新会话开始
          available_memories — 各类记忆当前条目数，如 {"short_term": 6, "long_term": 20}

        返回：按优先级排序的 LoadDecision 列表
        """
        available = available_memories or {}
        decisions = []

        # 1. 用户画像 — CACHED（新会话时加载，后续复用缓存）
        profile_budget = int(self.total_token_budget * self._ratios["user_profile"])
        if is_new_session:
            decisions.append(LoadDecision(
                memory_type="user_profile",
                strategy=LoadStrategy.CACHED,
                priority=1,
                token_budget=profile_budget,
                reason="新会话：加载用户画像并缓存"
            ))
        elif self._cache_valid:
            decisions.append(LoadDecision(
                memory_type="user_profile",
                strategy=LoadStrategy.CACHED,
                priority=1,
                token_budget=0,  # 缓存命中，不消耗额外 Token
                reason="缓存命中：复用已加载的用户画像"
            ))
        else:
            decisions.append(LoadDecision(
                memory_type="user_profile",
                strategy=LoadStrategy.CACHED,
                priority=1,
                token_budget=profile_budget,
                reason="缓存失效：重新加载用户画像"
            ))

        # 2. 长期记忆 — PARTIAL（取最近 N 条，不全量）
        ltm_size = available.get("long_term", 0)
        ltm_budget = int(self.total_token_budget * self._ratios["long_term"])
        if ltm_size == 0:
            decisions.append(LoadDecision(
                memory_type="long_term",
                strategy=LoadStrategy.SKIP,
                priority=2,
                token_budget=0,
                reason="长期记忆为空，跳过"
            ))
        elif ltm_size <= self._partial_limit:
            decisions.append(LoadDecision(
                memory_type="long_term",
                strategy=LoadStrategy.FULL,
                priority=2,
                token_budget=ltm_budget,
                reason=f"长期记忆仅 {ltm_size} 条，全量加载"
            ))
        else:
            decisions.append(LoadDecision(
                memory_type="long_term",
                strategy=LoadStrategy.PARTIAL,
                priority=2,
                token_budget=ltm_budget,
                reason=f"长期记忆 {ltm_size} 条，部分加载最近 {self._partial_limit} 条"
            ))

        # 3. 向量记忆 — ON_DEMAND（仅当用户输入有查询意图时触发）
        vector_budget = int(self.total_token_budget * self._ratios["vector"])
        has_query_intent = self._detect_query_intent(user_input, conversation_round)
        if has_query_intent and available.get("vector", 0) > 0:
            decisions.append(LoadDecision(
                memory_type="vector",
                strategy=LoadStrategy.ON_DEMAND,
                priority=3,
                token_budget=vector_budget,
                reason="检测到查询意图，触发向量搜索"
            ))
        else:
            decisions.append(LoadDecision(
                memory_type="vector",
                strategy=LoadStrategy.SKIP,
                priority=3,
                token_budget=0,
                reason="无查询意图或向量记忆为空，跳过"
            ))

        # 4. 短期记忆 — FULL（每轮都加载，保证对话连贯性）
        stm_budget = int(self.total_token_budget * self._ratios["short_term"])
        stm_size = available.get("short_term", 0)
        if stm_size == 0:
            decisions.append(LoadDecision(
                memory_type="short_term",
                strategy=LoadStrategy.SKIP,
                priority=4,
                token_budget=0,
                reason="短期记忆为空（首轮对话），跳过"
            ))
        else:
            decisions.append(LoadDecision(
                memory_type="short_term",
                strategy=LoadStrategy.FULL,
                priority=4,
                token_budget=stm_budget,
                reason="全量加载短期记忆，确保对话连贯"
            ))

        return sorted(decisions, key=lambda d: d.priority)

    def _detect_query_intent(self, user_input: str, conversation_round: int) -> bool:
        """
        简单的查询意图检测：
        - 首轮对话（round=0）通常有明确意图
        - 包含疑问词、搜索关键词时判定为有查询意图
        - 后续轮次中如果输入较长（>10字）也认为有查询意图
        """
        if not user_input or len(user_input.strip()) < 2:
            return False

        # 首轮通常有查询意图
        if conversation_round == 0:
            return True

        # 检测疑问词/搜索意图
        query_indicators = [
            "什么", "怎么", "为什么", "哪", "谁", "多少", "是否", "能不能",
            "查", "找", "搜索", "推荐", "告诉", "帮我", "请问",
            "what", "how", "why", "where", "who", "search", "find"
        ]
        lower_input = user_input.lower()
        for indicator in query_indicators:
            if indicator in lower_input:
                return True

        # 长输入可能包含查询意图
        if len(user_input) > 15:
            return True

        return False

    def cache_profile(self, context: str) -> None:
        """缓存用户画像上下文"""
        self._profile_cache = context
        self._cache_valid = True

    def get_cached_profile(self) -> Optional[str]:
        """获取缓存的用户画像"""
        if self._cache_valid:
            return self._profile_cache
        return None

    def invalidate_cache(self) -> None:
        """使缓存失效（用户修改偏好后调用）"""
        self._cache_valid = False
        self._profile_cache = None

    def update_ratios(self, ratios: Dict[str, float]) -> None:
        """更新 Token 预算分配比例"""
        total = sum(ratios.values())
        if total > 0:
            self._ratios = {k: v / total for k, v in ratios.items()}

    def get_ratios(self) -> Dict[str, float]:
        return dict(self._ratios)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_token_budget": self.total_token_budget,
            "ratios": self._ratios,
            "partial_limit": self._partial_limit,
            "cache_valid": self._cache_valid
        }
