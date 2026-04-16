"""Tests for the ScenarioStore adapter (GCS and Drive XLSX backends)."""
from unittest.mock import patch

import pytest

from backend.app.services import scenario_store


def test_get_store_defaults_to_gcs():
    assert scenario_store.get_store(None).kind == "gcs"
    assert scenario_store.get_store("gcs").kind == "gcs"
    assert scenario_store.get_store("drive_xlsx").kind == "drive_xlsx"
    # Unknown kind falls back to GCS rather than raising — keeps legacy docs safe.
    assert scenario_store.get_store("future_kind").kind == "gcs"


def test_store_for_scenario_prefers_storage_kind_field():
    scn = {"storage_kind": "drive_xlsx", "drive_file_id": "abc"}
    assert scenario_store.store_for_scenario(scn).kind == "drive_xlsx"


def test_store_for_scenario_infers_from_drive_file_id_when_kind_missing():
    """Legacy scenario docs don't have storage_kind — fall back to inference."""
    assert scenario_store.store_for_scenario({"drive_file_id": "abc"}).kind == "drive_xlsx"
    assert scenario_store.store_for_scenario({"storage_path": "x.xlsx"}).kind == "gcs"


@patch("backend.app.services.scenario_store.storage_service")
def test_gcs_store_read(mock_storage):
    mock_storage.download_xlsx.return_value = b"xlsx bytes"
    store = scenario_store.GCSStore()
    content = store.read_bytes({"storage_path": "excel_projects/x/y/inputs_v1.xlsx"})
    assert content == b"xlsx bytes"
    mock_storage.download_xlsx.assert_called_once_with("excel_projects/x/y/inputs_v1.xlsx")


def test_gcs_store_read_rejects_missing_path():
    store = scenario_store.GCSStore()
    with pytest.raises(ValueError, match="no storage_path"):
        store.read_bytes({})


@patch("backend.app.services.scenario_store.storage_service")
def test_gcs_store_write_produces_versioned_path(mock_storage):
    store = scenario_store.GCSStore()
    result = store.write_bytes(
        project_code="proj",
        scenario_code="scn",
        kind_label="inputs",
        version=3,
        filename="proj_scn.xlsx",
        content=b"abc",
    )
    assert result["storage_kind"] == "gcs"
    assert result["storage_path"] == "excel_projects/proj/scn/inputs_v3.xlsx"
    assert result["drive_file_id"] is None
    assert result["size_bytes"] == 3
    mock_storage.upload_xlsx.assert_called_once()


@patch("backend.app.services.scenario_store.drive_service")
def test_drive_xlsx_store_write_creates_new_file(mock_drive):
    mock_drive.upload_file.return_value = "new-file-id"
    store = scenario_store.DriveXlsxStore()
    result = store.write_bytes(
        project_code="proj",
        scenario_code="scn",
        kind_label="inputs",
        version=1,
        filename="scn.xlsx",
        content=b"xlsx",
        existing={"drive_folder_id": "folder-1"},
        user_access_token="tok",
    )
    assert result["storage_kind"] == "drive_xlsx"
    assert result["drive_file_id"] == "new-file-id"
    assert result["storage_path"] is None
    assert result["size_bytes"] == 4
    mock_drive.upload_file.assert_called_once_with(
        "folder-1", "scn.xlsx", b"xlsx", scenario_store.XLSX_MIME, user_access_token="tok",
    )


@patch("backend.app.services.scenario_store.drive_service")
def test_drive_xlsx_store_write_overwrites_existing_file(mock_drive):
    """Re-uploading an inputs file for a Drive scenario must replace content in place."""
    mock_drive.update_file_content.return_value = "same-file-id"
    store = scenario_store.DriveXlsxStore()
    result = store.write_bytes(
        project_code="proj",
        scenario_code="scn",
        kind_label="inputs",
        version=2,
        filename="scn.xlsx",
        content=b"new bytes",
        existing={"drive_folder_id": "folder-1", "drive_file_id": "same-file-id"},
        user_access_token="tok",
    )
    assert result["drive_file_id"] == "same-file-id"
    mock_drive.update_file_content.assert_called_once()
    mock_drive.upload_file.assert_not_called()


@patch("backend.app.services.scenario_store.drive_service")
def test_drive_xlsx_store_read(mock_drive):
    mock_drive.download_file.return_value = b"xlsx bytes"
    store = scenario_store.DriveXlsxStore()
    content = store.read_bytes({"drive_file_id": "abc"}, user_access_token="tok")
    assert content == b"xlsx bytes"
    mock_drive.download_file.assert_called_once_with("abc", user_access_token="tok")


def test_drive_xlsx_store_write_requires_folder_context():
    store = scenario_store.DriveXlsxStore()
    with pytest.raises(ValueError, match="drive_folder_id"):
        store.write_bytes(
            project_code="p", scenario_code="s", kind_label="inputs",
            version=1, filename="a.xlsx", content=b"x", existing={},
        )


def test_drive_xlsx_store_open_url_format():
    store = scenario_store.DriveXlsxStore()
    url = store.open_url({"drive_file_id": "abc123"})
    assert url == "https://docs.google.com/spreadsheets/d/abc123/edit"


@patch("backend.app.services.scenario_store.storage_service")
def test_gcs_store_open_url_uses_public_url_helper(mock_storage):
    mock_storage.public_url.return_value = "https://example/path"
    store = scenario_store.GCSStore()
    assert store.open_url({"storage_path": "x.xlsx"}) == "https://example/path"


def test_both_stores_return_none_open_url_when_no_artifact():
    assert scenario_store.GCSStore().open_url({}) is None
    assert scenario_store.DriveXlsxStore().open_url({}) is None


@patch("backend.app.services.scenario_store.drive_service")
def test_drive_store_read_raises_on_download_failure(mock_drive):
    mock_drive.download_file.return_value = None  # Drive SDK returns None on error
    with pytest.raises(RuntimeError, match="Drive download failed"):
        scenario_store.DriveXlsxStore().read_bytes({"drive_file_id": "x"}, user_access_token="t")


def test_mock_sanity():
    """Guard against test-mock drift: verify every public store has the required method set."""
    for store in (scenario_store.GCSStore(), scenario_store.DriveXlsxStore()):
        assert hasattr(store, "kind")
        assert callable(store.read_bytes)
        assert callable(store.write_bytes)
        assert callable(store.open_url)


def test_mock_call_count_on_gcs_write():
    store = scenario_store.GCSStore()
    with patch("backend.app.services.scenario_store.storage_service") as mock_storage:
        mock_storage.upload_xlsx.return_value = "https://x"
        for v in (1, 2, 3):
            store.write_bytes(
                project_code="p", scenario_code="s", kind_label="inputs",
                version=v, filename="p_s.xlsx", content=b"ab",
            )
        assert mock_storage.upload_xlsx.call_count == 3


def test_output_kind_puts_file_in_outputs_subfolder():
    store = scenario_store.GCSStore()
    with patch("backend.app.services.scenario_store.storage_service") as mock_storage:
        mock_storage.upload_xlsx.return_value = "url"
        result = store.write_bytes(
            project_code="proj", scenario_code="scn", kind_label="outputs",
            version=99, filename="20260416_out.xlsx", content=b"x",
        )
        assert result["storage_path"] == "excel_projects/proj/scn/outputs/20260416_out.xlsx"


def test_constants_match_expected_values():
    assert scenario_store.STORAGE_KIND_GCS == "gcs"
    assert scenario_store.STORAGE_KIND_DRIVE_XLSX == "drive_xlsx"
    assert scenario_store.XLSX_MIME.startswith("application/vnd.openxmlformats")
