"""Tests for Airtable connector."""
import json
from unittest.mock import MagicMock, patch

from backend.app.connectors.airtable import discover_fields, fetch_data
from backend.app.models.datasource import FieldMapping

MOCK_RESPONSE = {
    "records": [
        {
            "id": "rec1",
            "fields": {"Name": "Property A", "Price": 2500000, "Cap Rate": "5.5%", "Active": True},
        },
        {
            "id": "rec2",
            "fields": {"Name": "Property B", "Price": 1800000, "Cap Rate": "6.0%", "Active": False},
        },
    ]
}


def _mock_urlopen(response_data):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


@patch("backend.app.connectors.airtable.urllib.request.urlopen")
def test_discover_fields(mock_urlopen):
    mock_urlopen.return_value = _mock_urlopen(MOCK_RESPONSE)
    fields = discover_fields("appXXX", "Properties", "fake-key")

    assert len(fields) == 4
    names = [f.name for f in fields]
    assert "Name" in names
    assert "Price" in names

    price_field = next(f for f in fields if f.name == "Price")
    assert price_field.inferred_type == "number"

    active_field = next(f for f in fields if f.name == "Active")
    assert active_field.inferred_type == "boolean"


@patch("backend.app.connectors.airtable.urllib.request.urlopen")
def test_fetch_data(mock_urlopen):
    single_record = {"records": [MOCK_RESPONSE["records"][0]]}
    mock_urlopen.return_value = _mock_urlopen(single_record)

    mappings = [
        FieldMapping(source_field="Price", assumption_key="land_cost"),
        FieldMapping(source_field="Cap Rate", assumption_key="cap_rate"),
    ]
    data = fetch_data("appXXX", "Properties", "fake-key", mappings)
    assert data["Price"] == 2500000
    assert data["Cap Rate"] == "5.5%"


@patch("backend.app.connectors.airtable.urllib.request.urlopen")
def test_empty_table(mock_urlopen):
    mock_urlopen.return_value = _mock_urlopen({"records": []})
    fields = discover_fields("appXXX", "Empty", "fake-key")
    assert fields == []
