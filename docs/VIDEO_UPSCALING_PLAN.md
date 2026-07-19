# Video Upscaling — Design & Implementation Plan

Personal-use video upscaling, built the same way the photo pipeline was built:
lean, contract-first, testable without a GPU, and pay-per-second on Modal.

## 1. Understanding of the current system

The photo path today:

```text
Android app ──HTTPS + Google ID token──► Modal FastAPI web layer (CPU, cheap)
                                            │ validate upload, create job,
                                            │ store source on Volume, spawn worker
                                            ▼
                                         Modal GPU workers (scale-to-zero)
                                            Standard (L4):  Real-ESRGAN / GFPGAN / LaMa
                                            Ultra (L40S):   SD x4 latent upscaler
                                            ▼
                                         Volume (blobs) + Dict (job records)
                                            client polls status, downloads result,
                                            retention-based auto-delete
```

Everything that made this cheap and reliable carries over unchanged:

- **`JobService` + async job lifecycle** — media-agnostic already (status,
  stages, progress, idempotency, ownership, retention). Reused as-is.
- **Storage layout** (`uploads/…/source`, `results/…`, `previews/…`) — reused;
  only file extensions change.
- **Scale-to-zero GPU workers** — we pay only for seconds of GPU time.
- **`run_image_job` orchestration** is the only image-specific piece; video
  gets a sibling `run_video_job`.

## 2. Product scope (v1)

| Decision | Choice | Why |
|---|---|---|
| Input | MP4/MOV/WebM/MKV, ≤ 90 s, ≤ 1080p, ≤ 300 MB | Bounds cost + worker timeout; covers phone clips and old family footage |
| Output | `2x` / `4x`, capped at a 4K box | 8K video is enormous to encode/store/play; 4K is the practical ceiling |
| Modes | `natural` only in v1 | Face restore and generative detail on video flicker; they come later, done right |
| Container out | MP4, H.265 (NVENC), audio **stream-copied** | Universal playback, tiny files, original audio untouched |
| Users | Same single approved Google account | No change |

Non-goals for v1: frame interpolation, colorization, stabilization, >90 s
clips (phase 5 adds chunked long-clip support), in-app trimming.

## 3. Model strategy — lean but world-leading

**v1 Standard: `realesr-general-x4v3` frame-by-frame.**

- It is the *compact* SRVGGNet architecture — 5–10× faster than the RRDB
  `RealESRGAN_x4plus` used for photos, which is exactly what per-frame work
  needs. Already downloaded, hash-pinned, and baked into the standard image.
- Its adjustable **denoise strength** (`-dn`) is the single most effective
  anti-flicker lever for frame-wise SR: most shimmer is amplified sensor
  noise/compression grain, and processing every frame with identical,
  deterministic weights keeps the output stable.
- This is the same stack ffmpeg/Real-ESRGAN communities converge on for
  practical video work; "video-specific" temporal models (BasicVSR++,
  RealBasicVSR) are older, heavier, and fragile on real-world compression.

**Phase-4 Ultra: SeedVR2 (one-step diffusion video restoration)** — the current
open-weights state of the art for real-world video restoration, with true
temporal consistency. Heavy (L40S/A100-class), so it becomes the video
equivalent of the photo Ultra tier: opt-in, per-job, still pennies at personal
volume. Licence must be re-checked before shipping (personal use is fine).

## 4. Pipeline architecture (the core design)

**Never write frames to disk.** A 60 s 4K PNG frame dump is ~30 GB and kills
both speed and Volume cost. Instead, two ffmpeg subprocesses stream raw frames
through the model:

```text
source.mp4 ─► ffmpeg #1 (decode, CFR, rgb24 rawvideo) ─► stdout pipe
                                                            │  W×H×3 bytes/frame
                                                            ▼
                                   Python: batch → Real-ESRGAN (fp16, tiled) → 4K frame
                                                            │
                                                            ▼
              ffmpeg #2 (stdin rawvideo ─► hevc_nvenc) + `-i source.mp4 -map a -c:a copy`
                                                            ▼
                                                       result.mp4  (audio muxed back)
```

Key points:

- **ffprobe validation** in the web layer (duration, resolution, codec,
  stream sanity) mirrors `image_validation.py` → new `video_validation.py`.
  Container metadata (incl. GPS) is dropped on re-mux, same privacy stance.
- **VFR → CFR**: decode with `-vsync cfr` at the probed average fps so frame
  counts are deterministic and audio stays in sync.
- **NVENC encoding**: the L4's hardware encoder is idle while CUDA does SR —
  encoding is effectively free and never bottlenecks the pipeline.
- **Progress** = frames_done / frames_total, written to the Dict every ~2 s
  (not every frame — Dict writes are RPCs).
