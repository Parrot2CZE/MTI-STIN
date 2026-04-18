import os


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "")
    EXCHANGERATE_BASE_URL = "https://api.exchangerate.host"
    RATELIMIT_DEFAULT = "60 per minute"
    RATELIMIT_STORAGE_URI = "memory://"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False


class TestingConfig(BaseConfig):
    DEBUG = True
    TESTING = True
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
