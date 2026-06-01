"""
Example 1: Basic import and usage of ragcore as a library.
Run: python examples/01_basic_import.py
"""

from ragcore import RAGClient, RAGPipeline


# Option A: Direct pipeline (no server)
def example_pipeline():
    pipeline = RAGPipeline()
    doc_ids = pipeline.ingest_text(
        "RAG (Retrieval-Augmented Generation) combines retrieval systems "
        "with generative language models to produce accurate answers."
    )
    print(f"Ingested {len(doc_ids)} chunks")

    result = pipeline.query("What is RAG?")
    print(f"Answer: {result['answer'][:100]}...")
    print(f"Sources: {len(result['sources'])} chunks")
    print(f"Elapsed: {result['elapsed']:.3f}s")

# Option C: Lightweight client
def example_client():
    client = RAGClient()
    client.ingest_text("FAISS is a library for efficient similarity search.")
    result = client.query_sync("What is FAISS?")
    print(f"Client answer: {result['answer'][:100]}...")

if __name__ == "__main__":
    print("=== Pipeline Example ===")
    example_pipeline()
    print("\n=== Client Example ===")
    example_client()
