import pytest
import responses as rsps_lib
from datetime import date, timedelta
from app import create_app
from app.services import ExchangeRateService, ExchangeRateError

# ------------------------------------------------------------------
# Fake API responses
# ------------------------------------------------------------------

# /live vždy vrací USD jako zdroj — klíče s prefixem "USD"
FAKE_LIVE_USD_BASE = {
    "success": True,
    "source": "USD",
    "quotes": {
        "USDEUR": 0.92,
        "USDCZK": 23.5,
        "USDJPY": 149.0,
        "USDGBP": 0.79,
    },
}

# API vrátí USD quotes i při base=EUR — cross-rate se dopočítá v kódu
FAKE_LIVE_FOR_EUR_BASE = {
    "success": True,
    "source": "USD",
    "quotes": {
        "USDEUR": 0.92,
        "USDCZK": 23.5,
        "USDGBP": 0.79,
    },
}

FAKE_HISTORICAL_USD = {
    "success": True,
    "historical": True,
    "quotes": {"USDEUR": 0.91, "USDCZK": 23.1, "USDJPY": 148.5},
}

FAKE_HISTORICAL_FOR_EUR_BASE = {
    "success": True,
    "historical": True,
    "quotes": {"USDEUR": 0.92, "USDCZK": 23.5, "USDGBP": 0.79},
}

# /timeframe vrací { "YYYY-MM-DD": { "USDEUR": ..., ... }, ... }
FAKE_TIMEFRAME = {
    "success": True,
    "quotes": {
        "2024-01-14": {"USDEUR": 0.91, "USDCZK": 23.1},
        "2024-01-15": {"USDEUR": 0.92, "USDCZK": 23.5},
    },
}

FAKE_TIMEFRAME_FOR_EUR_BASE = {
    "success": True,
    "quotes": {
        "2024-01-14": {"USDEUR": 0.92, "USDCZK": 23.5, "USDGBP": 0.79},
        "2024-01-15": {"USDEUR": 0.91, "USDCZK": 23.1, "USDGBP": 0.78},
    },
}


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(autouse=True)
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


# ------------------------------------------------------------------
# _extract_rates
# ------------------------------------------------------------------

def test_extract_rates_plain_keys():
    raw = {"rates": {"EUR": 0.92, "CZK": 23.5}}
    result = ExchangeRateService._extract_rates(raw, "USD")
    assert result == {"EUR": 0.92, "CZK": 23.5}


def test_extract_rates_strips_usd_prefix():
    raw = {"quotes": {"USDEUR": 0.92, "USDCZK": 23.5}}
    result = ExchangeRateService._extract_rates(raw, "USD")
    assert "EUR" in result and "CZK" in result
    assert "USDEUR" not in result


def test_extract_rates_empty_data():
    assert ExchangeRateService._extract_rates({}, "USD") == {}


def test_extract_rates_no_base():
    raw = {"rates": {"EUR": 0.92}}
    assert ExchangeRateService._extract_rates(raw) == {"EUR": 0.92}


def test_extract_rates_float_cast():
    raw = {"rates": {"EUR": "0.92"}}
    result = ExchangeRateService._extract_rates(raw, "USD")
    assert isinstance(result["EUR"], float)


# ------------------------------------------------------------------
# get_latest — base=USD
# ------------------------------------------------------------------

@rsps_lib.activate
def test_get_latest_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_USD_BASE)
    svc = ExchangeRateService()
    data = svc.get_latest("USD", ["EUR", "CZK", "JPY"])
    assert abs(data["rates"]["EUR"] - 0.92) < 0.001
    assert abs(data["rates"]["CZK"] - 23.5) < 0.001


@rsps_lib.activate
def test_get_latest_raises_on_http_error():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=500)
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().get_latest("USD")


@rsps_lib.activate
def test_get_latest_raises_on_api_error():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": False, "error": {"info": "invalid key"}})
    with pytest.raises(ExchangeRateError, match="invalid key"):
        ExchangeRateService().get_latest("USD")


# ------------------------------------------------------------------
# get_latest — base=EUR (cross-rate)
# ------------------------------------------------------------------

@rsps_lib.activate
def test_get_latest_eur_base_cross_rate():
    """EUR→CZK = USDCZK / USDEUR = 23.5 / 0.92 ≈ 25.54"""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_FOR_EUR_BASE)
    svc = ExchangeRateService()
    rates = svc.get_latest("EUR", ["CZK", "GBP"])["rates"]
    assert abs(rates["CZK"] - (23.5 / 0.92)) < 0.01
    assert abs(rates["GBP"] - (0.79 / 0.92)) < 0.01


@rsps_lib.activate
def test_get_latest_eur_base_excludes_self():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_FOR_EUR_BASE)
    assert "EUR" not in ExchangeRateService().get_latest("EUR", ["CZK", "GBP"])["rates"]


@rsps_lib.activate
def test_get_latest_usd_in_symbols_non_usd_base():
    """base=CZK, symbols=[USD]: USD = 1 / usd_to_czk"""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "quotes": {"USDCZK": 23.5, "USDGBP": 0.79}})
    rates = ExchangeRateService().get_latest("CZK", ["USD", "GBP"])["rates"]
    assert abs(rates["USD"] - (1.0 / 23.5)) < 0.001


@rsps_lib.activate
def test_get_latest_missing_base_raises():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "quotes": {"USDCZK": 23.5}})
    with pytest.raises(ExchangeRateError, match="EUR"):
        ExchangeRateService().get_latest("EUR", ["CZK"])


