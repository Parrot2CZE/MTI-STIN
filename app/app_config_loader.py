from __future__ import annotations

import os
import yaml


_config: dict | None = None


def load_config() -> dict:
    """Načte config.yml jednou a cachuje výsledek."""
    global _config
    if _config is not None:
        return _config

    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yml")
    config_path = os.path.abspath(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)

    return _config


def get_base_currencies() -> list[str]:
    return load_config()["currencies"]["base"]


def get_compare_currencies() -> list[str]:
    return load_config()["currencies"]["compare"]


def get_cache_timeout() -> int:
    return load_config().get("cache", {}).get("timeout_seconds", 1200)


def get_historical_threads() -> int:
    return load_config().get("performance", {}).get("historical_threads", 7)
