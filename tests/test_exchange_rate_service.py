import pytest
import responses as rsps_lib
from datetime import date
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

# Pro cross-rate test: base=EUR — API stále vrátí USD quotes
# cross: EUR→CZK = USDCZK / USDEUR = 23.5 / 0.92 ≈ 25.54
# cross: EUR→GBP = USDGBP / USDEUR = 0.79 / 0.92 ≈ 0.858
FAKE_LIVE_FOR_EUR_BASE = {
    "success": True,
    "source": "USD",
    "quotes": {
        "USDEUR": 0.92,
        "USDCZK": 23.5,
        "USDGBP": 0.79,
    },
}

FAKE_HISTORICAL = {
    "success": True,
    "historical": True,
    "base": "USD",
    "rates": {"EUR": 0.91, "CZK": 23.1, "JPY": 148.5},
}

FAKE_HISTORICAL_EUR_BASE = {
    "success": True,
    "historical": True,
    "base": "EUR",
    "rates": {"CZK": 25.3, "GBP": 0.86},
}

FAKE_HISTORICAL_WITH_PREFIX = {
    "success": True,
    "historical": True,
    "quotes": {"USDEUR": 0.91, "USDCZK": 23.1},
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
    assert "EUR" in result
    assert "CZK" in result
    assert "USDEUR" not in result


def test_extract_rates_empty_data():
    result = ExchangeRateService._extract_rates({}, "USD")
    assert result == {}


def test_extract_rates_no_base():
    raw = {"rates": {"EUR": 0.92}}
    result = ExchangeRateService._extract_rates(raw)
    assert result == {"EUR": 0.92}


def test_extract_rates_float_cast():
    raw = {"rates": {"EUR": "0.92"}}
    result = ExchangeRateService._extract_rates(raw, "USD")
    assert isinstance(result["EUR"], float)


# ------------------------------------------------------------------
# get_latest — base=USD (přímý kurz)
# ------------------------------------------------------------------

@rsps_lib.activate
def test_get_latest_usd_base_returns_rates():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json=FAKE_LIVE_USD_BASE)
    svc = ExchangeRateService()
    data = svc.get_latest("USD", ["EUR", "CZK", "JPY"])
    assert abs(data["rates"]["EUR"] - 0.92) < 0.001
    assert abs(data["rates"]["CZK"] - 23.5) < 0.001


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


# ------------------------------------------------------------------
# get_latest — base=EUR (cross-rate přepočet)
# ------------------------------------------------------------------

@rsps_lib.activate
def test_get_latest_eur_base_cross_rate():
    """
    base=EUR: API vrátí USD quotes, kód přepočítá křížem.
    EUR→CZK = USDCZK / USDEUR = 23.5 / 0.92 ≈ 25.54
    EUR→GBP = USDGBP / USDEUR = 0.79 / 0.92 ≈ 0.858
    """
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json=FAKE_LIVE_FOR_EUR_BASE)
    svc = ExchangeRateService()
    data = svc.get_latest("EUR", ["CZK", "GBP"])
    rates = data["rates"]
    assert "CZK" in rates
    assert "GBP" in rates
    assert abs(rates["CZK"] - (23.5 / 0.92)) < 0.01
    assert abs(rates["GBP"] - (0.79 / 0.92)) < 0.01


@rsps_lib.activate
def test_get_latest_eur_base_excludes_base_from_result():
    """EUR nesmí být ve výsledných kurzech když je base=EUR."""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json=FAKE_LIVE_FOR_EUR_BASE)
    svc = ExchangeRateService()
    data = svc.get_latest("EUR", ["CZK", "GBP"])
    assert "EUR" not in data["rates"]


@rsps_lib.activate
def test_get_latest_missing_base_in_response_raises():
    """Pokud API nevrátí kurz pro base měnu, vyhodí ExchangeRateError."""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "quotes": {"USDCZK": 23.5}})
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError, match="EUR"):
        svc.get_latest("EUR", ["CZK"])


# ------------------------------------------------------------------
# get_historical
# ------------------------------------------------------------------

@rsps_lib.activate
def test_get_historical_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical",
                 json=FAKE_HISTORICAL)
    svc = ExchangeRateService()
    data = svc.get_historical(date(2024, 1, 15), "USD", ["EUR"])
    assert abs(data["rates"]["EUR"] - 0.91) < 0.001


@rsps_lib.activate
def test_get_historical_eur_base():
    """historical respektuje base parametr — vrací čisté klíče."""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical",
                 json=FAKE_HISTORICAL_EUR_BASE)
    svc = ExchangeRateService()
    data = svc.get_historical(date(2024, 1, 15), "EUR", ["CZK", "GBP"])
    assert abs(data["rates"]["CZK"] - 25.3) < 0.001
    assert abs(data["rates"]["GBP"] - 0.86) < 0.001


