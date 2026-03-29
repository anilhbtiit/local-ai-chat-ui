import logging
from pathlib import Path

MAX_LOG_BYTES = 10 * 1024 * 1024
DEFAULT_CLIP_LIMIT = 300


def clip_text(text: str, limit: int = DEFAULT_CLIP_LIMIT) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"...<truncated {len(text) - limit} chars>"


def _reset_log_if_oversized(log_path: Path) -> None:
    try:
        if log_path.exists() and log_path.stat().st_size > MAX_LOG_BYTES:
            # Keep behavior simple/predictable: reset file once it exceeds 10MB.
            log_path.write_text("", encoding="utf-8")
    except Exception:
        # Logging setup should never block app startup.
        pass


def get_logger(name: str = "ai_chat") -> logging.Logger:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "app.log"
    _reset_log_if_oversized(log_path)

    logger = logging.getLogger("ai_chat")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger.getChild(name)
