import responses as rsps_lib
from datetime import date, timedelta

FAKE_LATEST = {
    "success": True,
    "base": "EUR",
    "rates": {"USD": 1.10, "JPY": 160.0, "CZK": 25.0},
}

FAKE_HISTORICAL = {
    "success": True,
    "historical": True,
    "base": "EUR",
    "rates": {"USD": 1.08, "CZK": 24.8},
}

TODAY = date.today().isoformat()
WEEK_AGO = (date.today() - timedelta(days=6)).isoformat()


@rsps_lib.activate
def test_api_latest(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    r = client.get("/api/latest?base=EUR&symbols=USD,JPY")
    assert r.status_code == 200
    assert r.get_json()["success"] is True


@rsps_lib.activate
def test_api_strongest_returns_max(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    r = client.get("/api/strongest?base=EUR&symbols=USD,JPY,CZK")
    assert r.status_code == 200
    assert r.get_json()["currency"] == "JPY"  # 160 je max


@rsps_lib.activate
def test_api_weakest_returns_min(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    r = client.get("/api/weakest?base=EUR&symbols=USD,JPY,CZK")
    assert r.status_code == 200
    assert r.get_json()["currency"] == "USD"  # 1.10 je min


def test_api_strongest_missing_symbols(client):
    r = client.get("/api/strongest?base=EUR")
    assert r.status_code == 400


def test_api_weakest_missing_symbols(client):
    r = client.get("/api/weakest?base=EUR")
    assert r.status_code == 400


def test_api_invalid_currency(client):
    r = client.get("/api/latest?base=XX1")
    assert r.status_code == 400


@rsps_lib.activate
def test_api_average_date_range(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", json=FAKE_HISTORICAL)
    r = client.get(f"/api/average?base=EUR&symbols=USD,CZK&start_date={WEEK_AGO}&end_date={TODAY}")
    assert r.status_code == 200
    data = r.get_json()
    assert "USD" in data["averages"]
    assert data["start_date"] == WEEK_AGO


def test_api_average_missing_symbols(client):
    r = client.get(f"/api/average?base=EUR&start_date={WEEK_AGO}&end_date={TODAY}")
    assert r.status_code == 400


def test_api_average_invalid_date_range(client):
    r = client.get("/api/average?base=EUR&symbols=USD&start_date=2024-01-10&end_date=2024-01-01")
    assert r.status_code == 400


@rsps_lib.activate
def test_api_latest_upstream_error(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=503)
    r = client.get("/api/latest?base=EUR")
    assert r.status_code == 502
