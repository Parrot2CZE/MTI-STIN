from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()


def create_app(config_name: str = None) -> Flask:
    app = Flask(__name__)

    # Config
    env = config_name or os.getenv("FLASK_ENV", "production")
    if env == "testing":
        app.config.from_object("app.config.TestingConfig")
    elif env == "development":
        app.config.from_object("app.config.DevelopmentConfig")
    else:
        app.config.from_object("app.config.ProductionConfig")

    # Extensions
    from app.extensions import limiter, cache
    limiter.init_app(app)
    cache.init_app(app)

    # Blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
