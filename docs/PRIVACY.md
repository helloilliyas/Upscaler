# Privacy

This is a single-user, personal application. Photos are processed only for the
authenticated owner and are not used for training or shared publicly.

## Data flow

```text
Photo on phone ──HTTPS──► Modal temporary upload ──GPU──► Modal temporary result
        ──HTTPS──► Android Gallery ──► cloud copy deleted
```

## Defaults

- Authentication required for every job and result download.
- No public links; results are owner-scoped by stable Google `sub`.
- GPS / location metadata is removed by default; results are re-encoded without EXIF.
- Cloud files are deleted after download or within the retention window (default 24h);
  the user can delete a job immediately.
- No third-party analytics containing image paths; no face database; no biometric templates.

## Logging policy

**Logged:** job id, owner hash / stable id, mode, output category, input/output
dimensions, stage timings, GPU type, success/failure code, model version.

**Never logged:** raw Google ID tokens, photo or mask bytes, full email in
ordinary debug logs, EXIF GPS, or model-access secrets.

## Secrets

The approved account, OAuth client id, and any model-access tokens live in Modal
Secrets — never in source, the APK, or logs. The Android app contains no Modal
credentials; a Google ID token alone does not authorize processing for an
unapproved account.
