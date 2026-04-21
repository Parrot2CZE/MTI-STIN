"""
Testy UI rout — renderování šablon, zpracování formuláře, flash zprávy.
"""

import responses as rsps_lib

FAKE_LIVE = {
    "success": True,
    "source": "USD",
    "quotes": {"USDUSD": 1.0, "USDEUR": 0.92, "USDCZK": 23.5},
}

FAKE_TIMEFRAME = {
    "success": True,
    "quotes": {
        "2024-01-14": {"USDEUR": 0.91, "USDCZK": 23.1},
        "2024-01-15": {"USDEUR": 0.92, "USDCZK": 23.5},
    },
}


def test_index_redirects_when_not_logged_in(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "login" in r.headers["Location"]


def test_login_page_loads(client):
    r = client.get("/login")
    assert r.status_code == 200


def test_index_get_when_logged_in(auth_client):
    r = auth_client.get("/")
    assert r.status_code == 200
    assert "Měnové kurzy".encode() in r.data or "Exchange Rates".encode() in r.data


@rsps_lib.activate
def test_index_post_valid(auth_client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", json=FAKE_LIVE)
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/timeframe", json=FAKE_TIMEFRAME)
    r = auth_client.post("/", data={"base": "USD", "symbols": ["EUR", "CZK"], "days": "2"})
    assert r.status_code == 200
    assert b"EUR" in r.data


def test_index_post_no_symbols(auth_client):
    r = auth_client.post("/", data={"base": "USD", "symbols": [], "days": "7"})
    assert r.status_code == 200
    assert "alespoň".encode("utf-8") in r.data or b"least" in r.data


def test_index_post_invalid_days_string(auth_client):
    r = auth_client.post("/", data={"base": "USD", "symbols": ["EUR"], "days": "abc"})
    assert r.status_code == 200
    assert "celé číslo".encode("utf-8") in r.data or b"integer" in r.data


def test_index_post_days_out_of_range(auth_client):
    r = auth_client.post("/", data={"base": "USD", "symbols": ["EUR"], "days": "400"})
    assert r.status_code == 200
    assert "365".encode("utf-8") in r.data


@rsps_lib.activate
def test_index_post_api_error(auth_client):
    rsps_lib.add(rsps_lib.GET, "https://api.exchangerate.host/live", status=500)
    r = auth_client.post("/", data={"base": "USD", "symbols": ["EUR"], "days": "7"})
    assert r.status_code == 200
    assert "Chyba".encode("utf-8") in r.data or b"Error" in r.data


def test_lang_switch_cs(auth_client):
    r = auth_client.get("/lang/cs", follow_redirects=True)
    assert r.status_code == 200


def test_lang_switch_en(auth_client):
    r = auth_client.get("/lang/en", follow_redirects=True)
    assert r.status_code == 200


def test_404_returns_correct_status(auth_client):
    """Handler musí vrátit HTTP 404, ne 200 s chybovou stránkou."""
    r = auth_client.get("/neexistujici-stranka")
    assert r.status_code == 404


def test_404_renders_template(auth_client):
    """Šablona 404.html musí být renderována — ověříme přítomnost čísla 404 v obsahu."""
    r = auth_client.get("/neexistujici-stranka")
    assert b"404" in r.data
