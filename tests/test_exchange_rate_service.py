"""
Testy ExchangeRateService — unit testy service vrstvy bez HTTP.

Všechny testy mockují HTTP přes @responses.activate, takže nepotřebují
síť ani platný API klíč. app_ctx fixture zajišťuje Flask app context,
který service potřebuje pro přístup k cache a config.
"""

import pytest
import responses as rsps_lib
from datetime import date
from app import create_app
from app.services import ExchangeRateService, ExchangeRateError

# --- Test data ---

FAKE_LIVE_USD_BASE = {
    "success": True,
    "source": "USD",
    "quotes": {"USDEUR": 0.92, "USDCZK": 23.5, "USDJPY": 149.0, "USDGBP": 0.79},
}

FAKE_LIVE_FOR_EUR_BASE = {
    "success": True,
    "source": "USD",
    "quotes": {"USDEUR": 0.92, "USDCZK": 23.5, "USDGBP": 0.79},
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


@pytest.fixture(autouse=True)
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


# --- _extract_rates ---

def test_extract_rates_plain_keys():
    assert ExchangeRateService._extract_rates({"rates": {"EUR": 0.92}}, "USD") == {"EUR": 0.92}

def test_extract_rates_strips_usd_prefix():
    result = ExchangeRateService._extract_rates({"quotes": {"USDEUR": 0.92, "USDCZK": 23.5}}, "USD")
    assert "EUR" in result and "USDEUR" not in result

def test_extract_rates_empty_data():
    assert ExchangeRateService._extract_rates({}, "USD") == {}

def test_extract_rates_no_base():
    assert ExchangeRateService._extract_rates({"rates": {"EUR": 0.92}}) == {"EUR": 0.92}

def test_extract_rates_float_cast():
    # API občas vrátí číslo jako string, musíme castovat na float
    result = ExchangeRateService._extract_rates({"rates": {"EUR": "0.92"}}, "USD")
    assert isinstance(result["EUR"], float)


# --- get_latest ---

@rsps_lib.activate
def test_get_latest_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_USD_BASE)
    data = ExchangeRateService().get_latest("USD", ["EUR", "CZK"])
    assert abs(data["rates"]["EUR"] - 0.92) < 0.001

@rsps_lib.activate
def test_get_latest_raises_on_http_error():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=500)
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().get_latest("USD")

@rsps_lib.activate
def test_get_latest_raises_on_api_error():
    # API vrátí HTTP 200, ale success=false (neplatný klíč apod.)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": False, "error": {"info": "invalid key"}})
    with pytest.raises(ExchangeRateError, match="invalid key"):
        ExchangeRateService().get_latest("USD")


# --- Cross-rate výpočty pro non-USD base ---

@rsps_lib.activate
def test_get_latest_eur_base_cross_rate():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_FOR_EUR_BASE)
    rates = ExchangeRateService().get_latest("EUR", ["CZK", "GBP"])["rates"]
    # EUR->CZK = USD->CZK / USD->EUR = 23.5 / 0.92
    assert abs(rates["CZK"] - (23.5 / 0.92)) < 0.01
    assert abs(rates["GBP"] - (0.79 / 0.92)) < 0.01

@rsps_lib.activate
def test_get_latest_eur_base_excludes_self():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_FOR_EUR_BASE)
    assert "EUR" not in ExchangeRateService().get_latest("EUR", ["CZK", "GBP"])["rates"]

@rsps_lib.activate
def test_get_latest_usd_in_symbols_non_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "quotes": {"USDCZK": 23.5, "USDGBP": 0.79}})
    rates = ExchangeRateService().get_latest("CZK", ["USD", "GBP"])["rates"]
    assert abs(rates["USD"] - (1.0 / 23.5)) < 0.001

@rsps_lib.activate
def test_get_latest_missing_base_raises():
    # API nevrátilo kurz pro základní měnu -> cross-rate nelze spočítat
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "quotes": {"USDCZK": 23.5}})
    with pytest.raises(ExchangeRateError, match="EUR"):
        ExchangeRateService().get_latest("EUR", ["CZK"])


# --- get_historical ---

