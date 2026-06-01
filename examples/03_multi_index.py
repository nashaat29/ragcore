"""
Example 3: Multiple index management.
Run: python examples/03_multi_index.py
"""

from ragcore.pipeline.rag_pipeline import RAGPipeline


def example_multi_index():
    pipeline = RAGPipeline()

    pipeline.ingest_text("This is about AI and machine learning.")
    pipeline.save_index("ai_knowledge")
    print("Saved index: ai_knowledge")

    pipeline.clear_index()

    pipeline.ingest_text("This is about web development with Python.")
    pipeline.save_index("web_dev")
    print("Saved index: web_dev")

    pipeline.load_index("ai_knowledge")
    stats = pipeline.get_stats()
    print(f"Active index: {stats['active_index']}")
    print(f"Available indexes: {stats['available_indexes']}")


if __name__ == "__main__":
    example_multi_index()
