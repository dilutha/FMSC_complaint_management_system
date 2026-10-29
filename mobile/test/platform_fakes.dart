import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:fmsc_cases/core/api_client.dart';
import 'package:fmsc_cases/design/theme.dart';
import 'package:fmsc_cases/features/admin/data/admin.dart';
import 'package:fmsc_cases/features/auth/data/auth_repository.dart';
import 'package:fmsc_cases/features/auth/data/current_user.dart';
import 'package:fmsc_cases/features/auth/data/platform_auth_session.dart';
import 'package:fmsc_cases/features/auth/data/token_store.dart';
import 'package:fmsc_cases/features/cases/case_scope.dart';
import 'package:fmsc_cases/features/cases/data/models.dart';
import 'package:fmsc_cases/features/dashboard/data/dashboard.dart';
import 'package:fmsc_cases/features/notifications/data/notifications.dart';
import 'package:fmsc_cases/features/suggestions/data/suggestions.dart';
import 'package:fmsc_cases/platform/platform_scope.dart';

import 'fakes.dart';

/// Responses captured from the real Django API (synthetic data); see
/// test/fixtures/platform/README.md.
Map<String, dynamic> fixture(String name) =>
    jsonDecode(File('test/fixtures/platform/$name').readAsStringSync()) as Map<String, dynamic>;

List<dynamic> fixtureList(String name) => jsonDecode(File('test/fixtures/platform/$name').readAsStringSync()) as List;

CurrentUser userWith(String role, Set<String> capabilities) => CurrentUser(
  id: 1,
  username: 'test.$role',
  displayName: 'Test ${role.replaceAll('_', ' ')}',
  role: role,
  roleLabel: role,
  capabilities: capabilities,
);

final studentUser = userWith('student', {});
final managementUser = userWith('management', {'view_dashboard'});
final adminUser = userWith('case_admin', {
  'evaluate_suggestions', 'handle_assigned_cases', 'manage_authorities', 'view_dashboard',
});

ApiException apiError(int status, String message, [Map<String, dynamic> details = const {}]) =>
    ApiException(statusCode: status, code: status == 0 ? 'network' : 'error', message: message, details: details);

class FakeAuthRepository implements AuthRepository {
  ({String token, CurrentUser user})? signInResult;
  Object? signInError;
  CurrentUser? meResult;
  Object? meError;
  int revokeCalls = 0;
  int signInCalls = 0;

  /// When set, sign-in waits for it (simulates a request in flight).
  Completer<void>? holdSignIn;

  @override
  Future<({String token, CurrentUser user})> signIn(String username, String password) async {
    signInCalls++;
    if (holdSignIn != null) await holdSignIn!.future;
    if (signInError != null) throw signInError!;
    return signInResult!;
  }

  @override
  Future<CurrentUser> me() async {
    if (meError != null) throw meError!;
    return meResult!;
  }

  @override
  Future<CurrentUser> updateContact({required String contactNumber, required String department}) async => meResult!;

  @override
  Future<({String token, CurrentUser user})> changePassword(String current, String next) async => signInResult!;

  @override
  Future<void> revoke() async => revokeCalls++;
}

class FakeNotificationRepository implements NotificationRepository {
  List<AppNotification> items = [];
  Object? error;
  final read = <int>[];
  int markAllCalls = 0;

  @override
  Future<PageResult<AppNotification>> list({int page = 1, bool unreadOnly = false}) async {
    if (error != null) throw error!;
    final visible = unreadOnly ? items.where((n) => !n.isRead).toList() : items;
    return PageResult(count: visible.length, items: page == 1 ? visible : const [], hasNext: false);
  }

  @override
  Future<AppNotification> markRead(int id) async {
    read.add(id);
    final i = items.indexWhere((n) => n.id == id);
    items[i] = items[i].copyWith(isRead: true);
    return items[i];
  }

  @override
  Future<void> markAllRead() async {
    markAllCalls++;
    items = [for (final n in items) n.copyWith(isRead: true)];
  }

  @override
  Future<int> unreadCount() async => items.where((n) => !n.isRead).length;
}

class FakeDashboardRepository implements DashboardRepository {
  Object? error;
  DashboardSummary summaryResult = DashboardSummary.fromJson(fixture('dashboard_summary.json'));
  final summaryCalls = <DashboardFilters>[];

  @override
  Future<DashboardSummary> summary(DashboardFilters f) async {
    summaryCalls.add(f);
    if (error != null) throw error!;
    return summaryResult;
  }

