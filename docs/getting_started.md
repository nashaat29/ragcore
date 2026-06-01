# Getting Started with RAGCore

## Installation

```bash
cd rag_application
pip install -e .
```

## Configuration

Copy the example env file and adjust:

```bash
cp .env.example .env
```

Key defaults already set:
- LLM: `frob/qwen3.5-instruct:9b` via Ollama at `127.0.0.1:11434`
- Embedding: `nomic-embed-text:latest` via Ollama
- Data directory: `./rag_data/`

## Quick Start

### Option A: Run the API server

```python
from ragcore import RAGApp

app = RAGApp()
app.serve()  # http://127.0.0.1:29000
```

### Option B: Embed in your FastAPI app

```python
from fastapi import FastAPI
from ragcore import RAGClient

my_app = FastAPI()
rag = RAGClient()

@my_app.post("/ask")
async def ask(question: str):
    return await rag.query(question)
```

### Option C: Direct Python usage

```python
from ragcore import RAGPipeline

pipeline = RAGPipeline()

# Ingest
pipeline.ingest_file("document.pdf")
pipeline.ingest_text("Some custom text...")

# Query
result = pipeline.query("What does this document say?")
print(result["answer"])
```

## API Endpoints (when serving)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Component health |
| `/ingest/text` | POST | Ingest raw text |
| `/ingest/file` | POST | Upload and ingest file |
| `/ingest/directory` | POST | Ingest all files in a directory |
| `/ingest/{doc_id}` | DELETE | Delete a specific document |
| `/ingest/` | DELETE | Batch delete documents |
| `/query` | POST | Full RAG query |
| `/query/stream` | POST | Streaming response |
| `/query/retrieve` | POST | Retrieve only (no LLM) |
| `/manage/index/stats` | GET | Index statistics |
| `/manage/index/list` | GET | List all indexes |
| `/manage/index/save` | POST | Persist index |
| `/manage/index/load` | POST | Load index |
| `/manage/index/clear` | POST | Clear all vectors from active index |
| `/manage/index/{name}` | DELETE | Delete a saved index |
| `/manage/retrieval/strategy` | POST | Set retrieval strategy |
| `/manage/config` | GET | View current configuration |
| `/monitoring/stats` | GET | Runtime metrics and counters |
| `/monitoring/logs` | GET | Recent log lines |
| `/monitoring/logs/stream` | GET | SSE log stream |
| `/docs` | GET | Interactive API docs (Swagger) |
