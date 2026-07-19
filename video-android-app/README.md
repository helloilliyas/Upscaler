# Video Upscaler (Android app)

A standalone Android app for the `video-backend/` service — a **separate APK**
from the photo app, with its own package id (`com.example.videoupscaler`) and
its own icon (violet gradient, play glyph + upscale arrow, themed-icon ready).

Deliberately lean: Kotlin + Jetpack Compose, a single Activity, one ViewModel,
and one WorkManager job. No Hilt, Room, or navigation library.

## Flow

1. **Sign in with Google** (Credential Manager; ID token for the same Web
   client id the backend verifies — same single approved account).
2. **Pick a video** with the system Photo Picker (video-only).
3. **Choose output** — 2×, 4×, or 4K (server caps everything inside a 4K box).
4. **Upscale** — a foreground WorkManager job streams the upload straight from
   the content Uri (never fully in memory), polls with live frame progress,
   then streams the finished MP4 into **Movies/VideoUpscaler** in the Gallery
   and deletes the server-side copy.
5. **Play, share, or start the next clip** — results play in-app (Media3).

The job survives backgrounding and network blips (same idempotency key on
retry re-attaches to the same server job instead of paying for a new one).

## Build

Built by CI (`.github/workflows/video-android-ci.yml`), which provides the
Android SDK and uploads the debug APK as the `video-upscaler-debug` artifact.
Configuration (non-secret) comes from Gradle properties or environment:

| Property / env | Purpose |
|---|---|
| `VIDEO_BASE_URL` | The Modal video-backend endpoint (trailing slash) |
| `GOOGLE_WEB_CLIENT_ID` | Web OAuth client id (ID-token audience) |

The committed debug keystore is shared with the photo app, so the SHA-1 is
already known — to enable sign-in, add an **Android OAuth client** in Google
Cloud Console for package `com.example.videoupscaler.debug` with that SHA-1.

- minSdk 29 (Android 10) · targetSdk 34 · Compose BOM 2024.09
