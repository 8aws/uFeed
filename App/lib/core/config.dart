/// Where the uFeed server lives. Override for a local backend with
/// `flutter run --dart-define=UFEED_SERVER=http://localhost:8080`.
const String serverUrl = String.fromEnvironment(
  'UFEED_SERVER',
  defaultValue: 'https://ufeed.uverse.es',
);

const String apiBase = '$serverUrl/api';
