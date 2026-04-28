"""Sprint F tests for backend.app.services.secrets (KMS encryption helper)."""
import base64
from unittest.mock import MagicMock, patch

from backend.app.services import secrets as secrets_svc

PATCH_CLIENT = "backend.app.services.secrets._kms_client"


def _make_fake_kms(plaintext_to_ciphertext: dict[bytes, bytes]):
    """Build a fake KMS client whose encrypt/decrypt round-trips the given mapping."""
    client = MagicMock()

    def encrypt(request):
        pt = request["plaintext"]
        ct = plaintext_to_ciphertext.get(pt, b"FAKE-CIPHER:" + pt)
        return MagicMock(ciphertext=ct)

    def decrypt(request):
        ct = request["ciphertext"]
        for pt, expected_ct in plaintext_to_ciphertext.items():
            if ct == expected_ct:
                return MagicMock(plaintext=pt)
        # Default reverse the FAKE-CIPHER prefix
        if ct.startswith(b"FAKE-CIPHER:"):
            return MagicMock(plaintext=ct[len(b"FAKE-CIPHER:"):])
        raise ValueError(f"Unknown ciphertext: {ct!r}")

    client.encrypt.side_effect = encrypt
    client.decrypt.side_effect = decrypt
    return client


def test_kms_key_name_includes_env_and_project():
    name = secrets_svc.kms_key_name()
    assert "projects/masteko-fm" in name
    assert "/cryptoKeys/drive-tokens" in name
    assert "keyRings/mfm-secrets-" in name


def test_encrypt_decrypt_roundtrip():
    fake = _make_fake_kms({b"my-secret-token": b"ABCDEF"})
    secrets_svc._kms_client.cache_clear()
    with patch(PATCH_CLIENT, return_value=fake):
        ciphertext_b64 = secrets_svc.encrypt("my-secret-token")
        # Should be valid base64 of the fake ciphertext
        assert base64.b64decode(ciphertext_b64) == b"ABCDEF"
        # Round-trip
        plaintext = secrets_svc.decrypt(ciphertext_b64)
        assert plaintext == "my-secret-token"


def test_encrypt_rejects_empty():
    secrets_svc._kms_client.cache_clear()
    with patch(PATCH_CLIENT, return_value=MagicMock()):
        try:
            secrets_svc.encrypt("")
            raised = False
        except ValueError:
            raised = True
        assert raised


def test_decrypt_rejects_empty():
    secrets_svc._kms_client.cache_clear()
    with patch(PATCH_CLIENT, return_value=MagicMock()):
        try:
            secrets_svc.decrypt("")
            raised = False
        except ValueError:
            raised = True
        assert raised


def test_is_kms_available_true_when_client_imports():
    secrets_svc._kms_client.cache_clear()
    with patch(PATCH_CLIENT, return_value=MagicMock()):
        assert secrets_svc.is_kms_available() is True


def test_is_kms_available_false_when_client_raises():
    secrets_svc._kms_client.cache_clear()
    with patch(PATCH_CLIENT, side_effect=Exception("kms unavailable")):
        assert secrets_svc.is_kms_available() is False


def test_unicode_token_roundtrip():
    """Drive tokens are ASCII-safe but make sure UTF-8 still round-trips."""
    fake = _make_fake_kms({})
    secrets_svc._kms_client.cache_clear()
    with patch(PATCH_CLIENT, return_value=fake):
        token = "ya29.A0_eXample-tøkén"
        ct = secrets_svc.encrypt(token)
        assert secrets_svc.decrypt(ct) == token
