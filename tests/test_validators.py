import pytest
from datetime import date, timedelta
from app import create_app
from app.validators import (
    validate_currency, validate_currency_list,
    validate_date, validate_date_range, ValidationError,
)


@pytest.fixture(autouse=True)
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


def test_valid_currency():
    assert validate_currency("eur") == "EUR"
    assert validate_currency("USD") == "USD"


def test_invalid_currency_format():
    with pytest.raises(ValidationError, match="Neplatný"):
        validate_currency("US1")


def test_unsupported_currency():
    with pytest.raises(ValidationError, match="Nepodporovaná"):
        validate_currency("XYZ")


def test_currency_list_valid():
    result = validate_currency_list(["USD", "EUR", "CZK"])
    assert result == ["USD", "EUR", "CZK"]


def test_currency_list_empty_raises():
    with pytest.raises(ValidationError):
        validate_currency_list([], min_count=1)


def test_valid_date():
    assert validate_date("2024-01-15") == date(2024, 1, 15)


def test_invalid_date_format():
    with pytest.raises(ValidationError, match="Neplatné datum"):
        validate_date("15-01-2024")


def test_invalid_date_string():
    with pytest.raises(ValidationError):
        validate_date("not-a-date")


def test_valid_date_range():
    start, end = validate_date_range("2024-01-01", "2024-01-07")
    assert start < end


def test_date_range_start_after_end():
    with pytest.raises(ValidationError, match="před"):
        validate_date_range("2024-01-10", "2024-01-01")


def test_date_range_too_long():
    start = (date.today() - timedelta(days=400)).isoformat()
    end = date.today().isoformat()
    with pytest.raises(ValidationError, match="365"):
        validate_date_range(start, end)


def test_date_range_future_end():
    future = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError, match="budoucnosti"):
        validate_date_range(date.today().isoformat(), future)
