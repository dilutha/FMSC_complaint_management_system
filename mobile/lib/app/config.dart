/// Build-time configuration:
///   flutter run --dart-define=API_BASE_URL=https://fmsc.example.lk/api/v1/
/// Default targets a local Django server from the Android emulator.
abstract final class AppConfig {
  static const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000/api/v1/');
}
