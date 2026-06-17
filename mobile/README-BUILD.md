# UPSC AI — Android APK build (Capacitor)

This wraps the live UPSC AI site in a thin Android app. Because Capacitor's
native HTTP is enabled, the app's network calls (including YouTube caption
fetches) go out on the PHONE's IP, not your server's datacenter IP — which is
what bypasses the YouTube block. No new APK is needed when you update the site;
the app loads the live Vercel URL.

Live URL loaded by the app:
  https://upsc-agentic-ai.vercel.app/app-frontend.html?auth=1

## One-time setup on your PC
1. Install Node.js LTS:        https​://nodejs.org
2. Install Android Studio:     https​://developer.android.com/studio
   - During first run, let it install the Android SDK + Platform Tools.
3. Install Java JDK 17 (Android Studio usually bundles it).

## Build steps (run inside the `mobile/` folder)
```bash
cd mobile
npm install
npx cap add android
npx cap sync
npx cap open android      # opens Android Studio
```
In Android Studio:
  Build  >  Build Bundle(s) / APK(s)  >  Build APK(s)
OR from the terminal:
```bash
cd android
./gradlew assembleDebug      # Windows: gradlew.bat assembleDebug
```
The APK lands at:
  android/app/build/outputs/apk/debug/app-debug.apk

## Install on a phone (no Play Store)
1. Copy app-debug.apk to the phone.
2. Open it; allow "Install from unknown sources" when prompted.
3. Open the app, paste a YouTube link, tap Generate notes.
   - Inside the app, captions are fetched on the device IP (free, no block).
   - If a video has no captions, it auto-falls back to the server chain.

## Notes
- iOS is NOT covered here (needs a Mac + Apple developer account).
- For a shareable signed release build, generate a keystore and run
  `./gradlew assembleRelease` with signing configured.
- If the app shows a blank screen, confirm the live URL opens in a normal
  mobile browser first, and that the site is HTTPS.
