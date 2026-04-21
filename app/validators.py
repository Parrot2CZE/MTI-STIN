"""
Centralizovaná validace vstupů.

Všechny user-supplied hodnoty prochází tudy před zpracováním.
Regex na kódy měn a whitelist z config.yml chrání před injection
a neplatnými hodnotami, které by způsobily chyby v service vrstvě.
"""

from __future__ import annotations

import re
from datetime import date

# ISO 4217 kódy jsou přesně 3 velká písmena
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def _allowed_currencies() -> list[str]:
    """Whitelist měn z config.yml — nepovolujeme libovolné ISO kódy."""
    from app.app_config_loader import get_all_currencies
    return get_all_currencies()


class ValidationError(ValueError):
    """Vyhozen při neplatném vstupu. Zpráva je určena k zobrazení uživateli."""
    pass


def validate_currency(code: str) -> str:
    """
    Ověří kód měny — musí mít formát XYZ a být v povoleném whitelistu.
    Vrátí normalizovaný uppercase kód.
    """
    code = code.strip().upper()
    if not _CURRENCY_RE.match(code):
        raise ValidationError(f"Neplatny kod meny: '{code}'")
    if code not in _allowed_currencies():
        raise ValidationError(f"Nepodporovana mena: '{code}'")
    return code


def validate_currency_list(codes: list[str], min_count: int = 1) -> list[str]:
    """Ověří celý seznam měn najednou. min_count hlídá, že seznam není prázdný."""
    result = [validate_currency(c) for c in codes]
    if len(result) < min_count:
        raise ValidationError(f"Vyber alespon {min_count} menu.")
    return result


def validate_date(value: str) -> date:
    """Parsuje datum ve formátu YYYY-MM-DD. Jiné formáty jsou odmítnuty."""
    try:
        d = date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValidationError(f"Neplatne datum: '{value}'. Pouzij format YYYY-MM-DD.")
    return d


def validate_date_range(start: str, end: str) -> tuple[date, date]:
    """
    Ověří rozsah dat.
    Pravidla:
      - start <= end
      - rozsah max 365 dní (limit API)
      - end nesmí být v budoucnosti (neexistují kurzy pro budoucí data)
    """
    start_date = validate_date(start)
    end_date = validate_date(end)
    if start_date > end_date:
        raise ValidationError("Datum 'od' musi byt pred datem 'do'.")
    if (end_date - start_date).days > 365:
        raise ValidationError("Maximalni rozsah je 365 dni.")
    if end_date > date.today():
        raise ValidationError("Datum 'do' nesmi byt v budoucnosti.")
    return start_date, end_date
