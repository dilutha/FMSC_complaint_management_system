// Read-only end-to-end check of the real Flutter data layer against a running
// Django server (e.g. backed by Supabase). Skipped unless LIVE_API_BASE_URL is set:
//
//   flutter test test/live/live_api_test.dart \
//     --dart-define=LIVE_API_BASE_URL=http://127.0.0.1:8000/api/v1/
//
// Requires the demo accounts (python manage.py seed_demo_users). Creates no
// cases or suggestions; it only signs in, reads, and signs out.
import 'package:flutter_test/flutter_test.dart';
import 'package:fmsc_cases/core/api_client.dart';
import 'package:fmsc_cases/features/auth/data/auth_repository.dart';
import 'package:fmsc_cases/features/auth/data/platform_auth_session.dart';
import 'package:fmsc_cases/features/auth/data/token_store.dart';
import 'package:fmsc_cases/features/cases/data/case_repository.dart';
import 'package:fmsc_cases/features/dashboard/data/dashboard.dart';
import 'package:fmsc_cases/features/notifications/data/notifications.dart';
import 'package:fmsc_cases/features/suggestions/data/suggestions.dart';

const baseUrl = String.fromEnvironment('LIVE_API_BASE_URL');
const password = 'Password@123'; // development-only demo password

({ApiClient api, PlatformAuthSession session}) client({String url = baseUrl, Duration? timeout}) {
  final session = PlatformAuthSession(MemoryTokenStore());
  return (api: ApiClient(baseUrl: url, session: session, timeout: timeout ?? const Duration(seconds: 20)), session: session);
}

Future<int> timed(String label, Future<void> Function() body) async {
  final watch = Stopwatch()..start();
  await body();
  final ms = watch.elapsedMilliseconds;
  // ignore: avoid_print
  print('  $label: ${ms}ms');
  return ms;
}

void main() {
  final skip = baseUrl.isEmpty ? 'Set --dart-define=LIVE_API_BASE_URL to run against a server' : null;

  group('live API', skip: skip, () {
    const roles = {
      'demo_student': 'student',
      'demo_lecturer': 'lecturer',
      'demo_authority': 'authority',
      'demo_it_officer': 'authority',
      'demo_case_admin': 'case_admin',
      'demo_management': 'management',
      'demo_system_admin': 'system_admin',
    };

    for (final entry in roles.entries) {
      test('${entry.key} signs in, reads its data and signs out', () async {
        final c = client();
        final auth = ApiAuthRepository(c.api);
        late ({String token, dynamic user}) result;
        await timed('${entry.key} sign-in', () async => result = await auth.signIn(entry.key, password));
        expect(result.user.role, entry.value);
        await c.session.signIn(token: result.token, user: result.user);

        final me = await auth.me();
        expect(me.username, entry.key);
        await timed('${entry.key} my cases', () => ApiCaseRepository(c.api).listMyCases());
        await timed('${entry.key} notifications', () => ApiNotificationRepository(c.api).list());

        final dashboard = ApiDashboardRepository(c.api);
        if (me.canViewDashboard) {
          await timed('${entry.key} dashboard summary', () => dashboard.summary(const DashboardFilters()));
        } else {
          await expectLater(dashboard.summary(const DashboardFilters()),
              throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 403)));
        }
        if (me.seesSuggestionQueue) {
          await timed('${entry.key} suggestions', () => ApiSuggestionRepository(c.api).list());
        }
        await c.session.signOut(); // revoke is wired by the app; here we revoke explicitly
        await auth.revoke().catchError((_) {});
      });
    }

    test('wrong password is a 400 the login screen can explain', () async {
      final auth = ApiAuthRepository(client().api);
      await expectLater(auth.signIn('demo_student', 'wrong-password'),
          throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 400)));
    });

    test('an expired or invalid token signs the session out', () async {
      final c = client();
      await c.session.signIn(token: 'not-a-real-token', user: (await ApiAuthRepository(client().api).signIn('demo_student', password)).user);
      await expectLater(ApiAuthRepository(c.api).me(), throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 401)));
      expect(c.session.isSignedIn, isFalse);
    });

    test('an unreachable server is reported as a timeout, not a hang', () async {
      final c = client(url: 'http://10.255.255.1:8000/api/v1/', timeout: const Duration(seconds: 3));
      final watch = Stopwatch()..start();
      await expectLater(ApiAuthRepository(c.api).signIn('demo_student', password),
          throwsA(isA<ApiException>().having((e) => e.code, 'code', anyOf('timeout', 'network'))));
      expect(watch.elapsed, lessThan(const Duration(seconds: 6)));
    });
  });
}
