from __future__ import annotations

import re
from collections.abc import Callable

from ragcore.core.logger import get_logger

logger = get_logger("ragcore.ingestion.preprocessor")


class TextPreprocessor:
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._pipelines: dict[str, list[Callable[[str], str]]] = {}

    def register_pipeline(self, name: str, steps: list[Callable[[str], str]]) -> None:
        self._pipelines[name] = steps

    def run(self, text: str, pipeline: str = "default") -> str:
        steps = self._pipelines.get(pipeline)
        if steps is None:
            steps = self._default_steps()
            self._pipelines[pipeline] = steps
        for step in steps:
            try:
                text = step(text)
            except Exception as e:
                logger.warning(f"Preprocessing step failed: {e}")
        return text

    def _default_steps(self) -> list[Callable[[str], str]]:
        return [
            self.normalize_whitespace,
            self.normalize_unicode,
            self.strip_control_chars,
        ]

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def normalize_unicode(text: str) -> str:
        import unicodedata
        return unicodedata.normalize("NFKC", text)

    @staticmethod
    def strip_control_chars(text: str) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    @staticmethod
    def strip_urls(text: str, replacement: str = "") -> str:
        return re.sub(r"https?://\S+", replacement, text)

    @staticmethod
    def strip_emails(text: str, replacement: str = "") -> str:
        return re.sub(r"\S+@\S+\.\S+", replacement, text)

    @staticmethod
    def strip_html_tags(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text)

    @staticmethod
    def strip_code_blocks(text: str) -> str:
        return re.sub(r"```[\s\S]*?```", "", text)

    @staticmethod
    def collapse_newlines(text: str, max_consecutive: int = 2) -> str:
        return re.sub(r"\n{" + str(max_consecutive + 1) + r",}", "\n" * max_consecutive, text)


preprocessor = TextPreprocessor()
