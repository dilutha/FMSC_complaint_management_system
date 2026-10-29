import '../../../core/api_client.dart';
import '../../cases/data/models.dart' show PageResult;

class SuggestionSummary {
  const SuggestionSummary({
    required this.id,
    required this.caseNumber,
    required this.title,
    required this.category,
    required this.location,
    required this.createdAt,
    required this.status,
    required this.statusLabel,
    required this.caseStatus,
    required this.progressPercent,
    this.responsibleUnit,
    this.targetDate,
  });

  /// The case id (suggestions are cases with case_type "suggestion").
  final int id;
  final String caseNumber;
  final String title;
  final String category;
  final String location;
  final DateTime createdAt;
  final String status;
  final String statusLabel;
  final String caseStatus;
  final int progressPercent;
  final ({int id, String name})? responsibleUnit;
  final DateTime? targetDate;

  factory SuggestionSummary.fromJson(Map<String, dynamic> j) {
    final unit = j['responsible_unit'] as Map<String, dynamic>?;
    return SuggestionSummary(
      id: j['id'] as int,
      caseNumber: j['case_number'] as String,
      title: j['title'] as String,
      category: j['category'] as String,
      location: j['location'] as String,
      createdAt: DateTime.parse(j['created_at'] as String).toLocal(),
      status: j['status'] as String,
      statusLabel: j['status_label'] as String,
      caseStatus: j['case_status'] as String,
      progressPercent: j['progress_percent'] as int,
      responsibleUnit: unit == null ? null : (id: unit['id'] as int, name: unit['name'] as String),
      targetDate: j['target_date'] == null ? null : DateTime.parse(j['target_date'] as String),
    );
  }
}

class SuggestionHistoryEntry {
  const SuggestionHistoryEntry({
    required this.toStatus,
    required this.toStatusLabel,
    required this.actor,
    required this.reason,
    required this.createdAt,
    this.responsibleUnit,
    this.targetDate,
  });

  final String toStatus;
  final String toStatusLabel;
  final String actor;
  final String reason;
  final DateTime createdAt;
  final String? responsibleUnit;
  final DateTime? targetDate;

  factory SuggestionHistoryEntry.fromJson(Map<String, dynamic> j) => SuggestionHistoryEntry(
    toStatus: j['to_status'] as String,
    toStatusLabel: j['to_status_label'] as String,
    actor: j['actor'] as String,
    reason: (j['reason'] as String?) ?? '',
    createdAt: DateTime.parse(j['created_at'] as String).toLocal(),
    responsibleUnit: j['responsible_unit'] as String?,
    targetDate: j['target_date'] == null ? null : DateTime.parse(j['target_date'] as String),
  );
}

class ProgressEntry {
  const ProgressEntry({required this.note, required this.author, required this.createdAt, this.percentComplete});
  final String note;
  final String author;
  final DateTime createdAt;
  final int? percentComplete;

  factory ProgressEntry.fromJson(Map<String, dynamic> j) => ProgressEntry(
    note: j['note'] as String,
    author: j['author'] as String,
    createdAt: DateTime.parse(j['created_at'] as String).toLocal(),
    percentComplete: j['percent_complete'] as int?,
  );
}

class SuggestionDetail {
  const SuggestionDetail({
    required this.summary,
    required this.description,
    required this.submittedBy,
    required this.decisionReason,
    required this.planNote,
    required this.implementationSummary,
    required this.history,
    required this.progress,
    required this.allowedActions,
    this.decidedBy,
    this.decidedAt,
    this.implementedAt,
  });

  final SuggestionSummary summary;
  final String description;
  final String submittedBy;
  final String decisionReason;
  final String planNote;
  final String implementationSummary;
  final List<SuggestionHistoryEntry> history;
  final List<ProgressEntry> progress;

  /// start_evaluation, accept, decline, reconsider, plan, record_progress, mark_implemented
  final Set<String> allowedActions;
  final String? decidedBy;
  final DateTime? decidedAt;
  final DateTime? implementedAt;

