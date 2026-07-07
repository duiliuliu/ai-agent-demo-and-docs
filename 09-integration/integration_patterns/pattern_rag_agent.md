# 整合模式：RAG Agent

## 适用场景

需要基于企业私有知识回答用户问题的场景，如内部合规问答、产品知识库、技术文档助手。

## 参与的 skill

- `01-foundation/skill/base_llm_client`
- `03-memory/skill/vector_memory`
- `08-enterprise/skill/rag_pipeline`
- `08-enterprise/skill/enterprise_guard`

## 组合方式

```
用户输入
  -> enterprise_guard.filter_input（安全过滤）
  -> rag_pipeline.retrieve（从知识库召回相关片段）
  -> base_llm_client.complete（将召回片段作为上下文，生成回答）
  -> enterprise_guard.filter_output（合规检查）
  -> 返回用户
```

## 接口契约

1. `rag_pipeline.retrieve(query: str, top_k: int) -> List[Document]` 必须返回带 `source` 字段的文档，用于溯源。
2. `base_llm_client.complete` 的 prompt 模板必须包含 `context` 和 `question` 占位符，禁止将召回内容直接拼接到用户输入中而不加隔离标记。
3. `enterprise_guard.filter_output` 对未引用来源的断言性回答应标记为 "需人工复核"。

## 企业注意点

- 知识库更新后，向量索引重建期间应提供降级方案（如返回旧索引 + 更新提示）。
- 对高敏感领域（医疗、法律），RAG 召回结果必须由人工审核后才能作为最终答案。
