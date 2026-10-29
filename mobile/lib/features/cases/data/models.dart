/// Typed views of the /api/v1 case payloads (see docs/API.md).
library;

DateTime? _date(dynamic v) => v == null ? null : DateTime.parse(v as String).toLocal();

class Category {
  const Category({required this.id, required this.name, required this.code, this.description = ''});
  final int id;
  final String name;
  final String code;
  final String description;

  factory Category.fromJson(Map<String, dynamic> j) => Category(
    id: j['id'] as int,
    name: j['name'] as String,
    code: j['code'] as String,
    description: (j['description'] as String?) ?? '',
  );
}

class AuthorityRef {
  const AuthorityRef({required this.id, required this.name});
  final int id;
  final String name;

  static AuthorityRef? fromJson(dynamic j) =>
      j == null ? null : AuthorityRef(id: j['id'] as int, name: j['name'] as String);
}

class Attachment {
  const Attachment({
    required this.id,
    required this.name,
    required this.contentType,
    required this.size,
    required this.kind,
    required this.downloadUrl,
    required this.createdAt,
  });

  final int id;
  final String name;
  final String contentType;
  final int size;
  final String kind;
  final String downloadUrl;
  final DateTime createdAt;

  bool get isImage => contentType.startsWith('image/');
  bool get isVideo => contentType.startsWith('video/');

  factory Attachment.fromJson(Map<String, dynamic> j) => Attachment(
    id: j['id'] as int,
    name: j['original_name'] as String,
    contentType: j['content_type'] as String,
    size: j['size'] as int,
    kind: j['kind'] as String,
    downloadUrl: j['download_url'] as String,
    createdAt: _date(j['created_at'])!,
  );
}

class CaseSummary {
  const CaseSummary({
    required this.id,
    required this.caseNumber,
    required this.title,
    required this.caseType,
    required this.category,
    required this.priority,
    required this.status,
    required this.statusLabel,
    required this.location,
    required this.createdAt,
    required this.updatedAt,
    this.assignedAuthority,
    this.deadlineAt,
    this.isOverdue = false,
    this.ageDays = 0,
  });

  final int id;
  final String caseNumber;
  final String title;
  final String caseType;
  final Category category;
  final String priority;
  final String status;
  final String statusLabel;
  final String location;
  final AuthorityRef? assignedAuthority;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? deadlineAt;
  final bool isOverdue;
  final int ageDays;

  String get caseTypeLabel => caseType == 'suggestion' ? 'Suggestion' : 'Complaint';

  factory CaseSummary.fromJson(Map<String, dynamic> j) => CaseSummary(
    id: j['id'] as int,
    caseNumber: j['case_number'] as String,
    title: j['title'] as String,
    caseType: j['case_type'] as String,
    category: Category.fromJson(j['category'] as Map<String, dynamic>),
    priority: j['priority'] as String,
    status: j['status'] as String,
    statusLabel: j['status_label'] as String,
    location: j['location'] as String,
    assignedAuthority: AuthorityRef.fromJson(j['assigned_authority']),
    createdAt: _date(j['created_at'])!,
    updatedAt: _date(j['updated_at'])!,
    deadlineAt: _date(j['deadline_at']),
    isOverdue: (j['is_overdue'] as bool?) ?? false,
    ageDays: (j['age_days'] as int?) ?? 0,
  );
}

class Resolution {
  const Resolution({required this.note, required this.resolvedAt, required this.outcome, this.feedback = ''});
  final String note;
  final DateTime resolvedAt;
  final String outcome;
  final String feedback;

  static Resolution? fromJson(dynamic j) => j == null
      ? null
      : Resolution(
          note: j['note'] as String,
          resolvedAt: _date(j['resolved_at'])!,
          outcome: j['outcome'] as String,
          feedback: (j['submitter_feedback'] as String?) ?? '',
        );
}

class AllowedActions {
  const AllowedActions({
    this.transitions = const [],
    this.canVerifyResolution = false,
    this.canReopen = false,
    this.canComment = false,
    this.canAssign = false,
    this.canPostAdminMessage = false,
  });

  final List<String> transitions;
  final bool canVerifyResolution;
  final bool canReopen;
  final bool canComment;

  /// Case administrators: assign or reassign to a resolving department (Member B).
  final bool canAssign;

  /// Admins: post monitoring messages without workflow powers (Member B).
  final bool canPostAdminMessage;

  factory AllowedActions.fromJson(Map<String, dynamic>? j) => j == null
      ? const AllowedActions()
      : AllowedActions(
          transitions: ((j['transitions'] as List?) ?? const []).cast<String>(),
          canVerifyResolution: (j['can_verify_resolution'] as bool?) ?? false,
          canReopen: (j['can_reopen'] as bool?) ?? false,
          canComment: (j['can_comment'] as bool?) ?? false,
          canAssign: (j['can_assign'] as bool?) ?? false,
          canPostAdminMessage: (j['can_post_admin_message'] as bool?) ?? false,
        );
}

class CaseDetail extends CaseSummary {
  const CaseDetail({
    required super.id,
    required super.caseNumber,
    required super.title,
    required super.caseType,
    required super.category,
    required super.priority,
    required super.status,
    required super.statusLabel,
    required super.location,
    required super.createdAt,
    required super.updatedAt,
    super.assignedAuthority,
    super.deadlineAt,
    super.isOverdue,
    super.ageDays,
    required this.description,
    required this.requestedPriority,
    required this.attachments,
    required this.actions,
    this.solvedAt,
    this.closedAt,
    this.verificationDueAt,
    this.reopenCount = 0,
    this.latestResolution,
  });

