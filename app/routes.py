from datetime import date, timedelta
from flask import Blueprint, render_template, request, flash
from app.services import ExchangeRateService, ExchangeRateError
from app.validators import (
    validate_currency, validate_currency_list, validate_date_range,
    ValidationError, AVAILABLE_CURRENCIES,
)

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET", "POST"])
def index():
    today = date.today()
    default_start = (today - timedelta(days=6)).isoformat()
    default_end = today.isoformat()

    context = {
        "currencies": AVAILABLE_CURRENCIES,
        "result": None,
        "form": {
            "base": "USD",
            "symbols": [],
            "start_date": default_start,
            "end_date": default_end,
        },
    }

    if request.method == "POST":
        raw_base = request.form.get("base", "")
        raw_symbols = request.form.getlist("symbols")
        raw_start = request.form.get("start_date", default_start)
        raw_end = request.form.get("end_date", default_end)

        # Zachovej hodnoty formuláře pro re-render
        context["form"] = {
            "base": raw_base,
            "symbols": raw_symbols,
            "start_date": raw_start,
            "end_date": raw_end,
        }

        try:
            base = validate_currency(raw_base)
            symbols = validate_currency_list(raw_symbols, min_count=1)
            start_date, end_date = validate_date_range(raw_start, raw_end)
        except ValidationError as exc:
            flash(str(exc), "warning")
            return render_template("index.html", **context)

        svc = ExchangeRateService()
        try:
            strongest = svc.strongest_currency(base, symbols)
            weakest = svc.weakest_currency(base, symbols)
            averages = svc.average_rates(base, symbols, start_date, end_date)

            context["result"] = {
                "base": base,
                "strongest": {"currency": strongest[0], "rate": strongest[1]},
                "weakest":   {"currency": weakest[0],   "rate": weakest[1]},
                "averages": averages,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        except ExchangeRateError as exc:
            flash(f"Chyba při načítání kurzů: {exc}", "danger")

    return render_template("index.html", **context)
