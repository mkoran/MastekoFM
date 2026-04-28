# Sprint F — KMS encryption for persisted Drive tokens

> Status: ✅ shipped (code) on `epic/sprint-b-cleanup`. Activates per env when
> `./scripts/infra/setup_kms_drive_tokens.sh <env>` runs (creates keyring +
> key + IAM). Until then, the runs router falls back to plaintext storage
> with a logged warning — same behavior as before this sprint.

## Why

Sprint C persisted the user's Drive OAuth access token on the Run doc in
plaintext. Justification at the time: Firestore is encrypted at rest by
Google. But that's a single layer of defense:
  - A Firestore export / backup contains plaintext tokens.
  - Anyone with `roles/datastore.user` (which is broadly granted internally)
    can read tokens.
  - Compromise of the deployer SA's `datastore.user` access yields usable
    Drive credentials.

Sprint F adds Cloud KMS as a second layer. Now to use a token an attacker
needs BOTH Firestore read AND `cloudkms.cryptoKeyDecrypter` on our key.

## Stories

| ID | Story | Status |
|---|---|---|
| F-01 | `services/secrets.py` — KMS encrypt/decrypt helpers + `is_kms_available()` | ✅ |
| F-02 | `routers/runs.py` — encrypt drive_token before persisting; fall back to plaintext if KMS unavailable | ✅ |
| F-03 | `routers/_run_worker.py` — try `drive_token_encrypted` first (decrypt), fall back to legacy `drive_token` plaintext | ✅ |
| F-04 | Clear BOTH fields on terminal status (success + failure paths) | ✅ |
| F-05 | `scripts/infra/setup_kms_drive_tokens.sh` — one-time per-env setup with 90d rotation | ✅ |
| F-06 | Pytest: round-trip, empty input rejection, KMS-unavailable fallback | ✅ |
| F-07 | Activate KMS on DEV (run setup script + redeploy) | 🔒 needs deploy |
| F-08 | Activate KMS on PROD | 🔒 needs deploy |

## Test count delta
- Before: **94/94** (after Sprint C)
- After: **102/102** (+7 secrets, +1 worker decrypt path)

## Schema additions (additive — no migration required)

`Run` Firestore docs gain one new optional field:

| Field | Type | Meaning |
|---|---|---|
| `drive_token_encrypted` | `string \| null` | base64-encoded KMS ciphertext of the user's Drive token |

The legacy `drive_token` (plaintext) field stays for back-compat. Worker
prefers `drive_token_encrypted`, falls back to `drive_token`. New writes
populate one OR the other based on `is_kms_available()` — never both.

## Operational concerns addressed

- **Rotation**: KMS auto-rotates every 90 days. Old ciphertexts decrypt with
  old key versions automatically (KMS handles versioning transparently).
- **Cost**: ~$0.06/key/month + $0.03 per 10K operations. At MastekoFM's
  expected volume (~hundreds of runs/month) this is <$1/month.
- **Latency**: KMS encrypt/decrypt is ~5-20ms per call. We do one of each
  per Run, so adds <40ms to the critical path. Negligible vs. ~2s Hello
  World engine time, ~17s Campus Adele.
- **Key compromise**: If our SA's KMS access leaks, we rotate the key
  (one gcloud command) and existing runs become unrecoverable. Acceptable —
  failed-to-decrypt runs just need to be re-run by the user.

## Marc's per-env one-time activation

```bash
./scripts/infra/setup_kms_drive_tokens.sh dev
# then trigger a deploy (push to epic branch) so the new revision picks up
# the env (no env-var change needed — the script creates the keyring at the
# expected name; the API code finds it by convention).

./scripts/infra/setup_kms_drive_tokens.sh prod
# same for prod after dev is verified
```

## Future (V3 if needed)

- Move from token-storage-on-doc to token-broker-pattern (worker requests a
  fresh OAuth token from a dedicated /api/internal/drive-token endpoint)
- Use service-account delegation for non-personal Drive access (eliminates
  the 1h token TTL problem entirely)
