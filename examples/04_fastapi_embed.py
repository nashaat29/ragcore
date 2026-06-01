"""
Example 4: Embed ragcore into your existing FastAPI application.
Run: python examples/04_fastapi_embed.py
"""

from fastapi import FastAPI

from ragcore import RAGClient

# Create your existing FastAPI app
app = FastAPI(title="My Application with RAG")

# Embed ragcore as a lightweight client
rag = RAGClient()


@app.post("/my-rag-query")
async def my_query(question: str):
    result = await rag.query(question)
    return {
        "answer": result["answer"],
        "sources": result["sources"],
    }


@app.post("/my-ingest")
async def my_ingest(text: str):
    doc_ids = rag.ingest_text(text)
    return {"doc_ids": doc_ids, "count": len(doc_ids)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=29000)
