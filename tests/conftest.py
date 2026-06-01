import pytest

from ragcore.core.config import Settings


@pytest.fixture
def test_settings():
    return Settings(
        llm_model="test-model",
        embedding_model="test-embed-model",
        data_dir="/tmp/ragcore_test",
        log_level="DEBUG",
        log_format="colored",
    )


@pytest.fixture
def sample_texts():
    return [
        "Artificial intelligence is transforming the world of technology.",
        "Machine learning algorithms can identify patterns in data.",
        "Neural networks are inspired by the human brain structure.",
        "Natural language processing enables computers to understand text.",
        "Deep learning uses multiple layers of neural networks.",
        "Reinforcement learning trains agents through trial and error.",
        "Computer vision allows machines to interpret visual information.",
        "Transformers have revolutionized natural language processing tasks.",
    ]
