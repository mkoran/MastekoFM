"""Sprint F — KMS-backed encryption for sensitive values stored in Firestore.

Today's only consumer: the user's Drive OAuth access token persisted on Run
docs (Sprint C). Tokens previously sat in plaintext relying on Firestore's
encryption-at-rest. KMS adds a defense-in-depth layer:

  - Tokens never appear in Firestore exports / backups in plaintext.
  - Compromise of a Firestore-read role doesn't yield usable Drive credentials
    (still need cloudkms.decrypt on our key).
  - Key rotation is one gcloud command (KMS rewraps in place).

Per-env keys: mfm-secrets-dev / mfm-secrets-prod inside `mfm-secrets-{env}`
keyring in northamerica-northeast1. Created by
scripts/infra/setup_kms_drive_tokens.sh.

Graceful fallback: if KMS isn't configured (local dev / first deploy before
the setup script ran), is_kms_available() returns False and the caller can
choose to store plaintext + emit a warning. The runs router uses this so
the deploy that introduces this feature doesn't break.
"""
from __future__ import annotations

import base64
import logging
from functools import lru_cache

from backend.app.config import settings

logger = logging.getLogger(__name__)


def _env_label() -> str:
    """`dev` / `prod` / `local` — drives the keyring name."""
    return settings.environment if settings.environment in ("dev", "prod") else "local"


def kms_key_name() -> str:
    """Full KMS key resource name, e.g.
    projects/masteko-fm/locations/northamerica-northeast1/keyRings/mfm-secrets-dev/cryptoKeys/drive-tokens
    """
    return (
        f"projects/{settings.gcp_project}/locations/{settings.gcp_region}"
        f"/keyRings/mfm-secrets-{_env_label()}/cryptoKeys/drive-tokens"
    )


@lru_cache(maxsize=1)
def _kms_client():
    """Lazy import + memoized KMS client. Tests can patch this to inject a fake."""
    from google.cloud import kms

    return kms.KeyManagementServiceClient()


def is_kms_available() -> bool:
    """True if we can reach KMS (creds + key both present). Cheap probe — does
    not actually encrypt; tries to instantiate the client. If the key is wrong
    this returns True but encrypt() will raise — that's intended (loud failure
    is better than silent fallback when KMS was supposed to work).
    """
    try:
        _kms_client()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.info("KMS unavailable (%s); fallback path will be taken", exc)
        return False


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns base64-encoded ciphertext suitable for
    Firestore storage."""
    if not plaintext:
        raise ValueError("encrypt() got empty plaintext")
    client = _kms_client()
    resp = client.encrypt(
        request={"name": kms_key_name(), "plaintext": plaintext.encode("utf-8")}
    )
    return base64.b64encode(resp.ciphertext).decode("ascii")


def decrypt(ciphertext_b64: str) -> str:
    """Reverse of encrypt(). Raises on any KMS error."""
    if not ciphertext_b64:
        raise ValueError("decrypt() got empty ciphertext")
    client = _kms_client()
    resp = client.decrypt(
        request={
            "name": kms_key_name(),
            "ciphertext": base64.b64decode(ciphertext_b64),
        }
    )
    return resp.plaintext.decode("utf-8")