- **Preview** = poster JPEG (for history list) + first ~5 s at 720p as a
  preview MP4, generated on the worker after the main encode.
- **Orchestration**: `run_video_job` sibling of `run_image_job`; a GPU-free
  `LocalPlaceholderVideoProcessor` (pure-ffmpeg lanczos scale) makes the whole
  flow testable in CI with a tiny synthetic clip, exactly like the photo
  placeholder did.

## 5. API & schema changes (additive, no breaking changes)

- `POST /v1/jobs` accepts video uploads; job gains `media_type: photo|video`
  (default `photo` — existing clients unaffected).
- New config: `MAX_VIDEO_UPLOAD_BYTES` (300 MB), `MAX_VIDEO_SECONDS` (90),
  `MAX_VIDEO_INPUT_PIXELS` (1080p box). Photo limits untouched.
- New stages: `DECODING`; existing `ENHANCING`/`ENCODING` reused. Status
  response gains `frames_total`/`frames_done` (nullable, photo jobs omit).
- Result/preview endpoints serve `video/mp4` by content-type; storage paths
  unchanged (`result.mp4`, `preview.mp4`, `poster.jpg`).
- Upload streaming: the web layer already streams to the Volume; raise the
  body limit for `media_type=video` only.

## 6. Android app

- Photo Picker already supports video (`VisualMediaType.VideoOnly`) — small
  change to selection + review UI (show duration/size, mode picker hides
  photo-only options).
- Same WorkManager chain (Submit → Poll → Download → Cleanup); download
  streaming already exists.
- Result screen: ExoPlayer (Media3) before/after playback instead of the
  image comparison view; save to `MediaStore.Video`.

## 7. Cost model & guardrails

Modal L4 ≈ $0.80/hr, billed per second, scale-to-zero.

| Clip | Frames | Est. GPU time (compact model, fp16, NVENC) | Est. cost |
|---|---|---|---|
| 30 s @ 1080p30 → 4K | 900 | ~2–4 min | **~$0.03–0.06** |
| 90 s @ 1080p30 → 4K | 2700 | ~6–12 min | **~$0.08–0.16** |

Rule of thumb: **~$0.10–0.20 per minute of footage** — dozens of clips a month
land inside Modal's $30/month free credit, so realistic personal cost is $0.

Guardrails (all enforced server-side): duration/size/resolution caps, worker
`timeout` sized to the cap (30 min), scale-to-zero (`min_containers=0`),
retention deletion already covers the larger video blobs, and the status
response can surface a per-job cost estimate.

## 8. Implementation phases

1. **Foundation (CPU-only, fully tested)** — `media_type` in schema/records,
   `video_validation.py` (ffprobe), config limits, storage extensions,
   `run_video_job` + placeholder ffmpeg processor, API content-types, pytest
   coverage with a generated 2 s synthetic clip. CI stays GPU-free.
2. **GPU Standard video worker** — streaming pipe pipeline in
   `pipelines/video_sr.py`, batched Real-ESRGAN compact model, NVENC encode,
   audio copy, progress reporting; `selftest_video` Modal function (like
   `selftest_lama`) to validate on-GPU before wiring the app.
3. **Android video support** — picker/review/result-player/MediaStore, using
   the existing job plumbing.
4. **Quality tier** — evaluate SeedVR2 as the video Ultra worker; optional
   per-scene GFPGAN face restore with temporal blending if flicker-free.
5. **Long clips** — segment-chunked processing with per-segment resume, then
   concat mux; removes the 90 s cap without risking timeout-lost work.

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Temporal flicker from frame-wise SR | Compact model + denoise strength; deterministic weights; Ultra tier (temporal model) for hard cases |
| Worker timeout on long clips | Hard 90 s cap in v1; chunked resume in phase 5 |
| A/V desync on VFR phone video | Force CFR at probed fps on decode; audio stream-copied from the untouched source |
| Big uploads through the web layer | 300 MB cap, streamed to Volume; chunked upload only if real-world use demands it |
| NVENC unavailable on some GPU pool | Fallback to `libx264 -preset fast` (CPU encode on the same container) |
| Model licences | Real-ESRGAN is BSD-3 ✓; SeedVR2 licence re-checked at phase 4 (see `MODEL_LICENSES.md`) |

## 10. Open questions

1. Cap v1 at `4x`-within-4K only, or also allow plain `2x` for already-HD
   clips? (Plan assumes both, since sizing rules already exist.)
2. Is 90 s the right initial cap for your actual clips, or should phase 5
   (chunking) move earlier?
3. Preview clip (5 s @ 720p) vs poster-frame only — preview clip costs a few
   extra seconds of encode per job but makes the app feel much better.
