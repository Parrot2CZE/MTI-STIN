from __future__ import annotations

import os
import yaml

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
    return load_config()["currencies"]["base"]


def get_compare_currencies() -> list[str]:
    return load_config()["currencies"]["compare"]


def get_all_currencies() -> list[str]:
    cfg = load_config()["currencies"]
    return list(dict.fromkeys(cfg["base"] + cfg["compare"]))


def get_cache_timeout(dev: bool = False) -> int:
    cache = load_config().get("cache", {})
    if dev:
        return cache.get("timeout_seconds_dev", 300)
    return cache.get("timeout_seconds", 1200)


def get_rate_limit_default() -> str:
    return load_config().get("rate_limit", {}).get("default", "60 per minute")


def get_button_cooldown() -> int:
    return load_config().get("rate_limit", {}).get("button_cooldown_seconds", 10)


def get_api_base_url() -> str:
    return load_config().get("api", {}).get("base_url", "https://api.exchangerate.host")


def get_exchangerate_api_key() -> str:
    """API klíč: config.yml má přednost, fallback na env proměnnou."""
    yml_key = load_config().get("api_keys", {}).get("exchangerate", "")
    if yml_key:
        return yml_key
    return os.getenv("EXCHANGERATE_API_KEY", "")


def get_users() -> list[dict]:
    """Vrátí seznam uživatelů z config.yml."""
    return load_config().get("users", [])


def get_i18n(lang: str = "cs") -> dict:
    """Vrátí slovník překladů pro daný jazyk."""
    translations = load_config().get("i18n", {})
    return translations.get(lang, translations.get("cs", {}))


def get_supported_languages() -> list[str]:
    return list(load_config().get("i18n", {}).keys())
