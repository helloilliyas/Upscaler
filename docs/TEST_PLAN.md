# Test plan

## Backend (implemented)

Run from `backend/`: `ruff check .`, `mypy app`, `python -m pytest -q`.
Model inference is mocked by the placeholder processor; no GPU is required.

| Area | File | Covers |
|---|---|---|
| Auth | `tests/test_auth.py` | bearer extraction, approved/rejected accounts, sub pinning, end-to-end verify |
| Upload validation | `tests/test_image_validation.py` | format/size/pixel limits, garbage bytes, mask alignment + PNG requirement |
| Output sizing | `tests/test_sizing.py` | 2×/4×/4K/8K rules, aspect preservation, orientation-aware boxes |
| Job service | `tests/test_jobs.py` | idempotency, ownership, transitions, deletion + file cleanup, expired result |
| API (e2e) | `tests/test_api.py` | health/me, submit→complete→download, ownership 403/404, delete, error mapping |
| Idempotency | `tests/test_idempotency.py` | repeated key returns same job at the HTTP layer |

## Later phases (not yet implemented)

- **Model integration:** input/output decodable, correct dimensions, no tile
  seams, mask affects only intended area, GPS removed, cancellation between stages.
- **Android unit:** ViewModel state, job-status mapping, retry decisions, output
  dimension calc, batch queue, history repository.
- **Android instrumentation:** Photo Picker, sign-in handling, mock-server upload,
  WorkManager chain, Gallery save, before/after slider, mask coordinate mapping,
  process death recovery.
- **Real device (S22):** Wi-Fi/mobile, background mode, large 8K result, 50-photo
  batch, network interruption, token expiration, reinstall/update.

## Visual quality review

Maintain a private benchmark folder (`input/ natural/ restore/ ultra/ notes.csv`)
scoring identity preservation, naturalness, sharpness, artifacts, colour, scratch
repair, tile seams, building geometry, sky smoothness, generated-detail risk.
**Do not commit private photos to the repository.**
