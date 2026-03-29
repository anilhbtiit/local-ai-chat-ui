from pathlib import Path
from typing import Iterable, Tuple

from rag.vectordb import add_documents
from logging_config import get_logger

logger = get_logger("rag.ingest")

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".py", ".json", ".csv"}


def _read_pdf(path: Path) -> str:
    logger.info("Reading PDF file path=%s", path)
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _read_text(path: Path) -> str:
    logger.info("Reading text file path=%s", path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 120) -> Iterable[str]:
    logger.info("Chunking text chars=%s chunk_size=%s overlap=%s", len(text or ""), chunk_size, overlap)
    text = (text or "").strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def ingest_file(file_path: str) -> Tuple[int, str]:
    logger.info("Ingest file started path=%s", file_path)
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        logger.warning("Unsupported file extension path=%s suffix=%s", file_path, suffix)
        return 0, f"Unsupported extension: {suffix}"

    if suffix == ".pdf":
        content = _read_pdf(path)
    else:
        content = _read_text(path)

    chunks = list(_chunk_text(content))
    if not chunks:
        logger.warning("No readable content path=%s", file_path)
        return 0, "No readable content found"

    source = str(path.resolve())
    metadatas = [{"source": source} for _ in chunks]
    add_documents(chunks, metadatas)
    logger.info("Ingest file completed path=%s chunks=%s", file_path, len(chunks))
    return len(chunks), "ok"


def ingest_directory(directory_path: str) -> dict:
    logger.info("Ingest directory started path=%s", directory_path)
    base = Path(directory_path)
    if not base.exists() or not base.is_dir():
        logger.error("Ingest directory failed path missing/invalid path=%s", directory_path)
        return {"ingested_files": 0, "total_chunks": 0, "errors": ["Directory not found"]}

    ingested_files = 0
    total_chunks = 0
    errors = []

    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            chunks, msg = ingest_file(str(file_path))
            if chunks > 0:
                ingested_files += 1
                total_chunks += chunks
            elif msg != "No readable content found":
                errors.append(f"{file_path}: {msg}")
        except Exception as exc:
            logger.exception("Ingest directory file failed path=%s error=%s", file_path, exc)
            errors.append(f"{file_path}: {exc}")

    result = {
        "ingested_files": ingested_files,
        "total_chunks": total_chunks,
        "errors": errors,
    }
    logger.info(
        "Ingest directory completed path=%s files=%s chunks=%s errors=%s",
        directory_path,
        ingested_files,
        total_chunks,
        len(errors),
    )
    return result
