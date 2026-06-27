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

This repository currently contains the **backend foundation**:

- ✅ FastAPI app with the full `/v1` API contract (health, me, jobs CRUD, result/preview)
- ✅ Google ID-token verification + approved-account policy
- ✅ Upload validation (format, size, pixel limits, EXIF/GPS handling, mask alignment)
- ✅ Storage abstractions (Modal Volume / Dict) with local in-memory + filesystem implementations
- ✅ Async job lifecycle, idempotency, ownership enforcement, retention-ready deletion
- ✅ A GPU-free **placeholder processor** (deterministic resize) so the whole flow runs and is tested without a GPU
- ✅ Modal deployment glue (`backend/modal_app.py`) with standard + ultra GPU workers
- ✅ CI: ruff + mypy + pytest (`.github/workflows/backend-test.yml`) and Modal deploy

Not yet implemented (later phases): the real model pipelines, the Android app,
and the signed-release workflow.

## Repository layout

```text
backend/            FastAPI + Modal backend (this foundation)
  app/              framework-agnostic application code
  tests/            pytest unit + API tests (no GPU required)
  modal_app.py      Modal deployment entrypoint (Volume/Dict + GPU workers)
docs/               architecture, API, privacy, licences, test plan
.github/workflows/  backend tests + Modal deploy
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