@rsps_lib.activate
def test_get_historical_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", json=FAKE_HISTORICAL_USD)
    data = ExchangeRateService().get_historical(date(2024, 1, 15), "USD", ["EUR"])
    assert abs(data["rates"]["EUR"] - 0.91) < 0.001

@rsps_lib.activate
def test_get_historical_eur_base_cross_rate():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical",
                 json=FAKE_HISTORICAL_FOR_EUR_BASE)
    data = ExchangeRateService().get_historical(date(2024, 1, 15), "EUR", ["CZK", "GBP"])
    assert abs(data["rates"]["CZK"] - (23.5 / 0.92)) < 0.01
    assert "EUR" not in data["rates"]


# --- FR2: strongest ---

@rsps_lib.activate
def test_strongest_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_USD_BASE)
    currency, rate = ExchangeRateService().strongest_currency("USD", ["EUR", "CZK", "JPY"])
    assert currency == "EUR" and abs(rate - 0.92) < 0.001

@rsps_lib.activate
def test_strongest_eur_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_FOR_EUR_BASE)
    currency, _ = ExchangeRateService().strongest_currency("EUR", ["CZK", "GBP"])
    assert currency == "GBP"

@rsps_lib.activate
def test_strongest_empty_rates_raises():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "rates": {}})
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().strongest_currency("USD", ["EUR"])

def test_strongest_only_base_raises():
    # Pokud symbols obsahuje jen základní měnu, není co porovnávat
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().strongest_currency("USD", ["USD"])


# --- FR3: weakest ---

@rsps_lib.activate
def test_weakest_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_USD_BASE)
    currency, rate = ExchangeRateService().weakest_currency("USD", ["EUR", "CZK", "JPY"])
    assert currency == "JPY" and abs(rate - 149.0) < 0.001

@rsps_lib.activate
def test_weakest_eur_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_FOR_EUR_BASE)
    currency, _ = ExchangeRateService().weakest_currency("EUR", ["CZK", "GBP"])
    assert currency == "CZK"

def test_weakest_only_base_raises():
    with pytest.raises(ExchangeRateError):
        ExchangeRateService().weakest_currency("USD", ["USD"])


# --- FR4: average_rates ---

@rsps_lib.activate
def test_average_rates_uses_timeframe():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", json=FAKE_TIMEFRAME)
    averages = ExchangeRateService().average_rates("USD", ["EUR", "CZK"], days=2)
    # (0.91 + 0.92) / 2 = 0.915
    assert abs(averages["EUR"] - 0.915) < 0.001

@rsps_lib.activate
def test_average_rates_eur_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe",
                 json=FAKE_TIMEFRAME_FOR_EUR_BASE)
    averages = ExchangeRateService().average_rates("EUR", ["CZK", "GBP"], days=2)
    assert "CZK" in averages and "GBP" in averages

@rsps_lib.activate
def test_average_rates_base_in_symbols_returns_1():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", json=FAKE_TIMEFRAME)
    averages = ExchangeRateService().average_rates("USD", ["USD", "EUR"], days=2)
    assert averages["USD"] == 1.0

@rsps_lib.activate
def test_average_rates_fallback_to_historical():
    # Timeframe selže -> fallback na historical per den
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", status=500)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical",
                 json=FAKE_HISTORICAL_USD)
    averages = ExchangeRateService().average_rates("USD", ["EUR"], days=2)
    assert averages["EUR"] > 0

@rsps_lib.activate
def test_average_rates_skips_failed_days_in_fallback():
    # Všechny historical requesty selhají -> výsledek 0.0 (prázdný průměr)
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


# --- Retry / rate limit ---

@rsps_lib.activate
def test_rate_limit_retry_then_success():
    # První request vrátí 429, druhý uspěje — retry mechanismus musí fungovat
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE_USD_BASE)
    data = ExchangeRateService().get_latest("USD")
    assert "EUR" in data["rates"]

@rsps_lib.activate
def test_rate_limit_all_retries_exhausted():
    # Všechny pokusy vrátí 429 -> ExchangeRateError
    for _ in range(3):
        rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    with pytest.raises(ExchangeRateError, match="Rate limit"):
        ExchangeRateService().get_latest("USD")
