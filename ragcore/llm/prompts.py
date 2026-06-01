RAG_PROMPT_TEMPLATE = """You are a helpful, accurate assistant. Use the following pieces of retrieved context to answer the question. If you don't know the answer based on the context, say so honestly. Keep your answer concise and grounded in the provided context.

Context:
{context}

Question: {question}

Answer:"""

CONDENSE_QUESTION_TEMPLATE = """Given the chat history and a follow-up question, rephrase the follow-up question to be a standalone question.

Chat History:
{chat_history}

Follow-up Question: {question}

Standalone Question:"""

SUMMARIZE_TEMPLATE = """Provide a concise summary of the following text in 2-3 sentences:

{text}

Summary:"""

QUERY_DECOMPOSITION_TEMPLATE = """Break down the following complex question into simpler sub-questions that can be answered independently:

Original Question: {question}

Sub-questions:
1."""

HYDE_TEMPLATE = """Generate a hypothetical document that would perfectly answer the following question. Write it as a factual passage:

Question: {question}

Hypothetical Document:"""

REPHRASE_TEMPLATE = """Rephrase the following answer to be more clear and concise while preserving all information:

Original Question: {question}
Original Answer: {answer}

Improved Answer:"""

PROMPTS = {
    "rag": RAG_PROMPT_TEMPLATE,
    "condense_question": CONDENSE_QUESTION_TEMPLATE,
    "summarize": SUMMARIZE_TEMPLATE,
    "decompose": QUERY_DECOMPOSITION_TEMPLATE,
    "hyde": HYDE_TEMPLATE,
    "rephrase": REPHRASE_TEMPLATE,
}
