from flask import render_template, session
from app.app_config_loader import get_i18n, get_supported_languages


def _lang() -> str:
    return session.get("lang", "cs")


def register_error_handlers(app):

    @app.errorhandler(404)
    def not_found(e):
        t = get_i18n(_lang())
        return render_template(
            "errors/404.html",
            t=t,
            lang=_lang(),
            languages=get_supported_languages(),
        ), 404

    @app.errorhandler(500)
    def internal_error(e):
        t = get_i18n(_lang())
        return render_template(
            "errors/404.html",
            t=t,
            lang=_lang(),
            languages=get_supported_languages(),
            code=500,
        ), 500