  bool can(String action) => allowedActions.contains(action);

  factory SuggestionDetail.fromJson(Map<String, dynamic> j) => SuggestionDetail(
    summary: SuggestionSummary.fromJson(j),
    description: j['description'] as String,
    submittedBy: j['submitted_by'] as String,
    decisionReason: (j['decision_reason'] as String?) ?? '',
    planNote: (j['plan_note'] as String?) ?? '',
    implementationSummary: (j['implementation_summary'] as String?) ?? '',
    history: [for (final h in j['history'] as List) SuggestionHistoryEntry.fromJson(h as Map<String, dynamic>)],
    progress: [for (final p in j['progress_updates'] as List) ProgressEntry.fromJson(p as Map<String, dynamic>)],
    allowedActions: {for (final a in j['allowed_actions'] as List) a as String},
    decidedBy: j['decided_by'] as String?,
    decidedAt: j['decided_at'] == null ? null : DateTime.parse(j['decided_at'] as String).toLocal(),
    implementedAt: j['implemented_at'] == null ? null : DateTime.parse(j['implemented_at'] as String).toLocal(),
  );
}

String _date(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

abstract class SuggestionRepository {
  Future<PageResult<SuggestionSummary>> list({int page = 1, String? statuses});
  Future<SuggestionDetail> get(int id);
  Future<SuggestionDetail> decide(int id, String decision, {String reason = '', int? unitId, DateTime? targetDate});
  Future<SuggestionDetail> plan(int id, {required DateTime targetDate, String note = ''});
  Future<SuggestionDetail> recordProgress(int id, {required String note, int? percent});
  Future<SuggestionDetail> markImplemented(int id, String summary);

  /// Active responsible units (administrators only).
  Future<List<({int id, String name})>> units();
}

class ApiSuggestionRepository implements SuggestionRepository {
  ApiSuggestionRepository(this._api);
  final ApiClient _api;

  SuggestionDetail _detail(dynamic json) => SuggestionDetail.fromJson(json as Map<String, dynamic>);

  @override
  Future<PageResult<SuggestionSummary>> list({int page = 1, String? statuses}) async {
    final json =
        await _api.get('suggestions/', query: {'page': '$page', 'status': ?statuses})
            as Map<String, dynamic>;
    return PageResult(
      count: json['count'] as int,
      hasNext: json['next'] != null,
      items: [for (final e in json['results'] as List) SuggestionSummary.fromJson(e as Map<String, dynamic>)],
    );
  }

  @override
  Future<SuggestionDetail> get(int id) async => _detail(await _api.get('suggestions/$id/'));

  @override
  Future<SuggestionDetail> decide(int id, String decision, {String reason = '', int? unitId, DateTime? targetDate}) async =>
      _detail(await _api.post('suggestions/$id/decision/', {
        'decision': decision,
        'reason': reason,
        'responsible_unit_id': ?unitId,
        if (targetDate != null) 'target_date': _date(targetDate),
      }));

  @override
  Future<SuggestionDetail> plan(int id, {required DateTime targetDate, String note = ''}) async =>
      _detail(await _api.post('suggestions/$id/plan/', {'target_date': _date(targetDate), 'plan_note': note}));

  @override
  Future<SuggestionDetail> recordProgress(int id, {required String note, int? percent}) async =>
      _detail(await _api.post('suggestions/$id/progress/', {'note': note, 'percent_complete': ?percent}));

  @override
  Future<SuggestionDetail> markImplemented(int id, String summary) async =>
      _detail(await _api.post('suggestions/$id/implementation/', {'summary': summary}));

  @override
  Future<List<({int id, String name})>> units() async => [
    for (final a in (await _api.get('authorities/')) as List)
      (id: (a as Map<String, dynamic>)['id'] as int, name: a['name'] as String),
  ];
}
