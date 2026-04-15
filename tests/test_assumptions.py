"""Tests for assumption endpoints."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

AUTH = {"Authorization": "Bearer dev-test@example.com"}
BASE = "/api/projects/proj-1/assumptions"


@patch("backend.app.routers.assumptions._db")
def test_create_assumption(mock_db):
    """POST creates an assumption with history entry."""
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "asmp-1"
    mock_history_ref = MagicMock()
    mock_doc_ref.collection.return_value = mock_history_ref

    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

    response = client.post(
        BASE,
        json={"key": "land_cost", "display_name": "Land Cost", "category": "Construction", "type": "currency", "value": 2500000},
        headers=AUTH,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"] == "land_cost"
    assert data["value"] == 2500000.0
    assert data["version"] == 1
    mock_doc_ref.set.assert_called_once()
    mock_history_ref.add.assert_called_once()


@patch("backend.app.routers.assumptions._db")
def test_list_assumptions(mock_db):
    """GET lists assumptions."""
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.id = "asmp-1"
    mock_doc.to_dict.return_value = {
        "key": "rent", "display_name": "Rent", "category": "Revenue",
        "type": "currency", "value": 1850.0, "version": 1,
        "created_at": now, "updated_at": now,
    }
    mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = [mock_doc]

    response = client.get(BASE, headers=AUTH)
    assert response.status_code == 200
    assert len(response.json()) == 1


@patch("backend.app.routers.assumptions._db")
def test_update_assumption_creates_history(mock_db):
    """PUT on value change creates history entry."""
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "key": "rent", "display_name": "Rent", "category": "Revenue",
        "type": "currency", "value": 1850.0, "version": 1,
        "created_at": now, "updated_at": now,
    }
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_history_ref = MagicMock()
    mock_doc_ref.collection.return_value = mock_history_ref

    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

    response = client.put(f"{BASE}/asmp-1", json={"value": 2000}, headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["value"] == 2000.0
    assert data["version"] == 2
    mock_history_ref.add.assert_called_once()


def test_validate_percentage():
    """Percentage > 1 is auto-converted to decimal."""
    from backend.app.models.assumption import AssumptionType
    from backend.app.services.assumption_engine import validate_assumption_value

    assert validate_assumption_value(AssumptionType.PERCENTAGE, 5) == 0.05
    assert validate_assumption_value(AssumptionType.PERCENTAGE, 0.05) == 0.05


def test_validate_boolean():
    """Boolean coercion works."""
    from backend.app.models.assumption import AssumptionType
    from backend.app.services.assumption_engine import validate_assumption_value

    assert validate_assumption_value(AssumptionType.BOOLEAN, "true") is True
    assert validate_assumption_value(AssumptionType.BOOLEAN, "false") is False
    assert validate_assumption_value(AssumptionType.BOOLEAN, True) is True


def test_assumptions_requires_auth():
    response = client.get(BASE)
    assert response.status_code == 401