  final String description;
  final String requestedPriority;
  final List<Attachment> attachments;
  final AllowedActions actions;
  final DateTime? solvedAt;
  final DateTime? closedAt;
  final DateTime? verificationDueAt;
  final int reopenCount;
  final Resolution? latestResolution;

  factory CaseDetail.fromJson(Map<String, dynamic> j) {
    final s = CaseSummary.fromJson(j);
    return CaseDetail(
      id: s.id,
      caseNumber: s.caseNumber,
      title: s.title,
      caseType: s.caseType,
      category: s.category,
      priority: s.priority,
      status: s.status,
      statusLabel: s.statusLabel,
      location: s.location,
      createdAt: s.createdAt,
      updatedAt: s.updatedAt,
      assignedAuthority: s.assignedAuthority,
      deadlineAt: s.deadlineAt,
      isOverdue: s.isOverdue,
      ageDays: s.ageDays,
      description: j['description'] as String,
      requestedPriority: (j['requested_priority'] as String?) ?? s.priority,
      attachments: ((j['attachments'] as List?) ?? const [])
          .map((a) => Attachment.fromJson(a as Map<String, dynamic>))
          .toList(),
      actions: AllowedActions.fromJson(j['allowed_actions'] as Map<String, dynamic>?),
      solvedAt: _date(j['solved_at']),
      closedAt: _date(j['closed_at']),
      verificationDueAt: _date(j['verification_due_at']),
      reopenCount: (j['reopen_count'] as int?) ?? 0,
      latestResolution: Resolution.fromJson(j['latest_resolution']),
    );
  }
}

class TimelineEntry {
  const TimelineEntry({
    required this.type,
    required this.at,
    required this.title,
    required this.body,
    required this.actorName,
    this.toStatus,
    this.attachmentIds = const [],
  });

  final String type;
  final DateTime at;
  final String title;
  final String body;
  final String actorName;
  final String? toStatus;
  final List<int> attachmentIds;

  factory TimelineEntry.fromJson(Map<String, dynamic> j) => TimelineEntry(
    type: j['type'] as String,
    at: _date(j['at'])!,
    title: j['title'] as String,
    body: (j['body'] as String?) ?? '',
    actorName: ((j['actor'] as Map?)?['name'] as String?) ?? 'System',
    toStatus: j['to_status'] as String?,
    attachmentIds: ((j['attachment_ids'] as List?) ?? const []).cast<int>(),
  );
}

class PageResult<T> {
  const PageResult({required this.count, required this.items, required this.hasNext});
  final int count;
  final List<T> items;
  final bool hasNext;
}

class AttachmentLimits {
  const AttachmentLimits({
    required this.allowedExtensions,
    required this.maxImageBytes,
    required this.maxVideoBytes,
    required this.maxPerCase,
  });

  final List<String> allowedExtensions;
  final int maxImageBytes;
  final int maxVideoBytes;
  final int maxPerCase;

  static const imageExtensions = {'jpg', 'jpeg', 'png', 'webp'};

  factory AttachmentLimits.fromJson(Map<String, dynamic> j) => AttachmentLimits(
    allowedExtensions: (j['allowed_extensions'] as List).cast<String>(),
    maxImageBytes: j['max_image_bytes'] as int,
    maxVideoBytes: j['max_video_bytes'] as int,
    maxPerCase: j['max_per_case'] as int,
  );

  /// Client-side pre-check that mirrors the server rules (the server still decides).
  String? validate(String fileName, int size) {
    final ext = fileName.contains('.') ? fileName.split('.').last.toLowerCase() : '';
    if (!allowedExtensions.contains(ext)) {
      return '“$fileName” is not an allowed type. Use ${allowedExtensions.join(', ')}.';
    }
    final limit = imageExtensions.contains(ext) ? maxImageBytes : maxVideoBytes;
    if (size > limit) return '“$fileName” is larger than ${limit ~/ (1024 * 1024)} MB.';
    if (size == 0) return '“$fileName” is empty.';
    return null;
  }
}

class CaseOptions {
  const CaseOptions({required this.attachments, required this.verificationWindowDays});
  final AttachmentLimits attachments;
  final int verificationWindowDays;

  factory CaseOptions.fromJson(Map<String, dynamic> j) => CaseOptions(
    attachments: AttachmentLimits.fromJson(j['attachments'] as Map<String, dynamic>),
    verificationWindowDays: (j['verification_window_days'] as int?) ?? 7,
  );
}

class NewCase {
  const NewCase({
    required this.caseType,
    required this.categoryId,
    required this.title,
    required this.description,
    required this.location,
    required this.priority,
    required this.declarationAccepted,
  });

  final String caseType;
  final int categoryId;
  final String title;
  final String description;
  final String location;
  final String priority;
  final bool declarationAccepted;

  Map<String, String> toFields() => {
    'case_type': caseType,
    'category_id': '$categoryId',
    'title': title,
    'description': description,
    'location': location,
    'requested_priority': priority,
    'declaration_accepted': declarationAccepted ? 'true' : 'false',
  };
}
