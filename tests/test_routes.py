import responses as rsps_lib

# /live vrací USD quotes s prefixem
FAKE_LIVE = {
    "success": True,
    "source": "USD",
    "quotes": {"USDEUR": 0.04, "USDUSD": 1.0, "USDCZK": 1.0},
}

# /timeframe pro average_rates
FAKE_TIMEFRAME = {
    "success": True,
    "quotes": {
        "2024-01-14": {"USDEUR": 0.041, "USDUSD": 1.0},
        "2024-01-15": {"USDEUR": 0.040, "USDUSD": 1.0},
    },
}


def test_index_get(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Měnové kurzy".encode() in r.data


@rsps_lib.activate
def test_index_post_valid(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", json=FAKE_TIMEFRAME)
    r = client.post("/", data={"base": "USD", "symbols": ["EUR"], "days": "2"})
    assert r.status_code == 200
    assert b"EUR" in r.data


def test_index_post_no_symbols(client):
    r = client.post("/", data={"base": "USD", "symbols": [], "days": "7"})
    assert r.status_code == 200
    assert "Vyber alespoň jednu měnu".encode("utf-8") in r.data


def test_index_post_invalid_days_string(client):
    r = client.post("/", data={"base": "USD", "symbols": ["EUR"], "days": "abc"})
    assert r.status_code == 200
    assert "celé číslo".encode("utf-8") in r.data


def test_index_post_days_out_of_range(client):
    r = client.post("/", data={"base": "USD", "symbols": ["EUR"], "days": "400"})
    assert r.status_code == 200
    assert "365".encode("utf-8") in r.data


@rsps_lib.activate
def test_index_post_api_error(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=500)
    r = client.post("/", data={"base": "USD", "symbols": ["EUR"], "days": "7"})
    assert r.status_code == 200
    assert "Chyba".encode("utf-8") in r.data
