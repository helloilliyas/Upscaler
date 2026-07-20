# AI Video Upscaler (backend)

A standalone, personal-use video upscaling service: clips in, up-to-4K MP4s
out. Mirrors the photo backend's architecture (FastAPI web layer on Modal +
scale-to-zero GPU worker + Volume/Dict storage) but is a fresh codebase that
shares no files with it.

```text
client ──HTTPS + Google ID token──► Modal FastAPI web layer (CPU + ffprobe)
                                       │ validate (container/codec/duration/
                                       │ resolution/fps caps), create job,
                                       │ store source, spawn GPU worker
                                       ▼
                                    Modal L4 worker (scale-to-zero)
                                       ffmpeg decode ─pipe─► Real-ESRGAN
                                       (compact x4, fp16) ─pipe─► ffmpeg
                                       NVENC encode + audio stream-copy
                                       ▼
                                    Volume (uploads/results/posters)
                                    Dict (job records + frame progress)
```

## Design in one paragraph

Frames stream through two ffmpeg subprocess pipes and never touch disk. The
web layer probes uploads with ffprobe and enforces every cost guardrail
(≤ 90 s, ≤ 1080p, ≤ 300 MB, ≤ 60 fps). The GPU worker decodes to raw RGB at a
forced constant frame rate, pushes each frame through `realesr-general-x4v3`
(the compact SRVGGNet — fast enough for per-frame video work), and pipes the
output into hardware NVENC HEVC (x264 fallback), muxing the original audio
back untouched. Output dimensions are always even and capped inside a 4K box.
Estimated cost on a Modal L4: **~$0.10–0.20 per minute of footage**, $0 in
practice inside Modal's monthly free credit.

## Layout

```text
app/
  config.py            env-driven settings + cost guardrails
  errors.py            stable error codes -> HTTP statuses
  auth.py              Google ID-token verification, single approved account
  schemas.py           API enums + response models
  storage.py           FileStore/MetadataStore protocols + local impls
  jobs.py              JobRecord + JobService (lifecycle, idempotency, ownership)
  video_io.py          ffprobe/ffmpeg subprocess helpers (probe, progress)
  validation.py        upload validation via ffprobe
  sizing.py            2x/4x/4K rules: 4K cap + even dimensions
  worker.py            run_video_job orchestration + CPU placeholder enhancer
  realesrgan_video.py  GPU frame-streaming pipeline (lazy torch imports)
  api.py               /v1 routes
  main.py              create_app factory
tests/                 pytest suite (needs ffmpeg binaries; no GPU, no Modal)
modal_app.py           Modal entrypoint: web app + L4 worker + selftest_video
```

## Run and test locally

```bash
cd video-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
sudo apt-get install -y ffmpeg   # ffprobe/ffmpeg binaries

# quality gates (same as CI: .github/workflows/video-backend-test.yml)
ruff check .
mypy app
python -m pytest -q

# run the API locally (placeholder Lanczos processor, no GPU)
export GOOGLE_WEB_CLIENT_ID=...           # Web OAuth client id
export ALLOWED_GOOGLE_EMAIL=you@gmail.com # the single approved account
uvicorn app.main:app --reload
```

## Deploy

```bash
modal deploy video-backend/modal_app.py
# then prove the GPU pipeline end to end before pointing any client at it:
modal run video-backend/modal_app.py::selftest_video
```

Auth reuses the existing `photo-restorer-auth` Modal secret (same approved
Google account). The Volume (`video-upscaler-files`) and Dict
(`video-upscaler-jobs`) are created on first deploy.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `GOOGLE_WEB_CLIENT_ID` | Web OAuth client id; the ID-token audience | — |
| `ALLOWED_GOOGLE_EMAIL` | The single approved personal account | — |
| `ALLOWED_GOOGLE_SUB` | Stable subject id (pin after first sign-in) | — |
| `MAX_UPLOAD_BYTES` | Upload size limit | 300 MB |
| `MAX_DURATION_SECONDS` | Clip length limit | 90 |
| `MAX_INPUT_PIXELS` | Per-frame pixel limit | ~1080p |
| `MAX_FPS` | Frame-rate limit (slow-mo is a cost trap) | 61 |
| `DATA_DIR` | Local file-store root (Modal mounts a Volume) | `./video-backend/.data` |
| `RETENTION_HOURS` | Temporary-file retention window | 24 |

## Licences

Application source: MIT (repo licence). `realesr-general-x4v3` weights are from
Real-ESRGAN (BSD-3-Clause). Re-check model licences before any distribution.
