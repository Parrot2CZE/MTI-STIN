import pytest
import responses as rsps_lib
from datetime import date
from app import create_app
from app.services import ExchangeRateService, ExchangeRateError

FAKE_LATEST = {
    "success": True,
    "base": "EUR",
    "rates": {"USD": 1.10, "JPY": 160.0, "CZK": 25.0},
}

FAKE_HISTORICAL = {
    "success": True,
    "historical": True,
    "base": "EUR",
    "rates": {"USD": 1.08, "JPY": 158.0},
}


@pytest.fixture(autouse=True)
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


@rsps_lib.activate
def test_get_latest_returns_rates():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    data = ExchangeRateService().get_latest("EUR", ["USD", "JPY"])
    assert data["rates"]["JPY"] == 160.0


@rsps_lib.activate
def test_get_latest_raises_on_http_error():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=500)
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().get_latest("EUR")


@rsps_lib.activate
def test_get_latest_raises_on_api_error():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": False, "error": {"info": "invalid key"}})
    with pytest.raises(ExchangeRateError, match="invalid key"):
        ExchangeRateService().get_latest("EUR")


@rsps_lib.activate
def test_get_historical():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", json=FAKE_HISTORICAL)
    data = ExchangeRateService().get_historical(date(2024, 1, 15), "EUR", ["USD"])
    assert data["rates"]["USD"] == 1.08


# FR2 – strongest = MAX hodnota kurzu (JPY=160 > USD=1.10 > CZK=25? ne, JPY > CZK > USD)
@rsps_lib.activate
def test_strongest_currency_is_max_rate():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    currency, rate = ExchangeRateService().strongest_currency("EUR", ["USD", "JPY", "CZK"])
    assert currency == "JPY"   # 160 je nejvyšší
    assert rate == 160.0


# FR3 – weakest = MIN hodnota kurzu
@rsps_lib.activate
def test_weakest_currency_is_min_rate():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    currency, rate = ExchangeRateService().weakest_currency("EUR", ["USD", "JPY", "CZK"])
    assert currency == "USD"   # 1.10 je nejnižší
    assert rate == 1.10


# FR4 – průměr za datum od–do
@rsps_lib.activate
def test_average_rates_date_range():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", json=FAKE_HISTORICAL)
    svc = ExchangeRateService()
    avgs = svc.average_rates("EUR", ["USD", "JPY"],
                             start_date=date(2024, 1, 1), end_date=date(2024, 1, 2))
    assert "USD" in avgs
    assert abs(avgs["USD"] - 1.08) < 0.01


@rsps_lib.activate
def test_average_rates_skips_failed_days():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", status=500)
    avgs = ExchangeRateService().average_rates(
        "EUR", ["USD"], start_date=date(2024, 1, 1), end_date=date(2024, 1, 1)
    )
    assert avgs["USD"] == 0.0


def test_average_rates_invalid_range():
    with pytest.raises(ValueError, match="start_date"):
        ExchangeRateService().average_rates(
            "EUR", ["USD"],
            start_date=date(2024, 1, 10),
            end_date=date(2024, 1, 1),
        )


@rsps_lib.activate
def test_retry_on_429_then_success():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    data = ExchangeRateService().get_latest("EUR")
    assert "rates" in data


@rsps_lib.activate
def test_retry_exhausted_raises():
    for _ in range(3):
        rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    with pytest.raises(ExchangeRateError, match="Rate limit"):
        ExchangeRateService().get_latest("EUR")
