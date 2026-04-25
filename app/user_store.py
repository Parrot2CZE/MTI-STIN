"""
Persistentní úložiště stavu uživatele.

Ukládá last_result per uživatel jako JSON soubor v data/ adresáři.
Soubory přežijí restart aplikace i změnu prohlížeče — načtou se
při každém přihlášení.

Selhání čtení/zápisu nikdy nesmí shodit aplikaci — degraduje gracefully
na prázdný stav (uživatel prostě neuvidí minulý výsledek).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# data/ je vedle app/ v kořeni projektu — záměrně mimo statické soubory
_DATA_DIR = Path(__file__).parent.parent / "data"


def _user_path(username: str) -> Path:
    """
    Vrátí cestu k JSON souboru uživatele.
    Username se sanitizuje — povoleny jsou jen alfanumerické znaky, '-' a '_'.
    Zabraňuje path traversal útoku přes speciální znaky v username.
    """
    _DATA_DIR.mkdir(exist_ok=True)
    safe = "".join(c for c in username if c.isalnum() or c in "-_")
    if not safe:
        safe = "unknown"
    return _DATA_DIR / f"{safe}.json"


def load_user_state(username: str) -> dict:
    """
    Načte uložený stav uživatele ze souboru.
    Vrátí prázdný dict pokud soubor neexistuje nebo je poškozený.
    """
    path = _user_path(username)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        # Poškozený soubor tiše ignorujeme — uživatel začne znovu
        return {}


def save_user_state(username: str, state: dict) -> None:
    """
    Uloží stav uživatele do JSON souboru.
    Selhání zápisu (disk plný, permissions) se tiše pohltí — aplikace
    nesmí padat kvůli vedlejšímu efektu persistence.
    """
    try:
        with open(_user_path(username), "w", encoding="utf-8") as f:
            # default=str zachytí případné date objekty, které nejsou JSON serializable
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)
    except OSError:
        pass
