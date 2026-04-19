from flask import Blueprint, render_template, request, flash
from app.services import ExchangeRateService, ExchangeRateError
from app.app_config_loader import get_base_currencies, get_compare_currencies

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET", "POST"])
def index():
    base_currencies = get_base_currencies()
    compare_currencies = get_compare_currencies()

    context = {
        "base_currencies": base_currencies,
        "compare_currencies": compare_currencies,
        "result": None,
    }

    if request.method == "POST":
        base = request.form.get("base", base_currencies[0]).upper()
        selected = request.form.getlist("symbols")

        try:
            days = int(request.form.get("days", 7))
        except ValueError:
            flash("Počet dní musí být celé číslo.", "warning")
            return render_template("index.html", **context)

        if not selected:
            flash("Vyber alespoň jednu měnu.", "warning")
            return render_template("index.html", **context)

        if days < 1 or days > 365:
            flash("Počet dní musí být v rozsahu 1–365.", "warning")
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
