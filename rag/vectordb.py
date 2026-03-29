import chromadb
from chromadb.config import Settings
from uuid import uuid4
from logging_config import get_logger, clip_text

logger = get_logger("rag.vectordb")

try:
    client = chromadb.PersistentClient(path="chroma_db")
    logger.info("Using PersistentClient for Chroma path=chroma_db")
except Exception:
    logger.warning("PersistentClient unavailable. Falling back to chromadb.Client with Settings.")
    client = chromadb.Client(Settings(
        persist_directory="chroma_db",
        anonymized_telemetry=False
    ))

collection = client.get_or_create_collection(name="documents")
logger.info("Vector collection ready name=documents")

def add_documents(texts, metadatas=None):
    logger.info("Adding documents to vector DB count=%s", len(texts))
    ids = [str(uuid4()) for _ in texts]
    collection.add(
        documents=texts,
        metadatas=metadatas if metadatas else [{}]*len(texts),
        ids=ids
    )
    logger.info("Vector DB add completed count=%s", len(texts))

def query_docs(query, n_results=3):
    logger.info("Vector DB query started n_results=%s query=%s", n_results, clip_text(query))
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    docs = results["documents"][0]
    logger.info("Vector DB query completed returned_docs=%s", len(docs))
    return docs