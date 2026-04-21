"""
UI blueprint — HTML routy pro prohlížeč.

Veškeré výpočty deleguje na ExchangeRateService; tady se jen
zpracovává formulář, ukládá výsledek do session a renderují šablony.
"""

from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, session)
from app.services import ExchangeRateService, ExchangeRateError
from app.app_config_loader import (get_base_currencies, get_compare_currencies,
                                    get_i18n, get_supported_languages, get_button_cooldown)
from app.auth import verify_password, login_user, logout_user, is_logged_in

main_bp = Blueprint("main", __name__)


def _lang() -> str:
    """Vrátí aktuální jazyk ze session, výchozí čeština."""
    return session.get("lang", "cs")


def _t() -> dict:
    """Zkratka pro získání překladového slovníku aktuálního jazyka."""
    return get_i18n(_lang())


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    t = _t()
    # Přihlášený uživatel na login stránce nemá co dělat
    if is_logged_in():
        return redirect(url_for("main.index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if verify_password(username, password):
            login_user(username)
            return redirect(url_for("main.index"))
        error = t.get("login_error")
    return render_template("login.html", t=t, error=error, lang=_lang(),
                           languages=get_supported_languages())


@main_bp.route("/logout")
def logout():
    logout_user()
    # Smažeme i uložený výsledek, aby ho neviděl případný další uživatel na stejném PC
    session.pop("last_result", None)
    return redirect(url_for("main.login"))


@main_bp.route("/lang/<lang>")
def set_lang(lang: str):
    """Přepne jazyk a vrátí uživatele zpět na stránku, ze které přišel."""
    if lang in get_supported_languages():
        session["lang"] = lang
    return redirect(request.referrer or url_for("main.index"))


@main_bp.route("/", methods=["GET", "POST"])
def index():
    if not is_logged_in():
        return redirect(url_for("main.login"))

    t = _t()
    base_currencies = get_base_currencies()
    compare_currencies = get_compare_currencies()
    cooldown = get_button_cooldown()

    # Výsledek předchozího dotazu se drží v session, aby přežil přepnutí jazyka
    saved_result = session.get("last_result")

    context = {
        "base_currencies": base_currencies,
        "compare_currencies": compare_currencies,
        "result": saved_result,
        "t": t,
        "lang": _lang(),
        "languages": get_supported_languages(),
        "cooldown": cooldown,
    }

    if request.method == "POST":
        base = request.form.get("base", base_currencies[0]).upper()
        selected = request.form.getlist("symbols")

        try:
            days = int(request.form.get("days", 7))
        except ValueError:
            flash(t.get("err_days_int"), "warning")
            return render_template("index.html", **context)

        if not selected:
            flash(t.get("err_no_symbols"), "warning")
            return render_template("index.html", **context)

        if days < 1 or days > 365:
            flash(t.get("err_days_range"), "warning")
            return render_template("index.html", **context)

        svc = ExchangeRateService()
        try:
            from flask import current_app
            current_app.logger.info(
                f"Query: base={base} symbols={selected} days={days} user={session.get('user')}"
            )
            strongest = svc.strongest_currency(base, selected)
            weakest = svc.weakest_currency(base, selected)
            averages = svc.average_rates(base, selected, days)

            # Denní data pro spojnicový graf — samostatné volání, selhání nevadí
            from datetime import date, timedelta
            today = date.today()
            start = today - timedelta(days=days - 1)
            try:
                daily = svc.get_timeframe(start, today, base,
                                          [s for s in selected if s != base] or None)
            except Exception:
                # Graf je nice-to-have, bez dat ho prostě nevykreslíme
                daily = {}

            result = {
                "base": base,
                "strongest": {"currency": strongest[0], "rate": strongest[1]},
                "weakest": {"currency": weakest[0], "rate": weakest[1]},
                "averages": averages,
                "daily": daily,
                "days": days,
            }
            session["last_result"] = result
            context["result"] = result

        except ExchangeRateError as exc:
            from flask import current_app
            current_app.logger.error(f"ExchangeRateError: {exc}")
            flash(f"{t.get('err_api')}: {exc}", "danger")

    return render_template("index.html", **context)


@main_bp.app_errorhandler(404)
def not_found(e):
    """
    Globální handler pro 404.
    Používáme app_errorhandler místo errorhandler — ten funguje napříč
    celou aplikací, nejen v rámci tohoto blueprintu.
    """
    t = _t()
    return render_template("404.html", t=t, lang=_lang(),
                           languages=get_supported_languages()), 404
