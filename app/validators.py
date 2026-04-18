"""
Centralizovaná validace vstupů (ochrana proti injection, neplatným hodnotám).
"""
from __future__ import annotations
import re
from datetime import date

# Povolené kódy měn – pouze 3 velká písmena ISO 4217
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

AVAILABLE_CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "CHF", "CZK", "PLN", "HUF",
    "CAD", "AUD", "SEK", "NOK", "DKK", "CNY", "INR",
]


class ValidationError(ValueError):
    pass


def validate_currency(code: str) -> str:
    """Ověří, že kód měny je platný 3-písmenný ISO kód ze seznamu."""
    code = code.strip().upper()
    if not _CURRENCY_RE.match(code):
        raise ValidationError(f"Neplatný kód měny: '{code}'")
    if code not in AVAILABLE_CURRENCIES:
        raise ValidationError(f"Nepodporovaná měna: '{code}'")
    return code


def validate_currency_list(codes: list[str], min_count: int = 1) -> list[str]:
    """Ověří seznam kódů měn."""
    result = [validate_currency(c) for c in codes]
    if len(result) < min_count:
        raise ValidationError(f"Vyber alespoň {min_count} měnu.")
    return result


def validate_date(value: str) -> date:
    """Parsuje datum ve formátu YYYY-MM-DD."""
    try:
        d = date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValidationError(f"Neplatné datum: '{value}'. Použij formát YYYY-MM-DD.")
    return d


def validate_date_range(start: str, end: str) -> tuple[date, date]:
    """Ověří rozsah dat – start <= end, max 365 dní zpětně."""
    start_date = validate_date(start)
    end_date = validate_date(end)
    if start_date > end_date:
        raise ValidationError("Datum 'od' musí být před datem 'do'.")
    if (end_date - start_date).days > 365:
        raise ValidationError("Maximální rozsah je 365 dní.")
    if end_date > date.today():
        raise ValidationError("Datum 'do' nesmí být v budoucnosti.")
    return start_date, end_date
