import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:fmsc_cases/features/cases/data/models.dart';

/// Fixtures are real responses captured from the Django API (synthetic data),
/// so these tests fail if the backend and Flutter models drift apart.
dynamic fixture(String name) => jsonDecode(File('test/fixtures/$name').readAsStringSync());

void main() {
  test('case list page parses', () {
    final json = fixture('case_list.json') as Map<String, dynamic>;
    final items = (json['results'] as List).map((e) => CaseSummary.fromJson(e as Map<String, dynamic>)).toList();
    expect(items, isNotEmpty);
    expect(items.first.caseNumber, matches(RegExp(r'^FMSC-\d{4}-\d{5}$')));
  });

  test('case detail parses, including attachments, resolution and actions', () {
    final c = CaseDetail.fromJson(fixture('case_detail.json') as Map<String, dynamic>);
    expect(c.status, 'reopened');
    expect(c.reopenCount, 1);
    expect(c.attachments.single.isImage, isTrue);
    expect(c.attachments.single.downloadUrl, contains('/download/'));
    expect(c.latestResolution!.outcome, 'disputed');
    expect(c.actions.canComment, isTrue);
  });

  test('timeline parses', () {
    final entries = (fixture('case_timeline.json') as List)
        .map((e) => TimelineEntry.fromJson(e as Map<String, dynamic>))
        .toList();
    expect(entries.where((e) => e.type == 'status_change').map((e) => e.toStatus),
        ['submitted', 'under_review', 'assigned', 'solved', 'reopened']);
  });

  test('options and categories parse', () {
    final options = CaseOptions.fromJson(fixture('case_options.json') as Map<String, dynamic>);
    expect(options.attachments.allowedExtensions, contains('mp4'));
    final categories = (fixture('categories.json') as List).map((e) => Category.fromJson(e as Map<String, dynamic>));
    expect(categories.map((c) => c.code), contains('maintenance'));
  });
}
