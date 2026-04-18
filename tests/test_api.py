import responses as rsps_lib

FAKE_LATEST = {
    "success": True,
    "base": "USD",
    "rates": {"EUR": 0.92, "CZK": 23.5, "JPY": 149.0},
}

FAKE_HISTORICAL = {
    "success": True,
    "historical": True,
    "base": "USD",
    "rates": {"EUR": 0.91, "CZK": 23.1},
}


@rsps_lib.activate
def test_api_latest(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    r = client.get("/api/latest?base=USD&symbols=EUR,CZK")
    assert r.status_code == 200
    assert r.get_json()["success"] is True


@rsps_lib.activate
def test_api_strongest(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    r = client.get("/api/strongest?base=USD&symbols=EUR,CZK,JPY")
    assert r.status_code == 200
    assert r.get_json()["currency"] == "EUR"


@rsps_lib.activate
def test_api_weakest(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    r = client.get("/api/weakest?base=USD&symbols=EUR,CZK,JPY")
    assert r.status_code == 200
    assert r.get_json()["currency"] == "JPY"


def test_api_strongest_missing_symbols(client):
    r = client.get("/api/strongest?base=USD")
    assert r.status_code == 400


def test_api_weakest_missing_symbols(client):
    r = client.get("/api/weakest?base=USD")
    assert r.status_code == 400


def test_api_average_missing_symbols(client):
    r = client.get("/api/average?base=USD")
    assert r.status_code == 400


@rsps_lib.activate
def test_api_average(client):
    rsps_lib.add(
        rsps_lib.GET, "https://api.exchangerate.host/historical",
        json=FAKE_HISTORICAL,
    )
    r = client.get("/api/average?base=USD&symbols=EUR,CZK&days=2")
    assert r.status_code == 200
    assert "EUR" in r.get_json()["averages"]


@rsps_lib.activate
def test_api_latest_upstream_error(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=503)
    r = client.get("/api/latest?base=USD")
    assert r.status_code == 502
