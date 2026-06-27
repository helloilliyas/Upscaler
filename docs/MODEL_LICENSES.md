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
| Real-ESRGAN | Standard restoration / upscaling | BSD-3-Clause repo; verify weights + deps | _pending_ |
| CodeFormer | Face restoration | **Non-commercial** S-Lab terms | _pending_ |
| LaMa | Inpainting / scratch repair | Apache-2.0 repo; verify weights + deps | _pending_ |
| SUPIR | Ultra Detail generative restoration | **Explicit non-commercial restrictions** | _pending_ |
| GFPGAN | Optional face fallback | Review repo + bundled deps | _pending_ |
| FastAPI | Backend framework | Permissive (MIT) | n/a |
| Modal | Cloud infrastructure | Paid service terms / pricing apply | n/a |
| Android / Compose | Mobile app | Standard Android OSS terms | _pending_ |

## Weight verification

Model weights are **not** committed to this repository. They are downloaded at
image-build time (or from a dedicated Modal Volume) and checked against pinned
SHA-256 hashes by `scripts/verify_model_hashes.py` before use. Never download
weights from an unverified mirror.
