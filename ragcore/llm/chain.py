from __future__ import annotations

from collections.abc import AsyncIterator

from ragcore.core.logger import get_logger
from ragcore.llm.prompts import CONDENSE_QUESTION_TEMPLATE, RAG_PROMPT_TEMPLATE
from ragcore.llm.provider import LLMProvider

logger = get_logger("ragcore.llm.chain")


class RAGChain:
    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    def generate(
        self,
        question: str,
        context: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> str:
        if chat_history:
            question = self._condense_question(question, chat_history)

        prompt = RAG_PROMPT_TEMPLATE.format(question=question, context=context)
        return self._llm.invoke(prompt)

    async def generate_async(
        self,
        question: str,
        context: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> str:
        if chat_history:
            question = await self._condense_question_async(question, chat_history)

        prompt = RAG_PROMPT_TEMPLATE.format(question=question, context=context)
        return await self._llm.invoke_async(prompt)

    def stream(
        self,
        question: str,
        context: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[str]:
        if chat_history:
            question = self._condense_question(question, chat_history)

        prompt = RAG_PROMPT_TEMPLATE.format(question=question, context=context)
        return self._llm.stream(prompt)

    def _condense_question(
        self, question: str, chat_history: list[dict[str, str]]
    ) -> str:
        history_str = "\n".join(
            f"User: {m.get('user', '')}\nAssistant: {m.get('assistant', '')}"
            for m in chat_history[-6:]
        )
        prompt = CONDENSE_QUESTION_TEMPLATE.format(
            question=question, chat_history=history_str
        )
        return self._llm.invoke(prompt)

    async def _condense_question_async(
        self, question: str, chat_history: list[dict[str, str]]
    ) -> str:
        history_str = "\n".join(
            f"User: {m.get('user', '')}\nAssistant: {m.get('assistant', '')}"
            for m in chat_history[-6:]
        )
        prompt = CONDENSE_QUESTION_TEMPLATE.format(
            question=question, chat_history=history_str
        )
        return await self._llm.invoke_async(prompt)
