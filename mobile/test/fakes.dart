import 'package:flutter/material.dart';
import 'package:fmsc_cases/core/api_client.dart';
import 'package:fmsc_cases/design/theme.dart';
import 'package:fmsc_cases/features/cases/case_scope.dart';
import 'package:fmsc_cases/features/cases/data/case_repository.dart';
import 'package:fmsc_cases/features/cases/data/models.dart';

/// Synthetic API payloads in the exact shape the Django API returns.
Map<String, dynamic> caseJson({
  int id = 1,
  String status = 'submitted',
  String statusLabel = 'Submitted',
  String title = 'Projector not working in Hall A',
  Map<String, dynamic>? actions,
  Map<String, dynamic>? resolution,
  List<Map<String, dynamic>> attachments = const [],
}) => {
  'id': id,
  'case_number': 'FMSC-2026-${id.toString().padLeft(5, '0')}',
  'title': title,
  'case_type': 'complaint',
  'category': {'id': 3, 'name': 'Classroom', 'code': 'classroom', 'description': ''},
  'priority': 'urgent',
  'status': status,
  'status_label': statusLabel,
  'location': 'Hall A',
  'assigned_authority': null,
  'created_at': '2026-10-20T09:00:00+05:30',
  'updated_at': '2026-10-21T10:30:00+05:30',
  'deadline_at': null,
  'is_overdue': false,
  'age_days': 7,
  'description': 'The projector does not turn on during lectures.',
  'requested_priority': 'urgent',
  'solved_at': null,
  'closed_at': null,
  'verification_due_at': null,
  'reopen_count': 0,
  'attachments': attachments,
  'latest_resolution': resolution,
  'allowed_actions':
      actions ?? {'transitions': [], 'can_verify_resolution': false, 'can_reopen': false, 'can_comment': true},
};

const optionsJson = {
  'attachments': {
    'allowed_extensions': ['jpeg', 'jpg', 'mov', 'mp4', 'png', 'webm', 'webp'],
    'max_image_bytes': 5 * 1024 * 1024,
    'max_video_bytes': 50 * 1024 * 1024,
    'max_per_case': 10,
  },
  'verification_window_days': 7,
};

class FakeCaseRepository implements CaseRepository {
  final pages = <int, PageResult<CaseSummary>>{};
  Object? listError;
  CaseDetail? detail;
  Object? detailError;
  List<TimelineEntry> timeline = const [];
  List<Category> categories = const [Category(id: 3, name: 'Classroom', code: 'classroom')];
  Object? submitError;
  NewCase? lastSubmitted;
  List<UploadFile>? lastFiles;
  ({bool confirmed, String feedback})? lastVerification;
  String? lastReopenReason;
  int listCalls = 0;

  @override
  Future<PageResult<CaseSummary>> listMyCases({int page = 1, String? statusFilter}) async {
    listCalls++;
    if (listError != null) throw listError!;
    return pages[page] ?? const PageResult(count: 0, items: [], hasNext: false);
  }

  @override
  Future<CaseDetail> getCase(int id) async {
    if (detailError != null) throw detailError!;
    return detail!;
  }

  @override
  Future<List<TimelineEntry>> getTimeline(int id) async => timeline;

  @override
  Future<List<Category>> getCategories() async => categories;

  @override
  Future<CaseOptions> getOptions() async => CaseOptions.fromJson(Map<String, dynamic>.from(optionsJson));

  @override
  Future<CaseDetail> submitCase(NewCase data, List<UploadFile> files) async {
    lastSubmitted = data;
    lastFiles = files;
    if (submitError != null) throw submitError!;
    return CaseDetail.fromJson(caseJson(id: 42, title: data.title));
  }

  @override
  Future<CaseDetail> verifyResolution(int id, {required bool confirmed, String feedback = ''}) async {
    lastVerification = (confirmed: confirmed, feedback: feedback);
    return CaseDetail.fromJson(caseJson(status: confirmed ? 'closed' : 'reopened'));
  }

  @override
  Future<CaseDetail> reopen(int id, String reason) async {
    lastReopenReason = reason;
    return CaseDetail.fromJson(caseJson(status: 'reopened'));
  }

  @override
  Future<void> addComment(int id, String body, {String kind = 'comment'}) async {}

  @override
  Future<List<int>> downloadAttachment(Attachment attachment) async => const [];
}

Widget wrap(Widget child, FakeCaseRepository repo, {AttachmentPicker? picker}) => CaseScope(
  repository: repo,
  pickAttachments: picker ?? ({required List<String> allowedExtensions}) async => const [],
  child: MaterialApp(theme: buildUsjTheme(), home: child),
);
