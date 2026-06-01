# Configuration

All settings are managed via environment variables with the `RAGCORE_` prefix.
You can use a `.env` file or set them directly in your environment.

## LLM Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_LLM_MODEL` | `frob/qwen3.5-instruct:9b` | Ollama model for generation |
| `RAGCORE_LLM_BASE_URL` | `http://127.0.0.1:11434` | Ollama server URL |
| `RAGCORE_LLM_TEMPERATURE` | `0.0` | Generation temperature (0-2) |
| `RAGCORE_LLM_MAX_TOKENS` | `4096` | Max output tokens |
| `RAGCORE_LLM_TIMEOUT` | `120` | Request timeout in seconds |

## Embedding Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_EMBEDDING_MODEL` | `nomic-embed-text:latest` | Ollama embedding model |
| `RAGCORE_EMBEDDING_BASE_URL` | `http://127.0.0.1:11434` | Ollama server URL |

## Chunking Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_CHUNK_MIN_TOKENS` | `200` | Minimum tokens per chunk |
| `RAGCORE_CHUNK_MAX_TOKENS` | `1200` | Maximum tokens per chunk |
| `RAGCORE_CHUNK_OVERLAP_TOKENS` | `150` | Overlap tokens between chunks |
| `RAGCORE_CHUNK_SIMILARITY_THRESHOLD` | `0.85` | Semantic boundary threshold |

## Retrieval Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_RETRIEVAL_STRATEGY` | `simple` | `simple`, `mmr`, `hybrid`, `ensemble` |
| `RAGCORE_RETRIEVAL_TOP_K` | `4` | Number of chunks to retrieve |
| `RAGCORE_RETRIEVAL_SCORE_THRESHOLD` | `0.0` | Minimum similarity score |

## Cache Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_CACHE_ENABLED` | `true` | Enable/disable all caching |
| `RAGCORE_CACHE_EMBEDDING_TTL` | `86400` | Embedding cache TTL (seconds) |
| `RAGCORE_CACHE_SEMANTIC_TTL` | `3600` | Semantic cache TTL (seconds) |
| `RAGCORE_CACHE_SEMANTIC_THRESHOLD` | `0.92` | Semantic cache similarity threshold |
| `RAGCORE_CACHE_LRU_MAXSIZE` | `4096` | In-memory LRU cache size |

## Data & Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_DATA_DIR` | `./rag_data` | Data storage directory |
| `RAGCORE_INDEX_NAME` | `default` | Default index name |
| `RAGCORE_LOG_LEVEL` | `INFO` | Log level |
| `RAGCORE_LOG_FORMAT` | `json` | `json` or `colored` |
| `RAGCORE_LOG_FILE` | `./rag_data/logs/ragcore.log` | Log file path |
| `RAGCORE_LOG_ROTATION` | `10 MB` | Log rotation size |
| `RAGCORE_LOG_RETENTION` | `30 days` | Log retention period |

## Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_SERVER_HOST` | `127.0.0.1` | Server bind address |
| `RAGCORE_SERVER_PORT` | `29000` | Server port |
| `RAGCORE_SERVER_RELOAD` | `false` | Auto-reload on changes |
| `RAGCORE_SERVER_WORKERS` | `1` | Number of workers |

## CORS Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_CORS_ALLOW_ORIGINS` | `["http://localhost:29000"]` | Allowed origins (JSON array) |
| `RAGCORE_CORS_ALLOW_METHODS` | `["*"]` | Allowed HTTP methods |
| `RAGCORE_CORS_ALLOW_HEADERS` | `["*"]` | Allowed HTTP headers |

## Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RAGCORE_RATE_LIMIT_DEFAULT` | `100/minute` | Default endpoint limit |
| `RAGCORE_RATE_LIMIT_QUERY` | `20/minute` | Query endpoint limit |
| `RAGCORE_RATE_LIMIT_INGEST` | `10/minute` | Ingestion endpoint limit |

Format: `[count]/[interval]` where interval is `second`, `minute`, `hour`, or `day`.

## Input Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGCORE_MAX_TEXT_LENGTH` | `100000` | Max characters for text ingestion |
| `RAGCORE_MAX_FILE_SIZE_MB` | `50` | Max file upload size (MB) |
| `RAGCORE_MAX_QUERY_LENGTH` | `4000` | Max query characters |
| `RAGCORE_MAX_K` | `50` | Max retrieval count |
