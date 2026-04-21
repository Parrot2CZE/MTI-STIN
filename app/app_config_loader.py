"""
Načítání konfigurace z config.yml.

config.yml je zdrojem pravdy pro měny, limity, překlady a uživatele.
Singleton _config zabraňuje opakovanému čtení souboru při každém requestu.
"""

from __future__ import annotations

import os
import yaml

# Singleton — soubor se čte jednou a drží se v paměti po celou dobu běhu
_config: dict | None = None


def load_config() -> dict:
    global _config
    if _config is not None:
        return _config
    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "config.yml")
    )
    with open(config_path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    return _config


def get_base_currencies() -> list[str]:
    """Měny dostupné jako základní (základ pro výpočet kurzů)."""
    return load_config()["currencies"]["base"]


def get_compare_currencies() -> list[str]:
    """Měny nabízené k porovnání v UI checkboxech."""
    return load_config()["currencies"]["compare"]


def get_all_currencies() -> list[str]:
    """Sjednocení base a compare bez duplicit — používá se pro validaci vstupů."""
    cfg = load_config()["currencies"]
    return list(dict.fromkeys(cfg["base"] + cfg["compare"]))


def get_cache_timeout(dev: bool = False) -> int:
    """
    TTL cache v sekundách.
    Dev timeout je kratší, aby bylo vidět změny bez restartu aplikace.
    """
    cache = load_config().get("cache", {})
    if dev:
        return cache.get("timeout_seconds_dev", 300)
    return cache.get("timeout_seconds", 1200)


def get_rate_limit_default() -> str:
    """Globální rate limit pro Flask-Limiter ve formátu 'N per minute'."""
    return load_config().get("rate_limit", {}).get("default", "60 per minute")


def get_button_cooldown() -> int:
    """Cooldown tlačítka v UI v sekundách — brání spamu na straně klienta."""
    return load_config().get("rate_limit", {}).get("button_cooldown_seconds", 10)


def get_api_base_url() -> str:
    return load_config().get("api", {}).get("base_url", "https://api.exchangerate.host")


def get_exchangerate_api_key() -> str:
    """
    API klíč pro exchangerate.host.
    config.yml má přednost před env proměnnou, aby šlo klíč přebít bez restartu.
    V produkci doporučujeme nechat config.yml prázdný a použít GitHub Secrets / env.
    """
    yml_key = load_config().get("api_keys", {}).get("exchangerate", "")
    if yml_key:
        return yml_key
    return os.getenv("EXCHANGERATE_API_KEY", "")


def get_users() -> list[dict]:
    """
    Uživatelé s bcrypt hashy hesel z config.yml.
    Pro přidání uživatele vygeneruj hash:
      python -c "import bcrypt; print(bcrypt.hashpw(b'heslo', bcrypt.gensalt()).decode())"
    """
    return load_config().get("users", [])


def get_i18n(lang: str = "cs") -> dict:
    """Vrátí slovník překladů pro daný jazyk, fallback na češtinu."""
    translations = load_config().get("i18n", {})
    return translations.get(lang, translations.get("cs", {}))


def get_supported_languages() -> list[str]:
    """Jazyky definované v sekci i18n config.yml."""
    return list(load_config().get("i18n", {}).keys())