@rsps_lib.activate
def test_get_historical_with_prefix():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical",
                 json=FAKE_HISTORICAL_WITH_PREFIX)
    svc = ExchangeRateService()
    data = svc.get_historical(date(2024, 1, 15), "USD", ["EUR", "CZK"])
    assert "EUR" in data["rates"]


# ------------------------------------------------------------------
# FR2 — strongest_currency
# ------------------------------------------------------------------

@rsps_lib.activate
def test_strongest_usd_base():
    """EUR (0.92) < CZK (23.5) < JPY (149) → strongest je EUR."""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json=FAKE_LIVE_USD_BASE)
    svc = ExchangeRateService()
    currency, rate = svc.strongest_currency("USD", ["EUR", "CZK", "JPY"])
    assert currency == "EUR"
    assert abs(rate - 0.92) < 0.001


@rsps_lib.activate
def test_strongest_eur_base():
    """
    base=EUR, symbols=[CZK, GBP]:
    cross CZK = 23.5/0.92 ≈ 25.54
    cross GBP = 0.79/0.92 ≈ 0.858
    → strongest je GBP (nejnižší cross rate)
    """
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json=FAKE_LIVE_FOR_EUR_BASE)
    svc = ExchangeRateService()
    currency, rate = svc.strongest_currency("EUR", ["CZK", "GBP"])
    assert currency == "GBP"
    assert abs(rate - (0.79 / 0.92)) < 0.01


@rsps_lib.activate
def test_strongest_empty_rates_raises():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "rates": {}})
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError):
        svc.strongest_currency("USD", ["EUR"])


@rsps_lib.activate
def test_strongest_single_symbol():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "quotes": {"USDEUR": 0.92}})
    svc = ExchangeRateService()
    currency, _ = svc.strongest_currency("USD", ["EUR"])
    assert currency == "EUR"


# ------------------------------------------------------------------
# FR3 — weakest_currency
# ------------------------------------------------------------------

@rsps_lib.activate
def test_weakest_usd_base():
    """JPY (149) > CZK (23.5) > EUR (0.92) → weakest je JPY."""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json=FAKE_LIVE_USD_BASE)
    svc = ExchangeRateService()
    currency, rate = svc.weakest_currency("USD", ["EUR", "CZK", "JPY"])
    assert currency == "JPY"
    assert abs(rate - 149.0) < 0.001


@rsps_lib.activate
def test_weakest_eur_base():
    """
    base=EUR, symbols=[CZK, GBP]:
    cross CZK ≈ 25.54 > cross GBP ≈ 0.858
    → weakest je CZK
    """
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json=FAKE_LIVE_FOR_EUR_BASE)
    svc = ExchangeRateService()
    currency, rate = svc.weakest_currency("EUR", ["CZK", "GBP"])
    assert currency == "CZK"
    assert abs(rate - (23.5 / 0.92)) < 0.01


@rsps_lib.activate
def test_weakest_empty_rates_raises():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json={"success": True, "rates": {}})
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError):
        svc.weakest_currency("USD", ["EUR"])


# ------------------------------------------------------------------
# FR4 — average_rates
# ------------------------------------------------------------------

@rsps_lib.activate
def test_average_rates_usd_base():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical",
                 json=FAKE_HISTORICAL)
    svc = ExchangeRateService()
    averages = svc.average_rates("USD", ["EUR", "CZK"], days=2)
    assert "EUR" in averages
    assert "CZK" in averages
    assert abs(averages["EUR"] - 0.91) < 0.01


@rsps_lib.activate
def test_average_rates_eur_base():
    """historical respektuje base=EUR, takže průměr funguje bez cross-rate."""
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical",
                 json=FAKE_HISTORICAL_EUR_BASE)
    svc = ExchangeRateService()
    averages = svc.average_rates("EUR", ["CZK", "GBP"], days=2)
    assert "CZK" in averages
    assert abs(averages["CZK"] - 25.3) < 0.01


@rsps_lib.activate
def test_average_rates_skips_failed_days():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", status=500)
    svc = ExchangeRateService()
    averages = svc.average_rates("USD", ["EUR"], days=1)
    assert averages["EUR"] == 0.0


def test_average_rates_invalid_days_too_high():
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError, match="365"):
        svc.average_rates("USD", ["EUR"], days=400)


def test_average_rates_invalid_days_zero():
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError):
        svc.average_rates("USD", ["EUR"], days=0)


def test_average_rates_invalid_days_negative():
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError):
        svc.average_rates("USD", ["EUR"], days=-1)


# ------------------------------------------------------------------
# Retry / rate limit
# ------------------------------------------------------------------

@rsps_lib.activate
def test_rate_limit_retry_then_success():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live",
                 json=FAKE_LIVE_USD_BASE)
    svc = ExchangeRateService()
    data = svc.get_latest("USD")
    assert "EUR" in data["rates"]


@rsps_lib.activate
def test_rate_limit_all_retries_exhausted():
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=429)
    svc = ExchangeRateService()
    with pytest.raises(ExchangeRateError, match="Rate limit"):
        svc.get_latest("USD")
