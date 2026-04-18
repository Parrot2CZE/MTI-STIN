from flask import Blueprint, jsonify, request
from app.services import ExchangeRateService, ExchangeRateError
from app.extensions import limiter

api_bp = Blueprint("api", __name__)


def _svc() -> ExchangeRateService:
    return ExchangeRateService()


@api_bp.route("/latest")
@limiter.limit("30 per minute")
def latest():
    base = request.args.get("base", "USD").upper()
    symbols = request.args.get("symbols", "")
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] or None
    try:
        data = _svc().get_latest(base, sym_list)
        return jsonify({"success": True, "data": data})
    except ExchangeRateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


@api_bp.route("/strongest")
@limiter.limit("30 per minute")
def strongest():
    base = request.args.get("base", "USD").upper()
    symbols = [s.strip() for s in request.args.get("symbols", "").split(",") if s.strip()]
    if not symbols:
        return jsonify({"success": False, "error": "symbols param required"}), 400
    try:
        currency, rate = _svc().strongest_currency(base, symbols)
        return jsonify({"success": True, "currency": currency, "rate": rate})
    except ExchangeRateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


@api_bp.route("/weakest")
@limiter.limit("30 per minute")
def weakest():
    base = request.args.get("base", "USD").upper()
    symbols = [s.strip() for s in request.args.get("symbols", "").split(",") if s.strip()]
    if not symbols:
        return jsonify({"success": False, "error": "symbols param required"}), 400
    try:
        currency, rate = _svc().weakest_currency(base, symbols)
        return jsonify({"success": True, "currency": currency, "rate": rate})
    except ExchangeRateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


@api_bp.route("/average")
@limiter.limit("20 per minute")
def average():
    base = request.args.get("base", "USD").upper()
    symbols = [s.strip() for s in request.args.get("symbols", "").split(",") if s.strip()]
    days = int(request.args.get("days", 7))
    if not symbols:
        return jsonify({"success": False, "error": "symbols param required"}), 400
    try:
        averages = _svc().average_rates(base, symbols, days)
        return jsonify({"success": True, "base": base, "days": days, "averages": averages})
    except ExchangeRateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502
