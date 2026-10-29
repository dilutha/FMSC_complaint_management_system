import '../../staff/data/staff_cases.dart';

/// GET /dashboard/overview/: the signed-in user's role-scoped dashboard.
/// The server decides the scope (own cases, own department, or faculty-wide).
class DashboardOverview {
  const DashboardOverview({
    required this.workspace,
    required this.roleLabel,
    required this.counts,
    required this.recent,
    this.departments = const [],
    this.byStatus = const [],
    this.byDepartment = const [],
    this.activity = const [],
  });

  /// complainer | department | case_admin | admin | management
  final String workspace;
  final String roleLabel;
  final Map<String, int> counts;
  final List<StaffCaseRow> recent;

  /// For department users: the department(s) they belong to.
  final List<String> departments;
  final List<({String label, int count})> byStatus;
  final List<({String name, int active, int overdue, int resolved})> byDepartment;
  final List<({int caseId, String caseNumber, String title, String status, String actor, String message, DateTime at})>
  activity;

  int count(String key) => counts[key] ?? 0;

  factory DashboardOverview.fromJson(Map<String, dynamic> j) => DashboardOverview(
    workspace: j['workspace'] as String,
    roleLabel: j['role_label'] as String,
    counts: (j['counts'] as Map<String, dynamic>).map((k, v) => MapEntry(k, v as int)),
    recent: [for (final r in j['recent'] as List) StaffCaseRow.fromJson(r as Map<String, dynamic>)],
    departments: [for (final d in (j['department'] as List?) ?? const []) (d as Map)['name'] as String],
    byStatus: [
      for (final s in (j['by_status'] as List?) ?? const [])
        (label: (s as Map)['label'] as String, count: s['count'] as int),
    ],
    byDepartment: [
      for (final d in (j['by_department'] as List?) ?? const [])
        (
          name: (d as Map)['name'] as String,
          active: d['active'] as int,
          overdue: d['overdue'] as int,
          resolved: d['resolved'] as int,
        ),
    ],
    activity: [
      for (final a in (j['recent_activity'] as List?) ?? const [])
        (
          caseId: (a as Map)['case_id'] as int,
          caseNumber: a['case_number'] as String,
          title: a['title'] as String,
          status: a['to_status_label'] as String,
          actor: a['actor'] as String,
          message: (a['message'] as String?) ?? '',
          at: DateTime.parse(a['at'] as String).toLocal(),
        ),
    ],
  );
}
