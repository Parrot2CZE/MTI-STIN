"""
Flask konfigurace rozdělená do tří tříd podle prostředí.

BaseConfig drží společné hodnoty. TestingConfig vypíná rate limiting
a cache, aby testy nebyly závislé na stavu z předchozích testů.
"""

import os
from app.app_config_loader import get_cache_timeout, get_rate_limit_default, get_api_base_url


class BaseConfig:
    # SECRET_KEY musí být v produkci přepsán env proměnnou nebo GitHub Secret
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    EXCHANGERATE_BASE_URL = get_api_base_url()
    RATELIMIT_DEFAULT = get_rate_limit_default()
    # In-memory storage pro limiter — pro multi-worker produkci by bylo lepší Redis
    RATELIMIT_STORAGE_URI = "memory://"
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = get_cache_timeout()


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    # Kratší cache TTL v dev módu, aby změny kurzů byly vidět rychleji
    CACHE_DEFAULT_TIMEOUT = get_cache_timeout(dev=True)


class TestingConfig(BaseConfig):
    DEBUG = True
    TESTING = True
    # Rate limiting vypnutý — testy by jinak failovaly při opakovaném volání endpointů
    RATELIMIT_ENABLED = False
    # NullCache znamená, že každý call do service jde přímo na (mockované) API
    CACHE_TYPE = "NullCache"


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
