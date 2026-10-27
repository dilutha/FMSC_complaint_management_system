import '../../../core/api_client.dart';
import 'models.dart';

/// All case API calls used by the Flutter screens. Screens depend on this
/// interface so they can be tested with a fake.
abstract class CaseRepository {
  Future<PageResult<CaseSummary>> listMyCases({int page = 1, String? statusFilter});
  Future<CaseDetail> getCase(int id);
  Future<List<TimelineEntry>> getTimeline(int id);
  Future<List<Category>> getCategories();
  Future<CaseOptions> getOptions();
  Future<CaseDetail> submitCase(NewCase data, List<UploadFile> files);
  Future<CaseDetail> verifyResolution(int id, {required bool confirmed, String feedback = ''});
  Future<CaseDetail> reopen(int id, String reason);
  Future<void> addComment(int id, String body, {String kind = 'comment'});
  Future<List<int>> downloadAttachment(Attachment attachment);
}

class ApiCaseRepository implements CaseRepository {
  ApiCaseRepository(this._api);
  final ApiClient _api;
  CaseOptions? _options;

  @override
  Future<PageResult<CaseSummary>> listMyCases({int page = 1, String? statusFilter}) async {
    final json =
        await _api.get(
              'cases/',
              query: {
                'mine': 'true',
                'page': '$page',
                'page_size': '20',
                if (statusFilter != null && statusFilter.isNotEmpty) 'status': statusFilter,
              },
            )
            as Map<String, dynamic>;
    return PageResult(
      count: json['count'] as int,
      hasNext: json['next'] != null,
      items: (json['results'] as List).map((e) => CaseSummary.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }

  @override
  Future<CaseDetail> getCase(int id) async => CaseDetail.fromJson(await _api.get('cases/$id/') as Map<String, dynamic>);

  @override
  Future<List<TimelineEntry>> getTimeline(int id) async => ((await _api.get('cases/$id/timeline/')) as List)
      .map((e) => TimelineEntry.fromJson(e as Map<String, dynamic>))
      .toList();

  @override
  Future<List<Category>> getCategories() async =>
      ((await _api.get('categories/')) as List).map((e) => Category.fromJson(e as Map<String, dynamic>)).toList();

  @override
  Future<CaseOptions> getOptions() async =>
      _options ??= CaseOptions.fromJson(await _api.get('case-options/') as Map<String, dynamic>);

  @override
  Future<CaseDetail> submitCase(NewCase data, List<UploadFile> files) async {
    final json = await _api.postMultipart('cases/', data.toFields(), 'attachments', files);
    return CaseDetail.fromJson(json as Map<String, dynamic>);
  }

  @override
  Future<CaseDetail> verifyResolution(int id, {required bool confirmed, String feedback = ''}) async =>
      CaseDetail.fromJson(
        await _api.post('cases/$id/verify-resolution/', {'confirmed': confirmed, 'feedback': feedback})
            as Map<String, dynamic>,
      );

  @override
  Future<CaseDetail> reopen(int id, String reason) async =>
      CaseDetail.fromJson(await _api.post('cases/$id/reopen/', {'reason': reason}) as Map<String, dynamic>);

  @override
  Future<void> addComment(int id, String body, {String kind = 'comment'}) =>
      _api.post('cases/$id/updates/', {'body': body, 'kind': kind});

  @override
  Future<List<int>> downloadAttachment(Attachment attachment) => _api.getBytes(attachment.downloadUrl);
}
