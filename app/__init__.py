"""
Application factory.

Izoluje vytváření app do funkce create_app() tak, aby testy mohly
spouštět vlastní instance s odlišnou konfigurací bez vedlejších efektů.
"""

from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()


def create_app(config_name: str = None) -> Flask:
    app = Flask(__name__)

    # Chybějící env proměnná nikdy náhodou nezapne debug mode v produkci
    env = config_name or os.getenv("FLASK_ENV", "production")
    if env == "testing":
        app.config.from_object("app.config.TestingConfig")
    elif env == "development":
        app.config.from_object("app.config.DevelopmentConfig")
    else:
        app.config.from_object("app.config.ProductionConfig")

    # Extensions se inicializují až po vytvoření app objektu (Flask application factory pattern)
    from app.extensions import limiter, cache, cors
    limiter.init_app(app)
    cache.init_app(app)
    # CORS otevřen pouze pro /api/* — UI routy ho nepotřebují
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    from app.logger import setup_logger
    setup_logger(app)

    from app.routes import main_bp
    app.register_blueprint(main_bp)

    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
