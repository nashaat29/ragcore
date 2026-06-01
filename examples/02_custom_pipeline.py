"""
Example 2: Custom pipeline with different retrieval strategies.
Run: python examples/02_custom_pipeline.py
"""

from ragcore.pipeline.rag_pipeline import RAGPipeline


def example_different_retrievers():
    pipeline = RAGPipeline()

    pipeline.ingest_text(
        "Python is a high-level, interpreted programming language known for its readability. "
        "It supports multiple programming paradigms including procedural, object-oriented, and functional programming. "
        "Python's extensive standard library makes it suitable for web development, data science, AI, and automation. "
        "The language's dynamic typing and automatic memory management simplify development. "
        "Python's package ecosystem, particularly PyPI, hosts over 400,000 packages. "
        "Frameworks like Django and Flask power web applications. "
        "Libraries like NumPy, Pandas, and scikit-learn dominate data science. "
        "TensorFlow and PyTorch are leading deep learning frameworks in Python."
    )

    strategies = ["simple", "mmr", "hybrid"]
    for strategy in strategies:
        print(f"\n--- Strategy: {strategy} ---")
        pipeline.set_retrieval_strategy(strategy)
        result = pipeline.query("What is Python used for?", k=3)
        print(f"Answer: {result['answer'][:150]}...")
        print(f"Chunks used: {result['total_chunks']}")
        print(f"Elapsed: {result['elapsed']:.3f}s")


def example_custom_config():
    pipeline = RAGPipeline(config={
        "retrieval_strategy": "hybrid",
        "top_k": 5,
        "alpha": 0.7,
    })
    print(f"Strategy: {pipeline.retriever.name}")
    print(f"Config: top_k={pipeline.retriever.top_k}")


if __name__ == "__main__":
    example_different_retrievers()
    print("\n=== Custom Config ===")
    example_custom_config()
