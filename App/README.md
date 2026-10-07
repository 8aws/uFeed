# uFeed (app nativa)

Cliente Flutter de la API de uFeed. Plan y etapas: `../docs/NATIVE_APP.md`.

- Flutter 3.38.5 (mismo que AuraBox). CocoaPods en lugar de Swift Package
  Manager (`enable-swift-package-manager: false` en `pubspec.yaml`).
- Servidor por defecto: `https://ufeed.uverse.es`. Para el backend local:
  `--dart-define=UFEED_SERVER=http://localhost:8000`.
- Textos en `lib/l10n/app_es.arb` (plantilla) y `app_en.arb`.
- Icono: `uvx --with pillow python scripts/make_icons.py` (desde la raíz) y
  luego `dart run flutter_launcher_icons`.

## Simulador de iOS

Con Xcode 27, `flutter build ios --simulator` falla al empaquetar
("does not contain architectures arm64 x86_64"). Se compila solo arm64:

```bash
flutter build ios --simulator --debug --config-only
xcodebuild -workspace ios/Runner.xcworkspace -scheme Runner -configuration Debug -sdk iphonesimulator -derivedDataPath build/dd ARCHS=arm64 ONLY_ACTIVE_ARCH=YES build
```

Si `pod install` falla con un error de codificación: `export LANG=en_US.UTF-8`.

En compilaciones de depuración, `--dart-define=UFEED_DEV_EMAIL=…` y
`UFEED_DEV_PASSWORD=…` rellenan el inicio de sesión (solo para la cuenta de
pruebas local).

## Comprobaciones (igual que CI)

```bash
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```
