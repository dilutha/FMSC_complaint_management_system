import 'package:flutter_test/flutter_test.dart';
import 'package:fmsc_cases/features/admin/data/admin.dart';
import 'package:fmsc_cases/features/auth/data/current_user.dart';
import 'package:fmsc_cases/features/dashboard/data/dashboard.dart';
import 'package:fmsc_cases/features/notifications/data/notifications.dart';
import 'package:fmsc_cases/features/suggestions/data/suggestions.dart';

import 'platform_fakes.dart';

/// The models must parse responses captured from the real Django API.
void main() {
  test('login and me responses', () {
    final login = fixture('login.json');
    final officer = CurrentUser.fromJson(login['user'] as Map<String, dynamic>);
    expect(officer.role, 'authority');
    expect(officer.handlesCases, isTrue);
    expect(officer.canViewDashboard, isFalse);
    expect(officer.authorities.single.name, 'Maintenance Division');

    final management = CurrentUser.fromJson(fixture('me_management.json'));
    expect(management.canViewDashboard, isTrue);
    expect(management.canEvaluateSuggestions, isFalse);
    expect(management.seesSuggestionQueue, isTrue);
  });

  test('notifications carry navigation targets', () {
    final json = fixture('notifications.json');
    final items = [for (final n in json['results'] as List) AppNotification.fromJson(n as Map<String, dynamic>)];
    expect(items, hasLength(json['count']));
    expect(items.every((n) => !n.isRead), isTrue);
    expect(items.map((n) => n.targetType).toSet(), {'case', 'suggestion'});
    expect(items.firstWhere((n) => n.eventType == 'suggestion_decision').title, contains('accepted'));
    expect(fixture('unread_count.json')['unread'], items.length);
  });

  test('dashboard summary, workload, ageing, trends and report', () {
    final summary = DashboardSummary.fromJson(fixture('dashboard_summary.json'));
    expect(summary.total('total'), summary.total('complaints') + summary.total('suggestions'));
    expect(summary.byStatus.map((c) => c.count).reduce((a, b) => a + b), summary.total('total'));
    expect(summary.rates.keys, containsAll(['overdue', 'resolution', 'reopening', 'repeat_issue']));

    final workload = Workload.fromJson(fixture('dashboard_workload.json'));
    expect(workload.note, contains('not, on its own'));
    expect(workload.rows.any((r) => r.authorityName == 'Maintenance Division'), isTrue);

    final ageing = Ageing.fromJson(fixture('dashboard_ageing.json'));
    expect(ageing.buckets, hasLength(5));
    expect(ageing.oldest.length, ageing.count);

    final trends = Trends.fromJson(fixture('dashboard_trends.json'));
    expect(trends.interval, 'day');
    expect(trends.points.fold<int>(0, (a, p) => a + p.submitted), summary.total('total'));

    final report = fixture('report_cases.json');
    expect((report['results'] as List).map((r) => ReportCase.fromJson(r as Map<String, dynamic>)), hasLength(report['count']));
  });

  test('suggestion list and detail', () {
    final list = fixture('suggestions.json');
    final s = SuggestionSummary.fromJson((list['results'] as List).single as Map<String, dynamic>);
    expect(s.status, 'accepted');
    expect(s.responsibleUnit?.name, 'Maintenance Division');

    final d = SuggestionDetail.fromJson(fixture('suggestion_detail_officer.json'));
    expect(d.allowedActions, {'plan', 'record_progress', 'mark_implemented'});
    expect(d.summary.progressPercent, 40);
    expect(d.progress.single.note, 'Sockets ordered.');
    expect(d.history.map((h) => h.toStatus), contains('accepted'));
  });

  test('user and authority management', () {
    final users = fixture('manage_users.json');
    final parsed = [for (final u in users['results'] as List) ManagedUser.fromJson(u as Map<String, dynamic>)];
    expect(parsed.map((u) => u.role), containsAll(['student', 'authority']));
    expect((users['results'] as List).every((u) => !(u as Map).containsKey('password')), isTrue);
    final authorities = [for (final a in fixtureList('manage_authorities.json')) ManagedAuthority.fromJson(a as Map<String, dynamic>)];
    expect(authorities.firstWhere((a) => a.name == 'Maintenance Division').memberCount, 1);
  });
}
