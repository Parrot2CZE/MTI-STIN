from datetime import date, timedelta
from flask import Blueprint, jsonify, request
from app.services import ExchangeRateService, ExchangeRateError
from app.extensions import limiter, cache
from app.validators import (
    validate_currency, validate_currency_list, validate_date_range,
    ValidationError,
)

api_bp = Blueprint("api", __name__)


def _svc() -> ExchangeRateService:
    return ExchangeRateService()


def _parse_symbols() -> list[str] | None:
    raw = request.args.get("symbols", "")
    return [s.strip() for s in raw.split(",") if s.strip()] or None


@api_bp.route("/latest")
@limiter.limit("30 per minute")
@cache.cached(timeout=1200, query_string=True)
def latest():
    try:
        base = validate_currency(request.args.get("base", "USD"))
        sym_list = None
        raw = request.args.get("symbols", "")
        if raw:
            sym_list = validate_currency_list([s.strip() for s in raw.split(",") if s.strip()])
    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    try:
        data = _svc().get_latest(base, sym_list)
        return jsonify({"success": True, "data": data})
    except ExchangeRateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


@api_bp.route("/strongest")
@limiter.limit("30 per minute")
@cache.cached(timeout=1200, query_string=True)
def strongest():
    try:
        base = validate_currency(request.args.get("base", "USD"))
        symbols = validate_currency_list(
            [s.strip() for s in request.args.get("symbols", "").split(",") if s.strip()],
            min_count=1,
        )
    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    try:
        currency, rate = _svc().strongest_currency(base, symbols)
        return jsonify({"success": True, "currency": currency, "rate": rate})
    except ExchangeRateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


@api_bp.route("/weakest")
@limiter.limit("30 per minute")
@cache.cached(timeout=1200, query_string=True)
def weakest():
    try:
        base = validate_currency(request.args.get("base", "USD"))
        symbols = validate_currency_list(
            [s.strip() for s in request.args.get("symbols", "").split(",") if s.strip()],
            min_count=1,
        )
    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    try:
        currency, rate = _svc().weakest_currency(base, symbols)
        return jsonify({"success": True, "currency": currency, "rate": rate})
    except ExchangeRateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


@api_bp.route("/average")
@limiter.limit("20 per minute")
@cache.cached(timeout=1200, query_string=True)
def average():
    today = date.today()
    default_start = (today - timedelta(days=6)).isoformat()

    try:
        base = validate_currency(request.args.get("base", "USD"))
        symbols = validate_currency_list(
            [s.strip() for s in request.args.get("symbols", "").split(",") if s.strip()],
            min_count=1,
        )
        start_date, end_date = validate_date_range(
            request.args.get("start_date", default_start),
            request.args.get("end_date", today.isoformat()),
        )
    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    try:
        averages = _svc().average_rates(base, symbols, start_date, end_date)
        return jsonify({
            "success": True,
            "base": base,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "averages": averages,
        })
    except ExchangeRateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502