  @override
  Future<Trends> trends(DashboardFilters f) async => Trends.fromJson(fixture('dashboard_trends.json'));

  @override
  Future<Workload> workload(DashboardFilters f) async => Workload.fromJson(fixture('dashboard_workload.json'));

  @override
  Future<Ageing> ageing(DashboardFilters f) async => Ageing.fromJson(fixture('dashboard_ageing.json'));

  @override
  Future<PageResult<ReportCase>> report(DashboardFilters f, {int page = 1}) async {
    final json = fixture('report_cases.json');
    return PageResult(
      count: json['count'] as int,
      hasNext: false,
      items: [for (final r in json['results'] as List) ReportCase.fromJson(r as Map<String, dynamic>)],
    );
  }
}

class FakeSuggestionRepository implements SuggestionRepository {
  SuggestionDetail detail = SuggestionDetail.fromJson(fixture('suggestion_detail_officer.json'));
  final calls = <String>[];
  Object? actionError;
  Object? getError;

  @override
  Future<PageResult<SuggestionSummary>> list({int page = 1, String? statuses}) async {
    calls.add('list:$statuses');
    final json = fixture('suggestions.json');
    return PageResult(
      count: json['count'] as int,
      hasNext: false,
      items: [for (final r in json['results'] as List) SuggestionSummary.fromJson(r as Map<String, dynamic>)],
    );
  }

  @override
  Future<SuggestionDetail> get(int id) async {
    if (getError != null) throw getError!;
    return detail;
  }

  Future<SuggestionDetail> _record(String call) async {
    calls.add(call);
    if (actionError != null) throw actionError!;
    return detail;
  }

  @override
  Future<SuggestionDetail> decide(int id, String decision, {String reason = '', int? unitId, DateTime? targetDate}) =>
      _record('decide:$decision:$reason:$unitId');

  @override
  Future<SuggestionDetail> plan(int id, {required DateTime targetDate, String note = ''}) => _record('plan');

  @override
  Future<SuggestionDetail> recordProgress(int id, {required String note, int? percent}) =>
      _record('progress:$note:$percent');

  @override
  Future<SuggestionDetail> markImplemented(int id, String summary) => _record('implemented:$summary');

  @override
  Future<List<({int id, String name})>> units() async => const [(id: 7, name: 'Maintenance Division')];
}

class FakeAdminRepository implements AdminRepository {
  @override
  Future<PageResult<ManagedUser>> users({int page = 1, String search = '', String? role}) async {
    final json = fixture('manage_users.json');
    return PageResult(
      count: json['count'] as int,
      hasNext: false,
      items: [for (final u in json['results'] as List) ManagedUser.fromJson(u as Map<String, dynamic>)],
    );
  }

  @override
  Future<ManagedUser> createUser(Map<String, dynamic> data) async => throw UnimplementedError();

  @override
  Future<ManagedUser> updateUser(int id, Map<String, dynamic> changes) async => throw UnimplementedError();

  @override
  Future<List<ManagedAuthority>> authorities() async => [
    for (final a in fixtureList('manage_authorities.json')) ManagedAuthority.fromJson(a as Map<String, dynamic>),
  ];

  @override
  Future<ManagedAuthority> saveAuthority(int? id, Map<String, dynamic> data) async => throw UnimplementedError();
}

class PlatformHarness {
  PlatformHarness({CurrentUser? user})
    : store = MemoryTokenStore(),
      cases = FakeCaseRepository() {
    session = PlatformAuthSession(store);
    if (user != null) session.signIn(token: 'synthetic', user: user);
    unread = UnreadCounter(notifications);
  }

  final MemoryTokenStore store;
  late final PlatformAuthSession session;
  final auth = FakeAuthRepository();
  final notifications = FakeNotificationRepository();
  late final UnreadCounter unread;
  final dashboard = FakeDashboardRepository();
  final suggestions = FakeSuggestionRepository();
  final admin = FakeAdminRepository();
  final FakeCaseRepository cases;

  Widget wrap(Widget child) => PlatformScope(
    session: session,
    auth: auth,
    notifications: notifications,
    unread: unread,
    dashboard: dashboard,
    suggestions: suggestions,
    admin: admin,
    child: CaseScope(
      repository: cases,
      pickAttachments: ({required List<String> allowedExtensions}) async => const [],
      child: MaterialApp(theme: buildUsjTheme(), home: child),
    ),
  );
}
