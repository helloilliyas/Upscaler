# Deploy & verify the Modal backend

The Real-ESRGAN standard pipeline runs on a GPU and therefore can only be
verified by deploying to Modal — it cannot run in CI or on a CPU-only dev box.
The web layer, job lifecycle, and orchestration are covered by `pytest` (no GPU);
this guide covers the GPU half.

## 1. One-time setup

```bash
cd backend
pip install modal
modal token new                      # authenticate this machine

# Approved-account config the API verifies (Modal Secret named in modal_app.py):
modal secret create photo-restorer-auth \
  GOOGLE_WEB_CLIENT_ID="<your-web-oauth-client-id>" \
  ALLOWED_GOOGLE_EMAIL="<you@gmail.com>" \
  ALLOWED_GOOGLE_SUB=""              # fill in after first sign-in to pin the account
```

## 2. Deploy

```bash
cd backend
modal deploy modal_app.py
```

The **first** deploy builds the standard worker image: it installs the
Real-ESRGAN stack (torch 2.1.2 / torchvision 0.16.2 pinned so `basicsr` imports
cleanly) and runs `download_standard_weights()`, which fetches the two
checkpoints and **fails the build if a SHA-256 doesn't match** the pins in
`STANDARD_WEIGHTS`. Expect this build to take several minutes; later deploys are
cached.

`modal deploy` prints the web URL — set it as the Android app's `BASE_URL`.

## 3. Smoke-test the GPU pipeline

```bash
# Health (no auth):
curl -s https://<your-app>.modal.run/v1/health

# Submit a Natural 4x job (needs a real Google ID token for the approved account):
TOKEN="<google-id-token>"
curl -s -X POST https://<your-app>.modal.run/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $(uuidgen)" \
  -F "photo=@sample.jpg" -F "mode=natural" -F "output=4x"
# -> {"job_id":"job_…","status":"queued",...}

# Poll until completed, then download:
curl -s https://<your-app>.modal.run/v1/jobs/<job_id> -H "Authorization: Bearer $TOKEN"
curl -s https://<your-app>.modal.run/v1/jobs/<job_id>/result \
  -H "Authorization: Bearer $TOKEN" -o restored.jpg
```

What to check on the result:

- Dimensions match the requested output (e.g. a 1000×750 input at `4x` → 4000×3000;
  at `4k` it fits the 3840×2160 box preserving aspect).
- Real detail/denoise vs. the input (not just a resize).
- No visible tile seams on large outputs.
- `fidelity` is `high` for Natural, `moderate` for Restore.

## 4. Iterate

Logs and per-stage timings: `modal app logs ai-photo-restorer`. Tune `tile`
(memory vs. speed) in `StandardRestorer`, or switch the default checkpoint in
`backend/app/workers/standard_processor.py` (`realesr-general-x4v3` for faster
previews vs. `RealESRGAN_x4plus` for final output).

## Current pipeline scope

- ✅ Real-ESRGAN upscaling for **Natural** and the background of **Restore**.
- ✅ GFPGAN face restoration for **Restore**.
- ✅ LaMa inpainting for the **Restore** repair brush — when a mask is supplied
  the painted regions are filled in before the face/background restore pass.
- ⏳ Ultra (SUPIR) — the Ultra worker still runs the placeholder resize.
