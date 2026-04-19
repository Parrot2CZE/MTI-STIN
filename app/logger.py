from __future__ import annotations

import logging
import os
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler


# In-memory buffer — max 500 záznamů pro REST endpoint
_LOG_BUFFER: deque[dict] = deque(maxlen=500)


class BufferHandler(logging.Handler):
    """Ukládá záznamy do in-memory bufferu pro /api/logs endpoint."""

    def emit(self, record: logging.LogRecord) -> None:
        _LOG_BUFFER.append({
            "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "level": record.levelname,
            "message": self.format(record),
        })


def setup_logger(app) -> None:
    """
    Připojí BufferHandler + RotatingFileHandler k Flask app loggeru.
    Soubor: logs/app.log, max 5 MB, 3 zálohy (app.log.1, app.log.2, app.log.3).
    """
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    # In-memory buffer (vždy)
    buffer_handler = BufferHandler()
    buffer_handler.setFormatter(logging.Formatter("%(message)s"))
    buffer_handler.setLevel(logging.INFO)

    # File handler — vytvoří složku logs/ pokud neexistuje
    log_dir = os.path.join(os.path.dirname(app.root_path), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    app.logger.addHandler(buffer_handler)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)


def get_logs() -> list[dict]:
    """Vrátí kopii in-memory logů pro /api/logs endpoint."""
    return list(_LOG_BUFFER)