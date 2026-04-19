from __future__ import annotations

import os
import yaml

_config: dict | None = None


def load_config() -> dict:
    """Načte config.yml jednou a cachuje výsledek."""
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
    """Sjednocení base + compare — pro validaci."""
    cfg = load_config()["currencies"]
    return list(dict.fromkeys(cfg["base"] + cfg["compare"]))


def get_cache_timeout(dev: bool = False) -> int:
    cache = load_config().get("cache", {})
    if dev:
        return cache.get("timeout_seconds_dev", 300)
    return cache.get("timeout_seconds", 1200)


def get_rate_limit_default() -> str:
    return load_config().get("rate_limit", {}).get("default", "60 per minute")


def get_api_base_url() -> str:
    return load_config().get("api", {}).get("base_url", "https://api.exchangerate.host")
