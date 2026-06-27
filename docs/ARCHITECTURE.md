# Architecture

```text
Android app  ──HTTPS + Google ID token──►  Modal FastAPI web layer
                                              │  verify token, validate upload,
                                              │  create job, store source, spawn worker
                                              ▼
                                           Modal GPU workers
                                              │  Standard: Real-ESRGAN + CodeFormer + LaMa
                                              │  Ultra:    SUPIR (+ support models)
                                              ▼
                                           Temporary storage
                                              Volume: uploads / masks / results / previews
                                              Dict:   job metadata + progress
                                              Auto-deletion
```

## Backend modules (`backend/app`)

| Module | Responsibility |
|---|---|
| `config.py` | Environment-driven settings (limits, approved account, retention) |
| `errors.py` | Stable `ErrorCode` enum + `ApiError`; HTTP status derived from code |
| `schemas.py` | API enums (mode/output/status/stage) and Pydantic response models |
| `auth.py` | Google ID-token verification + approved-account policy (injectable verifier) |
| `image_validation.py` | Decode, enforce size/pixel limits, EXIF orientation, GPS strip, mask alignment |
| `storage.py` | `FileStore` / `MetadataStore` protocols + local implementations + path layout |
| `jobs.py` | `JobRecord` + `JobService`: creation, idempotency, ownership, transitions, deletion |
| `pipelines/sizing.py` | Deterministic 2×/4×/4K/8K output dimension rules |
| `workers/processor.py` | `Processor` protocol + GPU-free placeholder (resize) implementation |
| `api.py` | `/v1` routes wired to `request.app.state` components |
| `main.py` | `create_app(...)` factory + module-level `app` |

## Decoupling from Modal

`backend/app` has no hard dependency on Modal. `create_app` accepts the
settings, token verifier, file store, metadata store, and processor, so:

- **Tests / local** use `InMemoryMetadataStore`, `LocalFileStore`, a fake
  verifier, and the placeholder processor — no GPU, no network.
- **Production** (`backend/modal_app.py`) injects Modal Volume / Dict-backed
  stores and a `SpawnProcessor` that dispatches to GPU worker classes.

## Async job flow

`POST /v1/jobs` validates and stores the upload, creates a job, and dispatches
processing (a background task locally; a GPU `.spawn()` on Modal) — then returns
the job id immediately. The client polls `GET /v1/jobs/{id}` and downloads the
result once `status == completed`. The original upload connection is never held
open through processing.
