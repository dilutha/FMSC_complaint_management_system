import 'package:flutter/foundation.dart';

/// Build-time configuration:
///   flutter run --dart-define=API_BASE_URL=https://fmsc.example.lk/api/v1/
///
/// Without API_BASE_URL, a local Django server (`manage.py runserver`) is used:
/// * Android emulator: http://10.0.2.2:8000 (the emulator's alias for the host machine)
/// * Web (Chrome), iOS simulator, desktop: http://127.0.0.1:8000
/// A physical phone needs the computer's LAN address, e.g.
///   --dart-define=API_BASE_URL=http://192.168.1.20:8000/api/v1/  (and `runserver 0.0.0.0:8000`)
abstract final class AppConfig {
  static const _override = String.fromEnvironment('API_BASE_URL');

  /// Per-request timeout. Override with --dart-define=API_TIMEOUT_SECONDS=30.
  /// Normal requests take about 0.3–1.3 s against Supabase, so 20 s only trips
  /// when the server is unreachable or genuinely stuck.
  static const requestTimeout = Duration(seconds: int.fromEnvironment('API_TIMEOUT_SECONDS', defaultValue: 20));

  static String get apiBaseUrl {
    if (_override.isNotEmpty) return _override;
    final androidEmulator = !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
    return androidEmulator ? 'http://10.0.2.2:8000/api/v1/' : 'http://127.0.0.1:8000/api/v1/';
  }

  /// Human-readable server address for error messages, e.g. "127.0.0.1:8000".
  static String get serverLabel {
    final uri = Uri.tryParse(apiBaseUrl);
    return uri == null || uri.host.isEmpty ? apiBaseUrl : '${uri.host}${uri.hasPort ? ':${uri.port}' : ''}';
  }

  /// 10.0.2.2 exists only inside the Android emulator; anywhere else requests
  /// to it hang until they time out.
  static bool get looksMisconfigured =>
      Uri.tryParse(apiBaseUrl)?.host == '10.0.2.2' && (kIsWeb || defaultTargetPlatform != TargetPlatform.android);
}
