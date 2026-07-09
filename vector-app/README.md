# Vectorizer — personal image-to-vector converter

Flutter app + Modal/FastAPI backend. Converts photos into SVG / PDF / PNG
vectors with four styles (photo, poster, logo, sketch), saves results on the
phone, keeps local history, before/after preview, share to anywhere.

Runs entirely within Modal's free monthly credits for single-user load.
Scales to zero when idle — **$0/month**.

```
app/       Flutter app (thin client)
backend/   Modal + FastAPI + VTracer (all processing)
```

## 1. Deploy the backend (~5 minutes)

```sh
pip install modal
modal setup                       # opens browser, free account

# one long random string; this is the app's password
modal secret create vector-converter-secret API_KEY=$(openssl rand -hex 24)

modal deploy backend/modal_app.py
```

The deploy prints your endpoint URL, like
`https://yourname--vector-converter-api.modal.run`.

Smoke test:

```sh
curl https://yourname--vector-converter-api.modal.run/health
curl -X POST -H "x-api-key: YOUR_KEY" \
     -F file=@test.jpg -F preset=poster -F detail=60 -F format=svg \
     https://yourname--vector-converter-api.modal.run/vectorize | head -c 300
```

## 2. Build the app

Requires the [Flutter SDK](https://docs.flutter.dev/get-started/install) and
Android Studio (for the Android toolchain).

```sh
cd app
# put your endpoint URL and API key into:
#   lib/config.dart
flutter create . --platforms=android,ios   # generates platform scaffolding
flutter pub get
flutter build apk --release
```

Install `build/app/outputs/flutter-apk/app-release.apk` on your phone
(copy it over or `flutter install` with the phone plugged in).

For iOS, open `ios/` in Xcode and run on your device with your personal team
signing (free Apple ID works, re-sign every 7 days, or pay the $99/yr
developer account for a permanent install).

### Android notes

`flutter create` generates a default manifest; the app needs no special
permissions (image_picker and share_plus handle theirs). If the camera
button does nothing on Android 11+, add to
`android/app/src/main/AndroidManifest.xml` inside `<manifest>`:

```xml
<queries>
  <intent><action android:name="android.media.action.IMAGE_CAPTURE"/></intent>
</queries>
```

## 3. Conversion settings

| Setting | What it does |
|---|---|
| **Style** | photo (full color, smooth), poster (flat 8-color art), logo (6 colors, crisp edges), sketch (black & white line art) |
| **Detail** 0–100 | Low = fewer, cleaner paths. High = every speckle traced. 60 is a good default. |
| **Limit colors** | Override the palette size (2–32) for color styles. |
| **Output** | SVG (native vectors), PDF (print), PNG (2× raster of the vector) |

Outputs are saved in the app's documents folder and via **Share** can go to
Drive, WhatsApp, email, or the Files app.

## 4. Cost & privacy

- Backend scales to zero; a conversion costs a fraction of a cent of Modal's
  $30/month free credits. Uploads are capped at 10 MB and processed in a
  temp dir that's destroyed with the container — nothing is stored server-side.
- The API is protected by your `x-api-key`; rotate it any time with
  `modal secret create vector-converter-secret API_KEY=... --force` and a
  rebuild of the app (or move the key to a settings screen later).

## 5. Roadmap (next phases)

- **AI mode** (Modal GPU): background removal (rembg/BiRefNet), FastSAM
  segmentation, sticker mode with outline — add as a `spawn()`-based
  `/vectorize-pro` + `/job/{id}` pair.
- Batch conversion, DXF export (`ezdxf`) for cutters/CNC, palette editor.
