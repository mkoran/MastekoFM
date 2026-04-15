"""Tests for CSV connector."""
from backend.app.connectors.csv_connector import discover_fields, fetch_data, parse_csv
from backend.app.models.datasource import FieldMapping

SAMPLE_CSV = b"name,amount,rate,active\nLand Cost,2500000,5%,true\nRent,1850,3.5%,false\n"


def test_parse_csv():
    rows = parse_csv(SAMPLE_CSV)
    assert len(rows) == 2
    assert rows[0]["name"] == "Land Cost"
    assert rows[0]["amount"] == "2500000"


def test_discover_fields():
    fields = discover_fields(SAMPLE_CSV)
    assert len(fields) == 4
    names = [f.name for f in fields]
    assert "name" in names
    assert "amount" in names

    amount_field = next(f for f in fields if f.name == "amount")
    assert amount_field.inferred_type == "number"

    rate_field = next(f for f in fields if f.name == "rate")
    assert rate_field.inferred_type == "percentage"

    active_field = next(f for f in fields if f.name == "active")
    assert active_field.inferred_type == "boolean"


def test_fetch_data():
    mappings = [
        FieldMapping(source_field="amount", assumption_key="land_cost"),
        FieldMapping(source_field="rate", assumption_key="cap_rate"),
    ]
    data = fetch_data(SAMPLE_CSV, mappings)
    assert data["amount"] == "2500000"
    assert data["rate"] == "5%"


def test_empty_csv():
    fields = discover_fields(b"")
    assert fields == []
