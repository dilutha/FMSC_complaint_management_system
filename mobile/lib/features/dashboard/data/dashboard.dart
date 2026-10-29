import '../../../core/api_client.dart';
import '../../cases/data/models.dart' show PageResult;

/// Dashboard filters (all optional). Mirrors the backend query parameters.
class DashboardFilters {
  const DashboardFilters({
    this.dateFrom,
    this.dateTo,
    this.categoryId,
    this.priority,
    this.caseType,
    this.status,
    this.authorityId,
    this.location = '',
  });

  final DateTime? dateFrom;
  final DateTime? dateTo;
  final int? categoryId;
  final String? priority;
  final String? caseType;
  final String? status;
  final int? authorityId;
  final String location;

  static String _date(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Map<String, String> toQuery() => {
    if (dateFrom != null) 'date_from': _date(dateFrom!),
    if (dateTo != null) 'date_to': _date(dateTo!),
    if (categoryId != null) 'category': '$categoryId',
    'priority': ?priority,
    'case_type': ?caseType,
    'status': ?status,
    if (authorityId != null) 'authority': '$authorityId',
    if (location.trim().isNotEmpty) 'location': location.trim(),
  };

  /// Number of filters besides the date range (shown on the Filters button).
  int get refinementCount => [categoryId, priority, caseType, status, authorityId].where((v) => v != null).length +
      (location.trim().isEmpty ? 0 : 1);
}

typedef Count = ({String label, int count});

class Rate {
  const Rate({this.value, required this.numerator, required this.denominator});
  final double? value;
  final int numerator;
  final int denominator;

  factory Rate.fromJson(Map<String, dynamic> j) =>
      Rate(value: (j['value'] as num?)?.toDouble(), numerator: j['numerator'] as int, denominator: j['denominator'] as int);

  String get percent => value == null ? '–' : '${value!.toStringAsFixed(value! % 1 == 0 ? 0 : 1)}%';
}

class Timing {
  const Timing({this.median, this.average, required this.sampleSize});
  final double? median;
  final double? average;
  final int sampleSize;

  factory Timing.fromJson(Map<String, dynamic> j) => Timing(
    median: (j['median'] as num?)?.toDouble(),
    average: (j['average'] as num?)?.toDouble(),
    sampleSize: j['sample_size'] as int,
  );
}

List<Count> _counts(dynamic list) => [
  for (final r in (list as List?) ?? const []) (label: (r as Map)['label'] as String, count: r['count'] as int),
];

class DashboardSummary {
  const DashboardSummary({
    required this.totals,
    required this.rates,
    required this.firstResponseHours,
    required this.resolutionDays,
    required this.byStatus,
    required this.byCategory,
    required this.byPriority,
    required this.byCaseType,
    required this.byLocation,
    required this.suggestionsByStatus,
    required this.suggestionImplementation,
  });

  final Map<String, int> totals;
  final Map<String, Rate> rates;
  final Timing firstResponseHours;
  final Timing resolutionDays;
  final List<Count> byStatus;
  final List<Count> byCategory;
  final List<Count> byPriority;
  final List<Count> byCaseType;
  final List<Count> byLocation;
  final List<Count> suggestionsByStatus;
  final Rate suggestionImplementation;

  int total(String key) => totals[key] ?? 0;

  factory DashboardSummary.fromJson(Map<String, dynamic> j) {
    final timings = j['timings'] as Map<String, dynamic>;
    final suggestions = j['suggestions'] as Map<String, dynamic>;
    return DashboardSummary(
      totals: (j['totals'] as Map<String, dynamic>).map((k, v) => MapEntry(k, v as int)),
      rates: (j['rates'] as Map<String, dynamic>).map((k, v) => MapEntry(k, Rate.fromJson(v as Map<String, dynamic>))),
      firstResponseHours: Timing.fromJson(timings['first_response_hours'] as Map<String, dynamic>),
      resolutionDays: Timing.fromJson(timings['resolution_days'] as Map<String, dynamic>),
      byStatus: _counts(j['by_status']),
      byCategory: _counts(j['by_category']),
      byPriority: _counts(j['by_priority']),
      byCaseType: _counts(j['by_case_type']),
      byLocation: _counts(j['by_location']),
      suggestionsByStatus: _counts(suggestions['by_status']),
      suggestionImplementation: Rate.fromJson(suggestions['implementation_rate'] as Map<String, dynamic>),
    );
  }
}

class WorkloadRow {
  const WorkloadRow({
    required this.authorityId,
    required this.authorityName,
    required this.active,
    required this.notStarted,
    required this.inProgress,
    required this.waiting,
    required this.awaitingVerification,
    required this.overdue,
    required this.resolved,
    this.averageOpenAgeDays,
    this.medianResolutionDays,
  });

  final int authorityId;
  final String authorityName;
  final int active;
  final int notStarted;
  final int inProgress;
  final int waiting;
  final int awaitingVerification;
  final int overdue;
  final int resolved;
  final double? averageOpenAgeDays;
  final double? medianResolutionDays;

