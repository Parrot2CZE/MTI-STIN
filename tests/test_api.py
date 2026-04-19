import responses as rsps_lib

FAKE_LIVE = {
    "success": True,
    "source": "USD",
    "quotes": {"USDEUR": 0.92, "USDCZK": 23.5, "USDJPY": 149.0},
}

FAKE_TIMEFRAME = {
    "success": True,
    "quotes": {
        "2024-01-14": {"USDEUR": 0.91, "USDCZK": 23.1},
        "2024-01-15": {"USDEUR": 0.92, "USDCZK": 23.5},
    },
}


@rsps_lib.activate
def test_api_latest(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE)
    r = client.get("/api/latest?base=USD&symbols=EUR,CZK")
    assert r.status_code == 200
    assert r.get_json()["success"] is True


@rsps_lib.activate
def test_api_strongest(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE)
    r = client.get("/api/strongest?base=USD&symbols=EUR,CZK,JPY")
    assert r.status_code == 200
    data = r.get_json()
    assert data["currency"] == "EUR"
    assert abs(data["rate"] - 0.92) < 0.001


@rsps_lib.activate
def test_api_weakest(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE)
    r = client.get("/api/weakest?base=USD&symbols=EUR,CZK,JPY")
    assert r.status_code == 200
    data = r.get_json()
    assert data["currency"] == "JPY"
    assert abs(data["rate"] - 149.0) < 0.001


def test_api_strongest_missing_symbols(client):
    r = client.get("/api/strongest?base=USD")
    assert r.status_code == 400
    assert r.get_json()["success"] is False


def test_api_weakest_missing_symbols(client):
    r = client.get("/api/weakest?base=USD")
    assert r.status_code == 400


def test_api_average_missing_symbols(client):
    r = client.get("/api/average?base=USD")
    assert r.status_code == 400


def test_api_average_invalid_days(client):
    r = client.get("/api/average?base=USD&symbols=EUR&days=abc")
    assert r.status_code == 400


@rsps_lib.activate
def test_api_average(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", json=FAKE_TIMEFRAME)
    r = client.get("/api/average?base=USD&symbols=EUR,CZK&days=2")
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert "EUR" in body["averages"]
    assert body["days"] == 2


@rsps_lib.activate
def test_api_average_days_out_of_range(client):
    r = client.get("/api/average?base=USD&symbols=EUR&days=400")
    assert r.status_code == 502


@rsps_lib.activate
def test_api_latest_upstream_error(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=503)
    r = client.get("/api/latest?base=USD")
    assert r.status_code == 502
