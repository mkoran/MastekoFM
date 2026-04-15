"""Tests for data source sync — type inference and coercion."""
from backend.app.services.datasource_sync import coerce_value, infer_field_type


def test_infer_numeric():
    assert infer_field_type(["100", "200", "300"]) == "number"
    assert infer_field_type([1, 2.5, 3]) == "number"


def test_infer_currency():
    assert infer_field_type(["$1,000", "$2,500.00", "$100"]) == "currency"


def test_infer_percentage():
    assert infer_field_type(["5%", "10%", "3.5%"]) == "percentage"


def test_infer_boolean():
    assert infer_field_type(["true", "false", "yes"]) == "boolean"
    assert infer_field_type(["1", "0", "1"]) == "boolean"


def test_infer_date():
    assert infer_field_type(["2026-01-15", "2026-02-20"]) == "date"


def test_infer_text_default():
    assert infer_field_type(["hello", "world"]) == "text"
    assert infer_field_type([]) == "text"
    assert infer_field_type([None, ""]) == "text"


def test_coerce_number():
    assert coerce_value("1,234.56", "number") == 1234.56
    assert coerce_value("100", "number") == 100.0


def test_coerce_currency():
    assert coerce_value("$2,500.00", "currency") == 2500.0


def test_coerce_percentage():
    assert coerce_value("5%", "percentage") == 0.05
    assert coerce_value("0.05", "percentage") == 0.05


def test_coerce_boolean():
    assert coerce_value("true", "boolean") is True
    assert coerce_value("no", "boolean") is False


def test_coerce_none():
    assert coerce_value(None, "number") is None
