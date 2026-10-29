import '../../../core/api_client.dart';
import 'current_user.dart';

abstract class AuthRepository {
  Future<({String token, CurrentUser user})> signIn(String username, String password);
  Future<CurrentUser> me();
  Future<CurrentUser> updateContact({required String contactNumber, required String department});
  Future<({String token, CurrentUser user})> changePassword(String current, String next);
  Future<void> revoke();
}

class ApiAuthRepository implements AuthRepository {
  ApiAuthRepository(this._api);
  final ApiClient _api;

  ({String token, CurrentUser user}) _tokenResponse(dynamic json) {
    final map = json as Map<String, dynamic>;
    return (token: map['token'] as String, user: CurrentUser.fromJson(map['user'] as Map<String, dynamic>));
  }

  @override
  Future<({String token, CurrentUser user})> signIn(String username, String password) async =>
      _tokenResponse(await _api.post('auth/token/', {'username': username, 'password': password}));

  @override
  Future<CurrentUser> me() async => CurrentUser.fromJson(await _api.get('auth/me/') as Map<String, dynamic>);

  @override
  Future<CurrentUser> updateContact({required String contactNumber, required String department}) async =>
      CurrentUser.fromJson(
        await _api.patch('auth/me/', {'contact_number': contactNumber, 'department': department})
            as Map<String, dynamic>,
      );

  @override
  Future<({String token, CurrentUser user})> changePassword(String current, String next) async =>
      _tokenResponse(await _api.post('auth/change-password/', {'current_password': current, 'new_password': next}));

  @override
  Future<void> revoke() => _api.post('auth/logout/', const {});
}
