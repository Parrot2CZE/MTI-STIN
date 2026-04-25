"""
Testy REST API endpointů (/api/*).

Reálné HTTP requesty jsou interceptovány knihovnou responses,
takže testy nepotřebují síťové připojení ani platný API klíč.
"""

import responses as rsps_lib

# Simulovaná odpověď /live endpointu s USD-prefixovanými klíči (formát exchangerate.host)
FAKE_LIVE = {
    "success": True,
    "source": "USD",
    "quotes": {"USDEUR": 0.92, "USDCZK": 23.5, "USDJPY": 149.0},
}

# Simulovaná odpověď /timeframe endpointu pro 2 dny
FAKE_TIMEFRAME = {
    "success": True,
    "quotes": {
        "2024-01-14": {"USDEUR": 0.91, "USDCZK": 23.1},
        "2024-01-15": {"USDEUR": 0.92, "USDCZK": 23.5},
    },
}


@rsps_lib.activate
def test_api_latest(auth_client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE)
    r = auth_client.get("/api/latest?base=USD&symbols=EUR,CZK")
    assert r.status_code == 200
    assert r.get_json()["success"] is True


@rsps_lib.activate
def test_api_strongest(auth_client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE)
    r = auth_client.get("/api/strongest?base=USD&symbols=EUR,CZK,JPY")
    assert r.status_code == 200
    data = r.get_json()
    # EUR má nejnižší kurz (0.92) vůči USD -> je nejsilnější
    assert data["currency"] == "EUR"
    assert abs(data["rate"] - 0.92) < 0.001


@rsps_lib.activate
def test_api_weakest(auth_client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE)
    r = auth_client.get("/api/weakest?base=USD&symbols=EUR,CZK,JPY")
    assert r.status_code == 200
    data = r.get_json()
    # JPY má nejvyšší kurz (149.0) vůči USD -> je nejslabší
    assert data["currency"] == "JPY"
    assert abs(data["rate"] - 149.0) < 0.001


def test_api_strongest_missing_symbols(auth_client):
    r = auth_client.get("/api/strongest?base=USD")
    assert r.status_code == 400
    assert r.get_json()["success"] is False


def test_api_weakest_missing_symbols(auth_client):
    r = auth_client.get("/api/weakest?base=USD")
    assert r.status_code == 400


def test_api_average_missing_symbols(auth_client):
    r = auth_client.get("/api/average?base=USD")
    assert r.status_code == 400


def test_api_average_invalid_days(auth_client):
    r = auth_client.get("/api/average?base=USD&symbols=EUR&days=abc")
    assert r.status_code == 400


@rsps_lib.activate
def test_api_average(auth_client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", json=FAKE_TIMEFRAME)
    r = auth_client.get("/api/average?base=USD&symbols=EUR,CZK&days=2")
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert "EUR" in body["averages"]
    assert body["days"] == 2


@rsps_lib.activate
def test_api_average_days_out_of_range(auth_client):
    # 400 dní je nad limitem 365 — service vyhodí ExchangeRateError -> 502
    r = auth_client.get("/api/average?base=USD&symbols=EUR&days=400")
    assert r.status_code == 502


@rsps_lib.activate
def test_api_latest_upstream_error(auth_client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=503)
    r = auth_client.get("/api/latest?base=USD")
    assert r.status_code == 502


def test_api_logs_requires_auth(client):
    r = client.get("/api/logs")
    assert r.status_code == 401


def test_api_logs_accessible_when_logged_in(auth_client):
    r = auth_client.get("/api/logs")
    assert r.status_code == 200
    assert "logs" in r.get_json()
