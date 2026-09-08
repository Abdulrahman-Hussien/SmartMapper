import os
import sys
from pathlib import Path

from loguru import logger


def configure_logging(log_dir: str = "logs", level: str | None = None) -> None:
    level = level or os.environ.get("LOG_LEVEL", "INFO")
    logger.remove()
    logger.add(sys.stderr, level=level)

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path / "smart_mapper_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="90 days",
        level=level,
        encoding="utf-8",
    )
