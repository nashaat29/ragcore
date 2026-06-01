
from ragcore.ingestion.chunker import Chunk, SemanticChunker
from ragcore.ingestion.preprocessor import TextPreprocessor


class TestChunk:
    def test_chunk_creation(self):
        chunk = Chunk("test text", {"source": "test"})
        assert chunk.text == "test text"
        assert chunk.metadata["source"] == "test"
        assert chunk.token_count > 0

    def test_token_estimate(self):
        assert Chunk._estimate_tokens("hello world") >= 1
        assert Chunk._estimate_tokens("") == 0


class TestTextPreprocessor:
    def test_normalize_whitespace(self):
        result = TextPreprocessor.normalize_whitespace("  hello   world  \n\n\n test  ")
        assert "  " not in result
        assert "\n\n\n" not in result

    def test_strip_control_chars(self):
        result = TextPreprocessor.strip_control_chars("hello\x00world\x1ftest")
        assert result == "helloworldtest"

    def test_full_pipeline(self):
        pre = TextPreprocessor()
        result = pre.run("  Hello\x00 World!  \n\n\n Test.  ")
        assert "Hello World!" in result
        assert "Test." in result


class TestSemanticChunker:
    def test_split_sentences(self):
        chunker = SemanticChunker.__new__(SemanticChunker)
        sentences = chunker._split_sentences("Hello world. This is a test! Another one? Yes.")
        assert len(sentences) >= 3

    def test_empty_text(self):
        chunker = SemanticChunker.__new__(SemanticChunker)
        result = chunker.split_text("")
        assert result == []

    def test_single_sentence(self):
        chunker = SemanticChunker.__new__(SemanticChunker)
        result = chunker.split_text("Just a single sentence.")
        assert len(result) == 1
        assert result[0].text == "Just a single sentence."
