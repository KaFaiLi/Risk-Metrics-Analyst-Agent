import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(os.path.dirname(BASE_DIR), "Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
LOG_FILE = os.path.join(BASE_DIR, "risk_metrics_analysis.log")

MAX_LLM_CONCURRENCY = 4
MAX_LLM_ATTEMPTS = 3
LLM_RETRY_DELAY = 2.0


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    logger = logging.getLogger("risk_metrics_app")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()

__all__ = [
    "BASE_DIR",
    "OUTPUT_DIR",
    "LOG_FILE",
    "MAX_LLM_CONCURRENCY",
    "MAX_LLM_ATTEMPTS",
    "LLM_RETRY_DELAY",
    "logger",
    "setup_logging",
]
