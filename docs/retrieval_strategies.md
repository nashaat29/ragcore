# Retrieval Strategies

RAGCore supports 4 retrieval strategies, all configurable at runtime via the API or configuration.

## 1. Simple Retrieval (`simple`)

Basic cosine similarity search using FAISS. Fastest option, suitable for straightforward queries.

```python
pipeline.set_retrieval_strategy("simple")
result = pipeline.query("What is RAG?")
```

**Config**: `top_k`, `score_threshold`

## 2. MMR Retrieval (`mmr`)

Maximum Marginal Relevance — balances relevance and diversity to avoid redundant results. Ideal for complex topics where diverse perspectives matter.

```python
pipeline.set_retrieval_strategy("mmr")
```

**Config**: `top_k`, `lambda_mult` (default: 0.5), `k_initial`

- `lambda_mult=1.0` → pure relevance (like `simple`)
- `lambda_mult=0.0` → pure diversity

## 3. Hybrid Retrieval (`hybrid`)

Combines dense (FAISS semantic) + sparse (BM25 keyword) search with weighted fusion. Best general-purpose choice for production.

```python
pipeline.set_retrieval_strategy("hybrid")
```

**Config**: `top_k`, `alpha` (default: 0.5)

- `alpha=1.0` → pure dense
- `alpha=0.0` → pure sparse (BM25)
- `alpha=0.5` → balanced

## 4. Ensemble Retrieval (`ensemble`)

Combines multiple retrievers with weighted scoring. Most robust but slowest.

```python
pipeline.set_retrieval_strategy("ensemble")
```

**Config** (via `config` dict):
```python
pipeline = RAGPipeline(config={
    "retrieval_strategy": "ensemble",
    "weights": {"simple": 0.3, "mmr": 0.2, "hybrid": 0.5},
})
```

## Switching at Runtime (API)

```json
POST /manage/retrieval/strategy?strategy=hybrid
```

```json
POST /query
{
  "question": "...",
  "retrieval_strategy": "mmr"
}
```
