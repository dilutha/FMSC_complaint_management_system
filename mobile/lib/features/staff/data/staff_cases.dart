import '../../../core/api_client.dart';
import '../../cases/data/models.dart' show PageResult;

/// One row in the staff case lists (admin, case administrator, department).
class StaffCaseRow {
  const StaffCaseRow({
    required this.id,
    required this.caseNumber,
    required this.title,
    required this.caseType,
    required this.status,
    required this.statusLabel,
    required this.priority,
    required this.category,
    required this.createdAt,
    this.department,
    this.submitterType,
    this.isOverdue = false,
  });

  final int id;
  final String caseNumber;
  final String title;
  final String caseType;
  final String status;
  final String statusLabel;
  final String priority;
  final String category;
  final DateTime createdAt;
  final String? department;
  final String? submitterType;
  final bool isOverdue;

  factory StaffCaseRow.fromJson(Map<String, dynamic> j) {
    final category = j['category'];
    final authority = j['assigned_authority'];
    return StaffCaseRow(
      id: j['id'] as int,
      caseNumber: j['case_number'] as String,
      title: j['title'] as String,
      caseType: j['case_type'] as String,
      status: j['status'] as String,
      statusLabel: j['status_label'] as String,
      priority: j['priority'] as String,
      category: category is Map ? category['name'] as String : (category as String? ?? ''),
      createdAt: DateTime.parse(j['created_at'] as String).toLocal(),
      department: authority is Map ? authority['name'] as String : authority as String?,
      submitterType: (j['submitter_role_label'] as String?),
      isOverdue: (j['is_overdue'] as bool?) ?? false,
    );
  }
}

/// Filters for GET /cases/. They only narrow what the server already allows.
class StaffCaseFilter {
  const StaffCaseFilter({this.statuses, this.search = '', this.departmentId, this.submitterRole, this.queue});
  final String? statuses;
  final String search;
  final int? departmentId;
  final String? submitterRole;
  final String? queue;

  Map<String, String> toQuery(int page) => {
    'page': '$page',
    'page_size': '20',
    'status': ?statuses,
    if (search.trim().isNotEmpty) 'search': search.trim(),
    if (departmentId != null) 'assigned_authority': '$departmentId',
    'submitter_role': ?submitterRole,
    'queue': ?queue,
  };
}

/// Case-management calls used by staff screens. Every call is re-checked by
/// the server (role, department membership and workflow rules).
abstract class StaffCaseRepository {
  Future<PageResult<StaffCaseRow>> list(StaffCaseFilter filter, {int page = 1});
  Future<List<({int id, String name})>> departments();
  Future<void> assign(int caseId, {required int departmentId, required String message, String internalNote = ''});
  Future<void> changeStatus(int caseId, {required String toStatus, String message = '', String resolutionNote = ''});
}

class ApiStaffCaseRepository implements StaffCaseRepository {
  ApiStaffCaseRepository(this._api);
  final ApiClient _api;

  @override
  Future<PageResult<StaffCaseRow>> list(StaffCaseFilter filter, {int page = 1}) async {
    final json = await _api.get('cases/', query: filter.toQuery(page)) as Map<String, dynamic>;
    return PageResult(
      count: json['count'] as int,
      hasNext: json['next'] != null,
      items: [for (final r in json['results'] as List) StaffCaseRow.fromJson(r as Map<String, dynamic>)],
    );
  }

  @override
  Future<List<({int id, String name})>> departments() async => [
    for (final a in (await _api.get('authorities/')) as List)
      (id: (a as Map<String, dynamic>)['id'] as int, name: a['name'] as String),
  ];

  @override
  Future<void> assign(int caseId, {required int departmentId, required String message, String internalNote = ''}) =>
      _api.post('cases/$caseId/assign/', {
        'authority_id': departmentId,
        'message': message,
        if (internalNote.trim().isNotEmpty) 'internal_note': internalNote.trim(),
      });

  @override
  Future<void> changeStatus(int caseId, {required String toStatus, String message = '', String resolutionNote = ''}) =>
      _api.post('cases/$caseId/transition/', {
        'to_status': toStatus,
        'reason': message,
        if (resolutionNote.isNotEmpty) 'resolution_note': resolutionNote,
      });
}
