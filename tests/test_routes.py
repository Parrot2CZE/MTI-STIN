import responses as rsps_lib

FAKE_LATEST = {
    "success": True,
    "base": "CZK",
    "rates": {"EUR": 0.04, "USD": 0.043},
}

FAKE_HISTORICAL = {
    "success": True,
    "historical": True,
    "base": "CZK",
    "rates": {"EUR": 0.041, "USD": 0.042},
}


def test_index_get(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Měnové kurzy".encode() in r.data


@rsps_lib.activate
def test_index_post_valid(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", json=FAKE_HISTORICAL)
    r = client.post("/", data={"base": "CZK", "symbols": ["EUR", "USD"], "days": "2"})
    assert r.status_code == 200
    assert b"EUR" in r.data


def test_index_post_no_symbols(client):
    r = client.post("/", data={"base": "CZK", "symbols": [], "days": "7"})
    assert r.status_code == 200
    assert "Vyber alespoň jednu měnu".encode("utf-8") in r.data


def test_index_post_invalid_days_string(client):
    r = client.post("/", data={"base": "CZK", "symbols": ["EUR"], "days": "abc"})
    assert r.status_code == 200
    assert "celé číslo".encode("utf-8") in r.data


def test_index_post_days_out_of_range(client):
    r = client.post("/", data={"base": "CZK", "symbols": ["EUR"], "days": "400"})
    assert r.status_code == 200
    assert "365".encode("utf-8") in r.data


@rsps_lib.activate
def test_index_post_api_error(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=500)
    r = client.post("/", data={"base": "CZK", "symbols": ["EUR"], "days": "7"})
    assert r.status_code == 200
    assert "Chyba".encode("utf-8") in r.data