# ------------------------------------------------------------------
# get_historical
# ------------------------------------------------------------------

@rsps_lib.activate
def test_get_historical_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", json=FAKE_HISTORICAL_USD)
    data = ExchangeRateService().get_historical(date(2024, 1, 15), "USD", ["EUR"])
    assert abs(data["rates"]["EUR"] - 0.91) < 0.001


@rsps_lib.activate
def test_get_historical_eur_base_cross_rate():
    """historical taky vrátí USD quotes → cross-rate."""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical",
                 json=FAKE_HISTORICAL_FOR_EUR_BASE)
    data = ExchangeRateService().get_historical(date(2024, 1, 15), "EUR", ["CZK", "GBP"])
    assert abs(data["rates"]["CZK"] - (23.5 / 0.92)) < 0.01
    assert "EUR" not in data["rates"]


# ------------------------------------------------------------------
# FR2 — strongest_currency
# ------------------------------------------------------------------

@rsps_lib.activate
def test_strongest_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_USD_BASE)
    currency, rate = ExchangeRateService().strongest_currency("USD", ["EUR", "CZK", "JPY"])
    assert currency == "EUR"
    assert abs(rate - 0.92) < 0.001


@rsps_lib.activate
def test_strongest_eur_base():
    """cross GBP ≈ 0.858 < cross CZK ≈ 25.54 → strongest je GBP"""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_FOR_EUR_BASE)
    currency, _ = ExchangeRateService().strongest_currency("EUR", ["CZK", "GBP"])
    assert currency == "GBP"


@rsps_lib.activate
def test_strongest_empty_rates_raises():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "rates": {}})
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().strongest_currency("USD", ["EUR"])


def test_strongest_only_base_in_symbols_raises():
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().strongest_currency("USD", ["USD"])


# ------------------------------------------------------------------
# FR3 — weakest_currency
# ------------------------------------------------------------------

@rsps_lib.activate
def test_weakest_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_USD_BASE)
    currency, rate = ExchangeRateService().weakest_currency("USD", ["EUR", "CZK", "JPY"])
    assert currency == "JPY"
    assert abs(rate - 149.0) < 0.001


@rsps_lib.activate
def test_weakest_eur_base():
    """cross CZK ≈ 25.54 > cross GBP ≈ 0.858 → weakest je CZK"""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_FOR_EUR_BASE)
    currency, _ = ExchangeRateService().weakest_currency("EUR", ["CZK", "GBP"])
    assert currency == "CZK"


def test_weakest_only_base_in_symbols_raises():
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().weakest_currency("USD", ["USD"])


# ------------------------------------------------------------------
# FR4 — average_rates (přes /timeframe)
# ------------------------------------------------------------------

@rsps_lib.activate
def test_average_rates_uses_timeframe():
    """/timeframe vrátí 2 dny — průměr EUR = (0.91+0.92)/2 = 0.915"""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", json=FAKE_TIMEFRAME)
    averages = ExchangeRateService().average_rates("USD", ["EUR", "CZK"], days=2)
    assert abs(averages["EUR"] - 0.915) < 0.001
    assert abs(averages["CZK"] - 23.3) < 0.01


@rsps_lib.activate
def test_average_rates_eur_base_cross_rate():
    """base=EUR: cross-rate přes timeframe."""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe",
                 json=FAKE_TIMEFRAME_FOR_EUR_BASE)
    averages = ExchangeRateService().average_rates("EUR", ["CZK", "GBP"], days=2)
    assert "CZK" in averages
    assert "GBP" in averages


@rsps_lib.activate
def test_average_rates_base_in_symbols_returns_1():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", json=FAKE_TIMEFRAME)
    averages = ExchangeRateService().average_rates("USD", ["USD", "EUR"], days=2)
    assert averages["USD"] == 1.0


@rsps_lib.activate
def test_average_rates_fallback_to_historical():
    """/timeframe selže (500) → fallback na /historical."""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", status=500)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical",
                 json=FAKE_HISTORICAL_USD)
    averages = ExchangeRateService().average_rates("USD", ["EUR"], days=2)
    assert "EUR" in averages
    assert averages["EUR"] > 0


@rsps_lib.activate
def test_average_rates_skips_failed_days_in_fallback():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", status=500)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", status=500)
    averages = ExchangeRateService().average_rates("USD", ["EUR"], days=1)
    assert averages["EUR"] == 0.0


def test_average_rates_invalid_days_too_high():
    with pytest.raises(ExchangeRateError, match="365"):
        ExchangeRateService().average_rates("USD", ["EUR"], days=400)


def test_average_rates_invalid_days_zero():
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().average_rates("USD", ["EUR"], days=0)


def test_average_rates_invalid_days_negative():
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().average_rates("USD", ["EUR"], days=-1)


# ------------------------------------------------------------------
# Retry / rate limit
# ------------------------------------------------------------------

@rsps_lib.activate
def test_rate_limit_retry_then_success():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_USD_BASE)
    data = ExchangeRateService().get_latest("USD")
    assert "EUR" in data["rates"]


@rsps_lib.activate
def test_rate_limit_all_retries_exhausted():
    for _ in range(3):
        rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    with pytest.raises(ExchangeRateError, match="Rate limit"):
        ExchangeRateService().get_latest("USD")
