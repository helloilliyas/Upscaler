# API contract (`/v1`)

All endpoints except `/v1/health` require `Authorization: Bearer <GOOGLE_ID_TOKEN>`.
Errors are returned as `{"error": {"code": "...", "message": "..."}}` with the
HTTP status derived from the code.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| `GET` | `/v1/health` | No auth. `{ "status": "ok", "version": "..." }` |
| `GET` | `/v1/me` | Returns `{ "email", "authorized": true }` for the approved account |
| `POST` | `/v1/jobs` | Multipart submit (see below). Returns the job id; `201` |
| `GET` | `/v1/jobs` | `?limit=20` recent jobs for the owner |
| `GET` | `/v1/jobs/{id}` | Job status / stage / progress / result metadata |
| `GET` | `/v1/jobs/{id}/result` | Full-resolution result bytes (JPEG), attachment |
| `GET` | `/v1/jobs/{id}/preview` | Screen-sized preview (JPEG) |
| `DELETE` | `/v1/jobs/{id}` | Cancel/delete the job and its blobs; `204` |

## `POST /v1/jobs` form fields

| Field | Type | Required |
|---|---|---|
| `photo` | file (JPEG/PNG/WebP) | yes |
| `repair_mask` | PNG file, same dimensions as the photo | no |
| `mode` | `natural` \| `restore` \| `ultra` | yes |
| `output` | `2x` \| `4x` \| `4k` \| `8k` | yes |
| `preserve_metadata` | boolean | no |
| `crop_json` | JSON string | no |
| `rotation` | integer degrees | no |

Header `Idempotency-Key: <UUID>` is honoured: repeating a key for the same owner
returns the existing job instead of creating a new one.

## Job status response

```json
{
  "job_id": "job_...",
  "status": "processing",
  "stage": "restoring_faces",
  "progress": 58,
  "message": "Restoring faces",
  "result_available": false,
  "width": null,
  "height": null,
  "fidelity": null,
  "generated_detail": null
}
```

`status` ∈ `queued | processing | completed | failed | cancelled | expired`.
On completion, `result_available` is `true` with `width`, `height`, and a
`fidelity` label (`high | moderate | generative`).

## Error codes

`AUTH_REQUIRED` (401), `ACCOUNT_NOT_ALLOWED` (403), `UNSUPPORTED_FORMAT` (415),
`INVALID_IMAGE` (422), `FILE_TOO_LARGE` (413), `PIXEL_LIMIT_EXCEEDED` (422),
`MASK_SIZE_MISMATCH` (422), `GPU_OUT_OF_MEMORY` (500), `MODEL_ERROR` (500),
`RESULT_EXPIRED` (410), `BUDGET_LIMIT` (429), `INTERNAL_ERROR` (500),
`VALIDATION_ERROR` (400), `NOT_FOUND` (404).
