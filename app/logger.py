"""
Logování aplikace.

Kombinuje dva handlery:
  - BufferHandler: drží posledních 500 záznamů v paměti pro /api/logs endpoint
  - RotatingFileHandler: zapisuje do logs/app.log, max 5 MB, 3 zálohy

In-memory buffer záměrně nepřežije restart aplikace — to je OK pro debugging,
pro audit trail by bylo potřeba použít databázi nebo externí logging service.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler

# maxlen=500 — starší záznamy se automaticky zahazují (FIFO)
_LOG_BUFFER: deque[dict] = deque(maxlen=500)


class BufferHandler(logging.Handler):
    """Ukládá log záznamy do in-memory deque pro REST endpoint /api/logs."""

    def emit(self, record: logging.LogRecord) -> None:
        _LOG_BUFFER.append({
            "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "level": record.levelname,
            "message": self.format(record),
        })


def setup_logger(app) -> None:
    """
    Připojí oba handlery k Flask app loggeru.
    Volá se jednou z create_app(), ne z každého requestu.
    """
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    # Buffer handler — jednodušší formát, čas se přidává v emit()
    buffer_handler = BufferHandler()
    buffer_handler.setFormatter(logging.Formatter("%(message)s"))
    buffer_handler.setLevel(logging.INFO)

    # Logs složka je mimo app/ záměrně — nechceme ji servírovat jako statický soubor
    log_dir = os.path.join(os.path.dirname(app.root_path), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    app.logger.addHandler(buffer_handler)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)


def get_logs() -> list[dict]:
    """Vrátí kopii bufferu — klient nemůže deque přímo modifikovat."""
    return list(_LOG_BUFFER)
