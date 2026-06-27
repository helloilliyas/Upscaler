# Android sign-in & config setup

The debug APK installs and runs, but **Google sign-in needs real config**.
Once these steps are done, the next CI build produces a fully working APK.

## Values you'll need to register

| Field | Value |
|---|---|
| Debug package name | `com.example.photorestorer.debug` |
| Debug signing SHA-1 | `E5:AF:04:9E:FC:E8:AA:F9:21:FD:3E:C2:F4:C4:5A:5D:B5:8B:1C:66` |

The SHA-1 comes from the committed `android-app/app/debug.keystore`, so every CI
build shares it. (Re-derive any time: `keytool -list -v -keystore
android-app/app/debug.keystore -storepass android -alias androiddebugkey`.)

## 1. Google Cloud (console.cloud.google.com → APIs & Services)

1. Create or select a project.
2. **OAuth consent screen** → External → fill app name + your email → add your
   Gmail under **Test users**.
3. **Credentials → Create credentials → OAuth client ID**, twice:
   - **Android**: package `com.example.photorestorer.debug`, SHA-1 = the value above.
   - **Web application**: any name → copy its **Client ID** (`…apps.googleusercontent.com`).

> The app sends the **Web** client ID as the token audience; the **Android**
> client just has to exist with the matching package + SHA-1 so Google issues the
> credential. `GOOGLE_WEB_CLIENT_ID` = the **Web** client ID, not the Android one.

## 2. Deploy the backend (for `BASE_URL`)

Follow [`DEPLOY.md`](DEPLOY.md): `modal deploy backend/modal_app.py` prints a URL
like `https://<app>.modal.run/`. Also set the Modal `photo-restorer-auth` secret's
`ALLOWED_GOOGLE_EMAIL` to your Gmail (otherwise the backend returns 403
"account not approved" after sign-in).

## 3. Set repository Variables

GitHub → repo → **Settings → Secrets and variables → Actions → Variables tab →
New repository variable**:

| Variable | Value |
|---|---|
| `GOOGLE_WEB_CLIENT_ID` | the Web client ID from step 1.3 |
| `BASE_URL` | the Modal URL from step 2 (keep the trailing `/`) |

These are non-secret (a public client id and a public URL); Variables, not Secrets.

## 4. Rebuild and install

Trigger Android CI (push any change, or **Actions → Android CI → Run workflow**),
download the new `photo-restorer-debug` artifact, install on the S22. "Continue
with Google" now authenticates with your approved account.

## Why sign-in needs all three

The app gets a Google ID token via Credential Manager (needs the Android client +
SHA-1), then immediately calls `GET /v1/me` on `BASE_URL` to confirm the account
is approved. So a missing `BASE_URL` or an unconfigured backend makes sign-in fail
even when the OAuth setup is correct.
