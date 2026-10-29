import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fmsc_cases/features/admin/presentation/users_screen.dart';
import 'package:fmsc_cases/features/auth/data/platform_auth_session.dart';
import 'package:fmsc_cases/features/auth/presentation/login_screen.dart';
import 'package:fmsc_cases/features/cases/data/models.dart';
import 'package:fmsc_cases/features/cases/presentation/case_detail_screen.dart';
import 'package:fmsc_cases/features/dashboard/data/dashboard.dart';
import 'package:fmsc_cases/features/dashboard/presentation/dashboard_screen.dart';
import 'package:fmsc_cases/features/notifications/data/notifications.dart';
import 'package:fmsc_cases/features/notifications/presentation/notifications_screen.dart';
import 'package:fmsc_cases/features/suggestions/data/suggestions.dart';
import 'package:fmsc_cases/features/suggestions/presentation/suggestion_detail_screen.dart';
import 'package:fmsc_cases/main.dart';
import 'package:fmsc_cases/platform/app_shell.dart';

import 'fakes.dart';
import 'platform_fakes.dart';

AppNotification note(int id, {bool read = false, String type = 'case', String title = 'Case update'}) =>
    AppNotification(
      id: id,
      eventType: 'status_update',
      title: '$title $id',
      body: 'Body $id',
      isRead: read,
      createdAt: DateTime(2026, 10, 27, 9),
      targetType: type,
      targetId: 1,
    );

