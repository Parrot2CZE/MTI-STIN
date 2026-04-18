import responses as rsps_lib
from datetime import date, timedelta

FAKE_LATEST = {
    "success": True,
    "base": "EUR",
    "rates": {"USD": 1.10, "CZK": 25.0},
}

FAKE_HISTORICAL = {
    "success": True,
    "historical": True,
    "base": "EUR",
    "rates": {"USD": 1.08, "CZK": 24.8},
}

TODAY = date.today().isoformat()
WEEK_AGO = (date.today() - timedelta(days=6)).isoformat()


def test_index_get(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Měnové kurzy".encode() in r.data


@rsps_lib.activate
def test_index_post_valid(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LATEST)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/historical", json=FAKE_HISTORICAL)
    r = client.post("/", data={
        "base": "EUR",
        "symbols": ["USD", "CZK"],
        "start_date": WEEK_AGO,
        "end_date": TODAY,
    })
    assert r.status_code == 200
    assert b"USD" in r.data


def test_index_post_no_symbols(client):
    r = client.post("/", data={
        "base": "EUR",
        "symbols": [],
        "start_date": WEEK_AGO,
        "end_date": TODAY,
    })
    assert r.status_code == 200
    assert "Vyber alespoň".encode("utf-8") in r.data


def test_index_post_invalid_date_range(client):
    r = client.post("/", data={
        "base": "EUR",
        "symbols": ["USD"],
        "start_date": TODAY,
        "end_date": WEEK_AGO,  # end < start → chyba
    })
    assert r.status_code == 200
    assert "před".encode("utf-8") in r.data


@rsps_lib.activate
def test_index_post_api_error(client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=500)
    r = client.post("/", data={
        "base": "EUR",
        "symbols": ["USD"],
        "start_date": WEEK_AGO,
        "end_date": TODAY,
    })
    assert r.status_code == 200
    assert "Chyba".encode("utf-8") in r.data
