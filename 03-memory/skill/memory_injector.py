"""
记忆注入器（Memory Injector）

核心职责：根据 MemoryLoader 的决策，执行加载并构建最终 Prompt 上下文

工作流程：
  1. 调用 MemoryLoader.decide() 获取加载决策
  2. 按决策从各记忆源加载内容
  3. 按 Token 预算截断超量内容
  4. 按优先级拼接为结构化 Prompt 上下文

Token 截断策略：
  - 用户画像：保留完整（小而关键），超限时截断标签
  - 长期记忆：按时间倒序保留最新，超量截断最旧的
  - 向量记忆：按相似度排序保留 top-K，超量截断最低分的
  - 短期记忆：按时间正序保留全部，超量从最旧开始截断

Prompt 拼接顺序（影响 LLM 注意力）：
  用户画像 > 向量记忆 > 长期记忆 > 短期记忆
  短期记忆放最后（近因效应，LLM 对末尾内容更敏感）
"""
from typing import Dict, Any, List, Optional
from .memory_loader import MemoryLoader, LoadDecision, LoadStrategy


class MemoryInjector:
    def __init__(self, memory_manager, loader: Optional[MemoryLoader] = None):
        self.mm = memory_manager
        self.loader = loader or MemoryLoader()

    def inject(
        self,
        user_input: str,
        conversation_round: int = 0,
        is_new_session: bool = False
    ) -> Dict[str, Any]:
        """
        执行记忆加载和注入

        返回：
          {
            "context": str,           # 最终 Prompt 上下文
            "decisions": List[dict],  # 加载决策（含原因）
            "token_usage": dict,      # 各类记忆实际 Token 使用
            "total_tokens": int       # 总 Token
          }
        """
        # 获取各类记忆的条目数，供 Loader 决策
        available = {
            "short_term": self.mm.short_term.size(),
            "long_term": self.mm.long_term.size(),
            "user_profile": self.mm.user_profile.size(),
            "vector": self.mm.vector_memory.size()
        }

        decisions = self.loader.decide(
            user_input=user_input,
            conversation_round=conversation_round,
            is_new_session=is_new_session,
            available_memories=available
        )

        loaded_contexts = {}
        token_usage = {}

        for decision in decisions:
            ctx, tokens = self._execute_decision(decision, user_input)
            if ctx:
                loaded_contexts[decision.memory_type] = ctx
                token_usage[decision.memory_type] = tokens
            else:
                token_usage[decision.memory_type] = 0

        # 拼接最终 Prompt（顺序影响 LLM 注意力）
        context = self._assemble_context(loaded_contexts)

        return {
            "context": context,
            "decisions": [
                {
                    "memory_type": d.memory_type,
                    "strategy": d.strategy.value,
                    "reason": d.reason,
                    "token_budget": d.token_budget,
                    "actual_tokens": token_usage.get(d.memory_type, 0)
                }
                for d in decisions
            ],
            "token_usage": token_usage,
            "total_tokens": sum(token_usage.values())
        }

    def _execute_decision(self, decision: LoadDecision, user_input: str):
        """执行单个加载决策，返回 (context, actual_tokens)"""
        if decision.strategy == LoadStrategy.SKIP:
            return ("", 0)

        if decision.memory_type == "user_profile":
            return self._load_profile(decision)
        elif decision.memory_type == "long_term":
            return self._load_long_term(decision)
        elif decision.memory_type == "vector":
            return self._load_vector(decision, user_input)
        elif decision.memory_type == "short_term":
            return self._load_short_term(decision)
        return ("", 0)

    def _load_profile(self, decision: LoadDecision):
        """加载用户画像（CACHED 策略）"""
        # 检查缓存
        if decision.strategy == LoadStrategy.CACHED:
            cached = self.loader.get_cached_profile()
            if cached is not None:
                return (cached, self._estimate_tokens(cached))

        # 重新加载
        ctx = self.mm.user_profile.to_context()
        if ctx:
            self.loader.cache_profile(ctx)
            tokens = self._estimate_tokens(ctx)
            # 超预算时截断标签部分（保留基本信息）
            if tokens > decision.token_budget:
                ctx = self._truncate(ctx, decision.token_budget)
                tokens = self._estimate_tokens(ctx)
            return (ctx, tokens)
        return ("", 0)

    def _load_long_term(self, decision: LoadDecision):
        """加载长期记忆（PARTIAL / FULL 策略）"""
        if decision.strategy == LoadStrategy.FULL:
            limit = self.mm.long_term.size()
        else:
            limit = self.loader._partial_limit

        entries = self.mm.long_term.get_recent(limit)
        if not entries:
            return ("", 0)

        lines = []
        for e in entries:
            ts = e.timestamp.strftime("%m-%d %H:%M")
            lines.append(f"  [{ts}] {e.content}")

        ctx = "长期记忆:\n" + "\n".join(lines)
        tokens = self._estimate_tokens(ctx)

        # 超预算时从最旧开始截断
        if tokens > decision.token_budget:
            ctx = self._truncate_keep_recent(ctx, decision.token_budget)
            tokens = self._estimate_tokens(ctx)

        return (ctx, tokens)

    def _load_vector(self, decision: LoadDecision, user_input: str):
        """加载向量记忆（ON_DEMAND 策略：搜索用户输入相关内容）"""
        results = self.mm.vector_memory.search(user_input, top_k=3)
        if not results:
            return ("", 0)

        lines = ["相关记忆（向量检索）:"]
        for idx, (entry, score) in enumerate(results, 1):
            lines.append(f"  {idx}. {entry.content}")

        ctx = "\n".join(lines)
        tokens = self._estimate_tokens(ctx)

        # 超预算时减少返回条数
        if tokens > decision.token_budget:
            # 保留 top-1
            ctx = "相关记忆:\n  1. " + results[0][0].content
            tokens = self._estimate_tokens(ctx)

        return (ctx, tokens)

    def _load_short_term(self, decision: LoadDecision):
        """加载短期记忆（FULL 策略：全部注入）"""
        history = self.mm.short_term.get_conversation_history()
        if not history:
            return ("", 0)

        ctx = self.mm.short_term.to_context()
        tokens = self._estimate_tokens(ctx)

        # 超预算时从最旧开始截断
        if tokens > decision.token_budget:
            ctx = self._truncate_keep_recent(ctx, decision.token_budget)
            tokens = self._estimate_tokens(ctx)

        return (ctx, tokens)

    def _assemble_context(self, contexts: Dict[str, str]) -> str:
        """按优先级拼接最终上下文"""
        parts = []
        order = ["user_profile", "vector", "long_term", "short_term"]

        for key in order:
            if contexts.get(key):
                parts.append(contexts[key])

        return "\n\n".join(parts)

    def _estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text) / 4))

    def _truncate(self, text: str, max_tokens: int) -> str:
        """简单截断到 Token 限制"""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 3] + "..."

    def _truncate_keep_recent(self, text: str, max_tokens: int) -> str:
        """截断但保留最近的内容（从最旧行开始删除）"""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text

        lines = text.split("\n")
        while len("\n".join(lines)) > max_chars and len(lines) > 2:
            # 删除第二行（跳过标题行）
            del lines[1]
        return "\n".join(lines)
