from flask import Blueprint, render_template, request, flash
from app.services import ExchangeRateService, ExchangeRateError

main_bp = Blueprint("main", __name__)

AVAILABLE_CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "CHF", "CZK", "PLN", "HUF",
    "CAD", "AUD", "SEK", "NOK", "DKK", "CNY", "INR",
]


@main_bp.route("/", methods=["GET", "POST"])
def index():
    context = {
        "currencies": AVAILABLE_CURRENCIES,
        "result": None,
    }

    if request.method == "POST":
        base = request.form.get("base", "USD").upper()
        selected = request.form.getlist("symbols")
        days = int(request.form.get("days", 7))

        if not selected:
            flash("Vyber alespoň jednu měnu.", "warning")
            return render_template("index.html", **context)

        svc = ExchangeRateService()
        try:
            strongest = svc.strongest_currency(base, selected)
            weakest = svc.weakest_currency(base, selected)
            averages = svc.average_rates(base, selected, days)

            context["result"] = {
                "base": base,
                "strongest": {"currency": strongest[0], "rate": strongest[1]},
                "weakest": {"currency": weakest[0], "rate": weakest[1]},
                "averages": averages,
                "days": days,
            }
        except ExchangeRateError as exc:
            flash(f"Chyba při načítání kurzů: {exc}", "danger")

    return render_template("index.html", **context)
