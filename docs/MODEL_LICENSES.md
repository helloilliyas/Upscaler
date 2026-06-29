# Model and software licences

> **This project assumes personal, non-commercial use.** Some model licences
> (notably CodeFormer and SUPIR) forbid commercial use. Re-verify every model,
> weight file, and dependency licence before any public distribution or
> monetization.

For each model actually deployed, record: repository URL, commit/release used,
weight source, weight SHA-256, a copy or link to the licence, personal/commercial
status, and the date reviewed.

## Initial matrix

| Component | Use | Licence consideration | Reviewed |
|---|---|---|---|
| Real-ESRGAN | Standard restoration / upscaling | BSD-3-Clause repo; weights personal-use OK | 2026-06-27 |
| CodeFormer | Face restoration | **Non-commercial** S-Lab terms | _pending_ |
| LaMa | Inpainting / scratch repair (Restore brush) | Apache-2.0 repo + big-lama weights; pinned SHA-256 | 2026-06-29 |
| SUPIR | Ultra Detail generative restoration | **Explicit non-commercial restrictions** | _pending_ |
| GFPGAN | Face restoration (Restore) | Apache-2.0 repo; weights verify | 2026-06-28 |
| FastAPI | Backend framework | Permissive (MIT) | n/a |
| Modal | Cloud infrastructure | Paid service terms / pricing apply | n/a |
| Android / Compose | Mobile app | Standard Android OSS terms | _pending_ |

## Weight verification

Model weights are **not** committed to this repository. They are downloaded at
Modal image-build time and checked against pinned SHA-256 hashes before use.
Never download weights from an unverified mirror.

Pinned hashes live in two kept-in-sync places:

* `scripts/models.json` — used by `scripts/download_models.py` /
  `scripts/verify_model_hashes.py` for local/manual workflows.
* `STANDARD_WEIGHTS` in `backend/modal_app.py` — baked into the standard worker
  image at build time via `download_standard_weights()`.

| Weight | SHA-256 (prefix) | Bytes |
|---|---|---|
| `realesr-general-x4v3.pth` | `8dc7edb9…96292` | 4,885,111 |
| `RealESRGAN_x4plus.pth` | `4fa0d389…682f1` | 67,040,989 |
