"""Sprint F.1 tests for the user-token → SA-token Drive download fallback.

The fallback solves the case where the file is owned by Google account A
but the user is signed in with Google account B (drive.file scope only sees
files THIS app uploaded under the current account). The deployer SA has
broader `drive` scope and can read anything in the shared MastekoFM folder.
"""
from unittest.mock import patch

import pytest

from backend.app.services import pack_store

PATCH_DOWNLOAD = "backend.app.services.pack_store.drive_service.download_file"
PATCH_SA_TOKEN = "backend.app.services.pack_store._try_sa_drive_token"


def test_user_token_works_does_not_call_sa():
    """Happy path: user's token returns bytes — SA fallback never invoked."""
    with patch(PATCH_DOWNLOAD, return_value=b"file-bytes") as dl, \
         patch(PATCH_SA_TOKEN) as sa:
        result = pack_store._download_with_fallback("file-1", "user-token", "model")
    assert result == b"file-bytes"
    dl.assert_called_once_with("file-1", user_access_token="user-token")
    sa.assert_not_called()


def test_user_token_fails_then_sa_token_succeeds():
    """User's token returns None (Drive 404 or permission denied) → SA fallback wins."""
    call_args = []

    def download_side_effect(file_id, user_access_token=None):
        call_args.append(user_access_token)
        # First call (user token) returns None; second (SA token) returns bytes
        return None if user_access_token == "user-token" else b"sa-fetched-bytes"

    with patch(PATCH_DOWNLOAD, side_effect=download_side_effect), \
         patch(PATCH_SA_TOKEN, return_value="sa-token"):
        result = pack_store._download_with_fallback("file-1", "user-token", "pack")
    assert result == b"sa-fetched-bytes"
    assert call_args == ["user-token", "sa-token"]


def test_both_tokens_fail_raises_actionable_error():
    """User token fails AND SA token fails — raise with guidance toward fix."""
    with patch(PATCH_DOWNLOAD, return_value=None), \
         patch(PATCH_SA_TOKEN, return_value="sa-token"), pytest.raises(RuntimeError) as excinfo:
        pack_store._download_with_fallback("file-1", "user-token", "model")
    err = str(excinfo.value)
    assert "model file_id=file-1" in err
    assert "tried both user token and SA-fallback" in err
    assert "sign in with the owning account" in err.lower() or "share the masteko" in err.lower()


def test_no_user_token_skips_to_sa():
    """When no user token at all, jump straight to SA token."""
    call_args = []

    def download_side_effect(file_id, user_access_token=None):
        call_args.append(user_access_token)
        return b"sa-bytes"

    with patch(PATCH_DOWNLOAD, side_effect=download_side_effect), \
         patch(PATCH_SA_TOKEN, return_value="sa-token"):
        result = pack_store._download_with_fallback("file-1", None, "output_template")
    assert result == b"sa-bytes"
    # Only the SA token call should have happened (no user-token attempt)
    assert call_args == ["sa-token"]


def test_sa_mint_unavailable_falls_back_to_only_user_token_attempt():
    """If SA token mint fails (e.g., local dev without ADC), we try user token only."""
    with patch(PATCH_DOWNLOAD, return_value=None), \
         patch(PATCH_SA_TOKEN, return_value=None), pytest.raises(RuntimeError):
        pack_store._download_with_fallback("file-1", "user-token", "pack")


def test_load_model_compat_passes_user_token():
    """Sprint F.1: load_model_bytes_compat now accepts user_token."""
    with patch(PATCH_DOWNLOAD, return_value=b"model-bytes"):
        result = pack_store.load_model_bytes_compat(
            {"drive_file_id": "model-1"}, user_token="user-tok"
        )
    assert result == b"model-bytes"
