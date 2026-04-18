import os


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "")
    EXCHANGERATE_BASE_URL = "https://api.exchangerate.host"
    RATELIMIT_DEFAULT = "60 per minute"
    RATELIMIT_STORAGE_URI = "memory://"
    # Cache — výchozí 20 minut (NFR: 10–30 minut)
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 1200


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minut při vývoji


class TestingConfig(BaseConfig):
    DEBUG = True
    TESTING = True
    RATELIMIT_ENABLED = False
    CACHE_TYPE = "NullCache"   # cache vypnutá v testech


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
