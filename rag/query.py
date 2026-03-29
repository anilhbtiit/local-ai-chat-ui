import requests
from rag.vectordb import query_docs
from logging_config import get_logger, clip_text

logger = get_logger("rag.query")

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

def ask_rag(question, model="phi3"):
    logger.info("ask_rag started model=%s question=%s", model, clip_text(question))
    docs = query_docs(question)

    context = "\n\n".join(docs)

    prompt = f"""
Use the following context to answer the question.

Context:
{context}

Question:
{question}
"""

    response = requests.post(OLLAMA_URL, json={
        "model": model,
        "prompt": prompt,
        "stream": False
    })

    answer = response.json()["response"]
    logger.info("ask_rag completed answer=%s", clip_text(answer))
    return answer


def build_rag_context(question, n_results=4):
    logger.info("build_rag_context started n_results=%s question=%s", n_results, clip_text(question))
    docs = query_docs(question, n_results=n_results)
    if not docs:
        logger.info("build_rag_context no docs found.")
        return ""
    context = "\n\n".join(docs)
    logger.info("build_rag_context completed context_chars=%s", len(context))
    return context