void main() {
  group('Session', () {
    test('restores a saved token and keeps it in the token store', () async {
      final h = PlatformHarness();
      h.store.value = 'saved';
      h.auth.meResult = studentUser;
      await h.session.restore(h.auth.me);
      expect(h.session.state, SessionState.signedIn);
      expect(h.session.token, 'saved');
    });

    test('an expired token signs out, clears storage and explains why', () async {
      final h = PlatformHarness(user: studentUser);
      await Future<void>.delayed(Duration.zero);
      expect(h.store.value, 'synthetic');
      h.session.onUnauthorised();
      await Future<void>.delayed(Duration.zero);
      expect(h.session.state, SessionState.signedOut);
      expect(h.store.value, isNull);
      expect(h.session.takeNotice(), contains('expired'));
    });

    test('sign out revokes on the server and still succeeds offline', () async {
      final h = PlatformHarness(user: studentUser);
      h.session.revokeOnServer = () async => throw apiError(0, 'offline');
      await h.session.signOut();
      expect(h.session.isSignedIn, isFalse);
    });
  });

  group('Login', () {
    testWidgets('validates empty fields', (tester) async {
      final h = PlatformHarness();
      await tester.pumpWidget(h.wrap(const LoginScreen()));
      await tester.tap(find.text('Sign in'));
      await tester.pump();
      expect(find.text('Enter your username or email.'), findsOneWidget);
      expect(find.text('Enter your password.'), findsOneWidget);
    });

    testWidgets('shows a clear message for wrong credentials', (tester) async {
      final h = PlatformHarness()..auth.signInError = apiError(400, 'Incorrect username or password.');
      await tester.pumpWidget(h.wrap(const LoginScreen()));
      await tester.enterText(find.byType(TextFormField).at(0), 'student');
      await tester.enterText(find.byType(TextFormField).at(1), 'wrong');
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Incorrect username or password'), findsOneWidget);
      expect(h.session.isSignedIn, isFalse);
    });

    testWidgets('successful sign-in opens the role-based shell', (tester) async {
      final h = PlatformHarness()..auth.signInResult = (token: 'tok', user: managementUser);
      h.session.restore(() async => throw apiError(401, 'no token'));
      await tester.pumpWidget(FmscApp(
        session: h.session,
        auth: h.auth,
        caseRepository: h.cases,
        notifications: h.notifications,
        dashboard: h.dashboard,
        suggestions: h.suggestions,
        admin: h.admin,
        pickAttachments: ({required List<String> allowedExtensions}) async => const [],
      ));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField).at(0), 'manager');
      await tester.enterText(find.byType(TextFormField).at(1), 'Synthetic-pass-123');
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(find.byType(AppShell), findsOneWidget);
      expect(h.store.value, 'tok');
    });
  });

  group('AppShell navigation', () {
    Future<List<String>> labels(WidgetTester tester, user) async {
      final h = PlatformHarness(user: user);
      await tester.pumpWidget(h.wrap(const AppShell()));
      await tester.pumpAndSettle();
      return [
        for (final d in tester.widget<NavigationBar>(find.byType(NavigationBar)).destinations)
          (d as NavigationDestination).label,
      ];
    }

    testWidgets('students see only their own areas', (tester) async {
      expect(await labels(tester, studentUser), ['Cases', 'Alerts', 'Profile']);
    });

    testWidgets('management sees the dashboard', (tester) async {
      expect(await labels(tester, managementUser), ['Cases', 'Dashboard', 'Suggestions', 'Alerts', 'Profile']);
    });

    testWidgets('unread badge shows the count', (tester) async {
      final h = PlatformHarness(user: studentUser)..notifications.items = [note(1), note(2), note(3, read: true)];
      await tester.pumpWidget(h.wrap(const AppShell()));
      await tester.pumpAndSettle();
      expect(find.descendant(of: find.byType(Badge), matching: find.text('2')), findsOneWidget);
    });
  });

  group('NotificationsScreen', () {
    testWidgets('loading, then unread items labelled "New" (not colour alone)', (tester) async {
      final h = PlatformHarness(user: studentUser)..notifications.items = [note(1), note(2, read: true)];
      await tester.pumpWidget(h.wrap(const NotificationsScreen()));
      expect(find.text('Loading notifications…'), findsOneWidget);
      await tester.pumpAndSettle();
      expect(find.text('Case update 1'), findsOneWidget);
      expect(find.text('New'), findsOneWidget);
    });

    testWidgets('tapping marks read and opens the existing case-detail screen', (tester) async {
      final h = PlatformHarness(user: studentUser)..notifications.items = [note(1)];
      h.cases.detail = CaseDetail.fromJson(caseJson());
      await tester.pumpWidget(h.wrap(const NotificationsScreen()));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Case update 1'));
      await tester.pumpAndSettle();
      expect(h.notifications.read, [1]);
      expect(find.byType(CaseDetailScreen), findsOneWidget);
    });

    testWidgets('suggestion targets open the suggestion screen', (tester) async {
      final h = PlatformHarness(user: studentUser)..notifications.items = [note(1, type: 'suggestion')];
      await tester.pumpWidget(h.wrap(const NotificationsScreen()));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Case update 1'));
      await tester.pumpAndSettle();
      expect(find.byType(SuggestionDetailScreen), findsOneWidget);
    });

    testWidgets('empty state', (tester) async {
      final h = PlatformHarness(user: studentUser);
      await tester.pumpWidget(h.wrap(const NotificationsScreen()));
      await tester.pumpAndSettle();
      expect(find.text('No notifications yet'), findsOneWidget);
    });

    testWidgets('error state retries', (tester) async {
      final h = PlatformHarness(user: studentUser)..notifications.error = apiError(0, 'No connection to the server.');
      await tester.pumpWidget(h.wrap(const NotificationsScreen()));
      await tester.pumpAndSettle();
      expect(find.text('No connection to the server.'), findsOneWidget);
      h.notifications
        ..error = null
        ..items = [note(9)];
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Case update 9'), findsOneWidget);
    });

    testWidgets('mark all read clears the badge', (tester) async {
      final h = PlatformHarness(user: studentUser)..notifications.items = [note(1), note(2)];
      await tester.pumpWidget(h.wrap(const NotificationsScreen()));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Mark all read'));
      await tester.pumpAndSettle();
      expect(h.notifications.markAllCalls, 1);
      expect(h.unread.count, 0);
      expect(find.text('New'), findsNothing);
    });
  });

  group('DashboardScreen', () {
    testWidgets('shows KPIs from the summary with a default 90-day range', (tester) async {
      final h = PlatformHarness(user: managementUser);
      await tester.pumpWidget(h.wrap(const DashboardScreen()));
      expect(find.text('Loading dashboard…'), findsOneWidget);
      await tester.pumpAndSettle();
      final s = h.dashboard.summaryResult;
      expect(find.text('Total cases'), findsOneWidget);
      expect(find.text('${s.total('total')}'), findsWidgets);
      expect(h.dashboard.summaryCalls.single.dateFrom, isNotNull);
    });

    testWidgets('changing the period reloads with the new range', (tester) async {
      final h = PlatformHarness(user: managementUser);
      await tester.pumpWidget(h.wrap(const DashboardScreen()));
      await tester.pumpAndSettle();
      await tester.tap(find.text('All time'));
      await tester.pumpAndSettle();
      expect(h.dashboard.summaryCalls.last.dateFrom, isNull);
    });

    testWidgets('error state retries', (tester) async {
      final h = PlatformHarness(user: managementUser)..dashboard.error = apiError(403, 'You do not have permission.');
      await tester.pumpWidget(h.wrap(const DashboardScreen()));
      await tester.pumpAndSettle();
      expect(find.text('You do not have permission.'), findsOneWidget);
      h.dashboard.error = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Total cases'), findsOneWidget);
    });

    testWidgets('empty data explains itself', (tester) async {
      final h = PlatformHarness(user: managementUser);
      final empty = fixture('dashboard_summary.json');
      empty['totals'] = <String, dynamic>{for (final k in (empty['totals'] as Map).keys) k as String: 0};
      h.dashboard.summaryResult = DashboardSummary.fromJson(empty);
      await tester.pumpWidget(h.wrap(const DashboardScreen()));
      await tester.pumpAndSettle();
      expect(find.text('No cases match these filters'), findsOneWidget);
    });
  });

  group('SuggestionDetailScreen', () {
    testWidgets('shows decision, progress and allowed actions', (tester) async {
      tester.view.physicalSize = const Size(1200, 3200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final h = PlatformHarness(user: adminUser);
      await tester.pumpWidget(h.wrap(const SuggestionDetailScreen(suggestionId: 4)));
      await tester.pumpAndSettle();
      expect(find.text('Accepted for implementation'), findsOneWidget);
      expect(find.text('40%'), findsOneWidget);
      expect(find.text('Sockets ordered.'), findsOneWidget);
      expect(find.text('Set target date'), findsOneWidget);
      expect(find.text('Decline'), findsNothing);
    });

    testWidgets('decline requires a reason before calling the server', (tester) async {
      final h = PlatformHarness(user: adminUser);
      final json = fixture('suggestion_detail_officer.json')
        ..['status'] = 'under_evaluation'
        ..['status_label'] = 'Under Evaluation'
        ..['decided_at'] = null
        ..['allowed_actions'] = ['accept', 'decline'];
      h.suggestions.detail = SuggestionDetail.fromJson(json);
      await tester.pumpWidget(h.wrap(const SuggestionDetailScreen(suggestionId: 4)));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(OutlinedButton, 'Decline'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Decline'));
      await tester.pumpAndSettle();
      expect(find.text('A reason is required.'), findsOneWidget);
      expect(h.suggestions.calls.where((c) => c.startsWith('decide')), isEmpty);

      await tester.enterText(find.byType(TextFormField), 'Short');
      await tester.tap(find.widgetWithText(FilledButton, 'Decline'));
      await tester.pumpAndSettle();
      expect(find.text('Enter at least 10 characters.'), findsOneWidget);

      await tester.enterText(find.byType(TextFormField), 'Planned as part of next year\'s renovation.');
      await tester.tap(find.widgetWithText(FilledButton, 'Decline'));
      await tester.pumpAndSettle();
      expect(h.suggestions.calls.last, "decide:decline:Planned as part of next year's renovation.:null");
      expect(find.text('Suggestion declined.'), findsOneWidget);
    });

    testWidgets('server field errors appear under the field', (tester) async {
      final h = PlatformHarness(user: adminUser)
        ..suggestions.actionError = apiError(400, 'Please correct the highlighted fields.', {
          'note': ['This field is required.'],
        });
      await tester.pumpWidget(h.wrap(const SuggestionDetailScreen(suggestionId: 4)));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add progress update'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField), 'Work continues');
      await tester.tap(find.widgetWithText(FilledButton, 'Add progress update'));
      await tester.pumpAndSettle();
      expect(find.text('This field is required.'), findsOneWidget);
    });

    testWidgets('not found', (tester) async {
      final h = PlatformHarness(user: studentUser)..suggestions.getError = apiError(404, 'Not found.');
      await tester.pumpWidget(h.wrap(const SuggestionDetailScreen(suggestionId: 999)));
      await tester.pumpAndSettle();
      expect(find.text('Suggestion not found'), findsOneWidget);
    });
  });

  testWidgets('UsersScreen lists accounts', (tester) async {
    final h = PlatformHarness(user: adminUser);
    await tester.pumpWidget(h.wrap(const UsersScreen()));
    await tester.pumpAndSettle();
    expect(find.textContaining('fx.student'), findsOneWidget);
    expect(find.text('New account'), findsOneWidget);
  });

  test('dashboard filters serialise to the API query', () {
    final f = DashboardFilters(
      dateFrom: DateTime(2026, 1, 5),
      dateTo: DateTime(2026, 2, 1),
      categoryId: 3,
      priority: 'urgent',
      location: ' Hall A ',
    );
    expect(f.toQuery(), {
      'date_from': '2026-01-05',
      'date_to': '2026-02-01',
      'category': '3',
      'priority': 'urgent',
      'location': 'Hall A',
    });
    expect(f.refinementCount, 3);
    expect(PageResult(count: 0, items: const [], hasNext: false).items, isEmpty);
  });
}
