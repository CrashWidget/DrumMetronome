Android Remote (Flutter)

This folder contains the Flutter client for LAN control.

Setup (if platform files are missing)
1) Install Flutter SDK.
2) From the repo root:
   - cd android
   - flutter create --platforms android .
   - flutter pub get
   - flutter run

Build APK
- flutter build apk

Notes
- The desktop app listens on UDP 45833 for discovery and HTTP 45834 for control.
- If you change the discovery port in `drum_metronome.ini`, update `kDiscoveryPort` in `android/lib/main.dart`.
- If `flutter create` overwrote `lib/main.dart` or `pubspec.yaml`, restore them from this repo.
