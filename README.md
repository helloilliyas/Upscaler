# AI Photo Restorer

A lean, personal-use system that restores old and low-resolution photographs and
produces high-resolution (up to 8K-sized) outputs. An Android app handles the
user experience; a FastAPI backend on [Modal](https://modal.com) runs the GPU AI
pipelines (Real-ESRGAN, CodeFormer, LaMa, and SUPIR for Ultra Detail).

See the full design in [`docs/`](docs/) and the original blueprint sections for
product scope, architecture, API contract, and implementation phases.

> Personal, non-commercial use. Several AI model licences (notably CodeFormer
> and SUPIR) are non-commercial. Re-check every model and weight licence before
> any distribution or monetization — see [`docs/MODEL_LICENSES.md`](docs/MODEL_LICENSES.md).

## Status

**Backend foundation** (`backend/`):

- ✅ FastAPI app with the full `/v1` API contract (health, me, jobs CRUD, result/preview)
- ✅ Google ID-token verification + approved-account policy
- ✅ Upload validation (format, size, pixel limits, EXIF/GPS handling, mask alignment)
- ✅ Storage abstractions (Modal Volume / Dict) with local in-memory + filesystem implementations
- ✅ Async job lifecycle, idempotency, ownership enforcement, retention-ready deletion
- ✅ **Real-ESRGAN** standard pipeline (Natural + Restore upscaling) with tiling, behind a shared `run_image_job` orchestration; weights pinned by SHA-256 and baked into the Modal image at build (see [`docs/DEPLOY.md`](docs/DEPLOY.md))
- ✅ A GPU-free **placeholder processor** (deterministic resize) still used by the Ultra worker and for CPU tests
- ✅ Modal deployment glue (`backend/modal_app.py`) with standard (Real-ESRGAN) + ultra (placeholder) GPU workers
- ✅ CI: ruff + mypy + pytest (`.github/workflows/backend-test.yml`) and Modal deploy

**Android app scaffold** (`android-app/`):

- ✅ Kotlin + Jetpack Compose + Hilt + MVVM, wired to the backend API
- ✅ Sign in with Google via Credential Manager (ID token only; no Modal secrets in the APK)
- ✅ Photo Picker selection (up to 50), batch review with mode/output selection
- ✅ Retrofit/OkHttp client matching the `/v1` contract; streaming uploads/downloads
- ✅ Persistent WorkManager chain (Submit → Poll → Download → Cleanup) with idempotency keys
- ✅ Room history, DataStore settings, MediaStore Gallery save, before/after result view
- ✅ CI builds the debug APK (`.github/workflows/android-ci.yml`); JVM unit tests for model mapping

Not yet implemented (later phases): CodeFormer (faces) and LaMa (repair mask)
stages, the SUPIR Ultra worker, the in-editor crop/rotate and repair-brush mask,
and the signed-release workflow.

> The Android module builds via GitHub Actions (which provides the Android SDK).
> Configure it with a `BASE_URL` (your Modal endpoint) and `GOOGLE_WEB_CLIENT_ID`
> via Gradle properties or environment variables at build time.

## Repository layout

```text
backend/            FastAPI + Modal backend
  app/              framework-agnostic application code
  tests/            pytest unit + API tests (no GPU required)
  modal_app.py      Modal deployment entrypoint (Volume/Dict + GPU workers)
android-app/        Kotlin + Compose app (Gradle, builds in CI)
  app/src/main/     auth, network, database, repository, worker, ui, di
  app/src/test/     JVM unit tests
docs/               architecture, API, privacy, licences, test plan
scripts/            model download + hash verification
.github/workflows/  android-ci, backend-test, modal-deploy
.devcontainer/      Codespaces dev environment
```

## Backend: run and test locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# quality gates (same as CI)
ruff check .
mypy app
python -m pytest -q

# run the API locally (placeholder resize processor)
export GOOGLE_WEB_CLIENT_ID=...           # Web OAuth client id
export ALLOWED_GOOGLE_EMAIL=you@gmail.com # the single approved account
uvicorn app.main:app --reload
```

Then `GET /v1/health` requires no auth; all other endpoints require
`Authorization: Bearer <google-id-token>`.

## Configuration

Backend configuration comes from environment variables (Modal Secrets in
production) — never commit secrets. Key values:

| Variable | Purpose |
|---|---|
| `GOOGLE_WEB_CLIENT_ID` | Web OAuth client id; the ID-token audience |
| `ALLOWED_GOOGLE_EMAIL` | The single approved personal account |
| `ALLOWED_GOOGLE_SUB` | Stable subject id of the approved account (pin after first sign-in) |
| `MAX_UPLOAD_BYTES` | Compressed upload limit (default 40 MB) |
| `MAX_INPUT_PIXELS` | Decoded pixel limit (default 50 MP) |
| `DATA_DIR` | Local file-store root (Modal mounts a Volume instead) |
| `RETENTION_HOURS` | Temporary-file retention window |

## License

Application source: MIT (see [`LICENSE`](LICENSE)). AI model weights and their
repositories carry their own, sometimes non-commercial, licences.