  factory WorkloadRow.fromJson(Map<String, dynamic> j) {
    final authority = j['authority'] as Map<String, dynamic>;
    return WorkloadRow(
      authorityId: authority['id'] as int,
      authorityName: authority['name'] as String,
      active: j['active'] as int,
      notStarted: j['not_started'] as int,
      inProgress: j['in_progress'] as int,
      waiting: j['waiting_for_information'] as int,
      awaitingVerification: j['awaiting_verification'] as int,
      overdue: j['overdue'] as int,
      resolved: j['resolved'] as int,
      averageOpenAgeDays: (j['average_open_age_days'] as num?)?.toDouble(),
      medianResolutionDays: (j['median_resolution_days'] as num?)?.toDouble(),
    );
  }
}

class Workload {
  const Workload({required this.rows, required this.note});
  final List<WorkloadRow> rows;
  final String note;

  factory Workload.fromJson(Map<String, dynamic> j) => Workload(
    note: j['note'] as String,
    rows: [for (final r in j['results'] as List) WorkloadRow.fromJson(r as Map<String, dynamic>)],
  );
}

/// One case row in the ageing list and the case report.
class ReportCase {
  const ReportCase({
    required this.id,
    required this.caseNumber,
    required this.title,
    required this.status,
    required this.statusLabel,
    required this.priority,
    required this.ageDays,
    required this.isOverdue,
    this.category,
    this.authority,
  });

  final int id;
  final String caseNumber;
  final String title;
  final String status;
  final String statusLabel;
  final String priority;
  final int ageDays;
  final bool isOverdue;
  final String? category;
  final String? authority;

  factory ReportCase.fromJson(Map<String, dynamic> j) => ReportCase(
    id: j['id'] as int,
    caseNumber: j['case_number'] as String,
    title: j['title'] as String,
    status: j['status'] as String,
    statusLabel: j['status_label'] as String,
    priority: j['priority'] as String,
    ageDays: j['age_days'] as int,
    isOverdue: j['is_overdue'] as bool,
    category: j['category'] as String?,
    authority: j['authority'] as String?,
  );
}

class Ageing {
  const Ageing({required this.count, required this.averageAgeDays, required this.buckets, required this.oldest});
  final int count;
  final double? averageAgeDays;
  final List<Count> buckets;
  final List<ReportCase> oldest;

  factory Ageing.fromJson(Map<String, dynamic> j) => Ageing(
    count: j['count'] as int,
    averageAgeDays: (j['average_age_days'] as num?)?.toDouble(),
    buckets: _counts(j['buckets']),
    oldest: [for (final r in j['oldest'] as List) ReportCase.fromJson(r as Map<String, dynamic>)],
  );
}

class TrendPoint {
  const TrendPoint({required this.period, required this.submitted, required this.solved, required this.closed});
  final DateTime period;
  final int submitted;
  final int solved;
  final int closed;

  factory TrendPoint.fromJson(Map<String, dynamic> j) => TrendPoint(
    period: DateTime.parse(j['period'] as String),
    submitted: j['submitted'] as int,
    solved: j['solved'] as int,
    closed: j['closed'] as int,
  );
}

class Trends {
  const Trends({required this.interval, required this.points});
  final String interval;
  final List<TrendPoint> points;

  factory Trends.fromJson(Map<String, dynamic> j) => Trends(
    interval: j['interval'] as String,
    points: [for (final p in j['series'] as List) TrendPoint.fromJson(p as Map<String, dynamic>)],
  );
}

abstract class DashboardRepository {
  Future<DashboardSummary> summary(DashboardFilters f);
  Future<Workload> workload(DashboardFilters f);
  Future<Ageing> ageing(DashboardFilters f);
  Future<Trends> trends(DashboardFilters f);
  Future<PageResult<ReportCase>> report(DashboardFilters f, {int page = 1});
}

class ApiDashboardRepository implements DashboardRepository {
  ApiDashboardRepository(this._api);
  final ApiClient _api;

  Future<Map<String, dynamic>> _get(String path, DashboardFilters f, [Map<String, String> extra = const {}]) async =>
      await _api.get(path, query: {...f.toQuery(), ...extra}) as Map<String, dynamic>;

  @override
  Future<DashboardSummary> summary(DashboardFilters f) async =>
      DashboardSummary.fromJson(await _get('dashboard/summary/', f));

  @override
  Future<Workload> workload(DashboardFilters f) async => Workload.fromJson(await _get('dashboard/workload/', f));

  @override
  Future<Ageing> ageing(DashboardFilters f) async => Ageing.fromJson(await _get('dashboard/ageing/', f));

  @override
  Future<Trends> trends(DashboardFilters f) async => Trends.fromJson(await _get('dashboard/trends/', f));

  @override
  Future<PageResult<ReportCase>> report(DashboardFilters f, {int page = 1}) async {
    final json = await _get('reports/cases/', f, {'page': '$page'});
    return PageResult(
      count: json['count'] as int,
      hasNext: json['next'] != null,
      items: [for (final r in json['results'] as List) ReportCase.fromJson(r as Map<String, dynamic>)],
    );
  }
}
