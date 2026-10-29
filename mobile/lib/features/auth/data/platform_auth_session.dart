import '../../../integration/auth_session.dart';
import 'current_user.dart';
import 'token_store.dart';

enum SessionState { restoring, signedOut, signedIn }

/// The real [AuthSession] (shared contract with the case module). Keeps the
/// token in [TokenStore], exposes the signed-in [CurrentUser], and signs out
/// automatically when the server answers 401 (expired or revoked token).
class PlatformAuthSession extends AuthSession {
  PlatformAuthSession(this._store);

  final TokenStore _store;
  String? _token;
  CurrentUser? _user;
  SessionState _state = SessionState.restoring;
  String? _notice;

  /// Revokes the token on the server; set by the auth repository.
  Future<void> Function()? revokeOnServer;

  @override
  String? get token => _token;
  CurrentUser? get user => _user;
  SessionState get state => _state;

  @override
  bool get isSignedIn => _token != null && _user != null;

  @override
  String? get displayName => _user?.displayName;

  @override
  String? get role => _user?.role;

  /// A message for the sign-in screen, e.g. "Your session has expired".
  String? takeNotice() {
    final notice = _notice;
    _notice = null;
    return notice;
  }

  /// Loads a saved token and confirms it with [fetchUser] (GET /auth/me/).
  Future<void> restore(Future<CurrentUser> Function() fetchUser) async {
    _token = await _store.read();
    if (_token == null) {
      _setState(SessionState.signedOut);
      return;
    }
    try {
      _user = await fetchUser();
      _setState(SessionState.signedIn);
    } catch (_) {
      // Expired token (401 already cleared it) or offline: ask to sign in.
      await _clear(notify: false);
      _setState(SessionState.signedOut);
    }
  }

  Future<void> signIn({required String token, required CurrentUser user}) async {
    _token = token;
    _user = user;
    await _store.write(token);
    _setState(SessionState.signedIn);
  }

  /// After a profile edit or password change.
  Future<void> update({String? token, CurrentUser? user}) async {
    if (token != null) {
      _token = token;
      await _store.write(token);
    }
    if (user != null) _user = user;
    notifyListeners();
  }

  @override
  void onUnauthorised() {
    if (_token == null) return;
    _notice = 'Your session has expired. Please sign in again.';
    _clear();
  }

  @override
  Future<void> signOut() async {
    try {
      await revokeOnServer?.call();
    } catch (_) {
      // Signing out locally must always succeed, even offline.
    }
    await _clear();
  }

  Future<void> _clear({bool notify = true}) async {
    _token = null;
    _user = null;
    await _store.delete();
    if (notify) _setState(SessionState.signedOut);
  }

  void _setState(SessionState s) {
    _state = s;
    notifyListeners();
  }
}
