"""
Testy persistentního úložiště uživatelského stavu.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolate_data_dir(tmp_path, monkeypatch):
    """
    Přesměruje _DATA_DIR do dočasného adresáře, aby testy
    nezapisovaly do skutečného data/ adresáře projektu.
    """
    import app.user_store as us
    monkeypatch.setattr(us, "_DATA_DIR", tmp_path)
    yield tmp_path


def test_load_nonexistent_user_returns_empty():
    from app.user_store import load_user_state
    assert load_user_state("nobody") == {}


def test_save_and_load_roundtrip():
    from app.user_store import save_user_state, load_user_state
    state = {"last_result": {"base": "EUR", "days": 7, "averages": {"USD": 1.08}}}
    save_user_state("testuser", state)
    loaded = load_user_state("testuser")
    assert loaded["last_result"]["base"] == "EUR"
    assert loaded["last_result"]["averages"]["USD"] == pytest.approx(1.08)


def test_save_overwrites_previous():
    from app.user_store import save_user_state, load_user_state
    save_user_state("testuser", {"last_result": {"base": "USD"}})
    save_user_state("testuser", {"last_result": {"base": "CZK"}})
    assert load_user_state("testuser")["last_result"]["base"] == "CZK"


def test_load_corrupted_file_returns_empty(tmp_path, monkeypatch):
    import app.user_store as us
    monkeypatch.setattr(us, "_DATA_DIR", tmp_path)
    # Zapíšeme neplatný JSON
    (tmp_path / "testuser.json").write_text("{ not valid json !!!", encoding="utf-8")
    from app.user_store import load_user_state
    assert load_user_state("testuser") == {}


def test_save_write_error_does_not_raise(monkeypatch):
    """Selhání zápisu (permissions, disk plný) nesmí shodit aplikaci."""
    import app.user_store as us
    def bad_open(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr("builtins.open", bad_open)
    from app.user_store import save_user_state
    # Nesmí vyhodit výjimku
    save_user_state("testuser", {"last_result": {}})


def test_username_sanitization(tmp_path, monkeypatch):
    import app.user_store as us
    monkeypatch.setattr(us, "_DATA_DIR", tmp_path)
    from app.user_store import save_user_state, load_user_state
    # Nebezpečné znaky v username se odstraní
    save_user_state("../evil/path", {"last_result": {"base": "USD"}})
    # Soubor musí být v tmp_path, ne mimo něj
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert ".." not in str(files[0])


def test_empty_username_falls_back_to_unknown(tmp_path, monkeypatch):
    import app.user_store as us
    monkeypatch.setattr(us, "_DATA_DIR", tmp_path)
    from app.user_store import save_user_state, load_user_state
    save_user_state("", {"last_result": {"base": "GBP"}})
    result = load_user_state("")
    assert result["last_result"]["base"] == "GBP"
