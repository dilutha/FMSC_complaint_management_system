import 'package:flutter/foundation.dart';

/// SHARED CONTRACT with Member B (authentication).
///
/// The case screens only need a token to attach to requests and a hook for
/// expired sessions. Member B provides the real implementation (secure token
/// storage, refresh, SSO, logout UI) by implementing this interface and
/// passing it to [FmscCasesApp] / [CaseModule].
abstract class AuthSession extends ChangeNotifier {
  /// Current access token, or null when signed out.
  String? get token;

  /// Authorization header scheme: 'Token' for DRF tokens, 'Bearer' for JWT.
  String get scheme => 'Token';

  /// Display name and role of the signed-in user (for greetings only;
  /// permissions are always enforced by the server).
  String? get displayName;
  String? get role;

  bool get isSignedIn => token != null;

  /// Called by the API client when the server answers 401.
  void onUnauthorised();

  Future<void> signOut();
}

/// PLACEHOLDER implementation used until Member B's auth module is merged.
/// Keeps the token in memory only.
class InMemoryAuthSession extends AuthSession {
  String? _token;
  String? _displayName;
  String? _role;

  @override
  String? get token => _token;
  @override
  String? get displayName => _displayName;
  @override
  String? get role => _role;

  void signIn({required String token, required String displayName, required String role}) {
    _token = token;
    _displayName = displayName;
    _role = role;
    notifyListeners();
  }

  @override
  void onUnauthorised() => _clear();

  @override
  Future<void> signOut() async => _clear();

  void _clear() {
    if (_token == null) return;
    _token = null;
    _displayName = null;
    _role = null;
    notifyListeners();
  }
}
