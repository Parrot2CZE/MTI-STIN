import pytest
import responses as rsps_lib
from datetime import date
from app import create_app
from app.services import ExchangeRateService, ExchangeRateError

FAKE_LATEST = {
    "success": True,
    "base": "USD",
    "rates": {"EUR": 0.92, "CZK": 23.5, "JPY": 149.0},
}

FAKE_HISTORICAL = {
    "success": True,
    "historical": True,
    "base": "USD",
    "rates": {"EUR": 0.91, "CZK": 23.1, "JPY": 148.5},
}


@pytest.fixture(autouse=True)
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


@rsps_lib.activate
def test_get_latest_returns_rates():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    svc = ExchangeRateService()
    data = svc.get_latest("USD", ["EUR", "CZK", "JPY"])
    assert data["rates"]["EUR"] == 0.92


@rsps_lib.activate
def test_get_latest_raises_on_http_error():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=500)
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError):
        svc.get_latest("USD")


@rsps_lib.activate
def test_get_latest_raises_on_api_error():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": False, "error": {"info": "invalid key"}})
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError, match="invalid key"):
        svc.get_latest("USD")


@rsps_lib.activate
def test_get_historical_returns_rates():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", json=FAKE_HISTORICAL)
    svc = ExchangeRateService()
    data = svc.get_historical(date(2024, 1, 15), "USD", ["EUR"])
    assert data["rates"]["EUR"] == 0.91


@rsps_lib.activate
def test_strongest_currency():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    svc = ExchangeRateService()
    currency, rate = svc.strongest_currency("USD", ["EUR", "CZK", "JPY"])
    assert currency == "EUR"
    assert rate == 0.92


@rsps_lib.activate
def test_weakest_currency():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    svc = ExchangeRateService()
    currency, rate = svc.weakest_currency("USD", ["EUR", "CZK", "JPY"])
    assert currency == "JPY"
    assert rate == 149.0


@rsps_lib.activate
def test_average_rates():
    rsps_lib.add(
        rsps_lib.GET, "https://api.exchangerate.host/historical",
        json=FAKE_HISTORICAL,
    )
    svc = ExchangeRateService()
    averages = svc.average_rates("USD", ["EUR", "CZK"], days=2)
    assert "EUR" in averages
    assert "CZK" in averages
    assert abs(averages["EUR"] - 0.91) < 0.01


@rsps_lib.activate
def test_average_rates_skips_failed_days():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", status=500)
    svc = ExchangeRateService()
    averages = svc.average_rates("USD", ["EUR"], days=1)
    assert averages["EUR"] == 0.0


@rsps_lib.activate
def test_rate_limit_retry_then_success():
    # First call returns 429, second returns data
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    svc = ExchangeRateService()
    data = svc.get_latest("USD")
    assert data["rates"]["EUR"] == 0.92


@rsps_lib.activate
def test_rate_limit_all_retries_exhausted():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError, match="Rate limit"):
        svc.get_latest("USD")
