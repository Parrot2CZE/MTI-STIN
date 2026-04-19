import os
from app.app_config_loader import get_cache_timeout, get_rate_limit_default, get_api_base_url


class BaseConfig:
    # Tajné hodnoty — pouze z prostředí, nikdy z config.yml
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "")

    # Vše ostatní z config.yml
    EXCHANGERATE_BASE_URL = get_api_base_url()
    RATELIMIT_DEFAULT = get_rate_limit_default()
    RATELIMIT_STORAGE_URI = "memory://"
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = get_cache_timeout()


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    CACHE_DEFAULT_TIMEOUT = get_cache_timeout(dev=True)


class TestingConfig(BaseConfig):
    DEBUG = True
    TESTING = True
    RATELIMIT_ENABLED = False
    CACHE_TYPE = "NullCache"


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
