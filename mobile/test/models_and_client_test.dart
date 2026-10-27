import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:fmsc_cases/core/api_client.dart';
import 'package:fmsc_cases/features/cases/data/case_repository.dart';
import 'package:fmsc_cases/features/cases/data/models.dart';
import 'package:fmsc_cases/integration/auth_session.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'fakes.dart';

void main() {
  group('models', () {
    test('CaseDetail parses the API payload', () {
      final c = CaseDetail.fromJson(
        caseJson(
          status: 'solved',
          statusLabel: 'Solved – Awaiting Verification',
          actions: {
            'transitions': ['closed', 'reopened'],
            'can_verify_resolution': true,
            'can_reopen': true,
            'can_comment': true,
          },
          resolution: {
            'id': 1,
            'note': 'Replaced lamp',
            'resolved_at': '2026-10-22T08:00:00Z',
            'outcome': 'pending',
            'submitter_feedback': '',
            'outcome_at': null,
          },
        ),
      );
      expect(c.caseNumber, 'FMSC-2026-00001');
      expect(c.category.name, 'Classroom');
      expect(c.actions.canVerifyResolution, isTrue);
      expect(c.latestResolution!.note, 'Replaced lamp');
      expect(c.caseTypeLabel, 'Complaint');
    });

    test('AttachmentLimits mirrors server rules', () {
      final limits = CaseOptions.fromJson(Map<String, dynamic>.from(optionsJson)).attachments;
      expect(limits.validate('photo.png', 1000), isNull);
      expect(limits.validate('virus.exe', 10), contains('not an allowed type'));
      expect(limits.validate('big.jpg', 6 * 1024 * 1024), contains('larger than 5 MB'));
      expect(limits.validate('clip.mp4', 6 * 1024 * 1024), isNull);
      expect(limits.validate('empty.png', 0), contains('empty'));
    });
  });

  group('ApiClient', () {
    late InMemoryAuthSession session;
    setUp(() {
      session = InMemoryAuthSession()..signIn(token: 'abc123', displayName: 'Test', role: 'student');
    });

    test('sends token and parses paginated cases', () async {
      late http.Request seen;
      final client = MockClient((req) async {
        seen = req;
        return http.Response(
          jsonEncode({
            'count': 1,
            'next': null,
            'previous': null,
            'results': [caseJson()],
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final repo = ApiCaseRepository(
        ApiClient(baseUrl: 'http://api.test/api/v1/', session: session, httpClient: client),
      );
      final page = await repo.listMyCases(statusFilter: 'solved');
      expect(seen.headers['Authorization'], 'Token abc123');
      expect(seen.url.path, '/api/v1/cases/');
      expect(seen.url.queryParameters, containsPair('mine', 'true'));
      expect(seen.url.queryParameters, containsPair('status', 'solved'));
      expect(page.items.single.title, 'Projector not working in Hall A');
      expect(page.hasNext, isFalse);
    });

    test('maps the error envelope to ApiException with field errors', () async {
      final client = MockClient(
        (_) async => http.Response(
          jsonEncode({
            'error': {
              'code': 'validation_error',
              'message': 'Please correct the highlighted fields.',
              'details': {
                'title': ['Ensure this field has at least 5 characters.'],
              },
            },
          }),
          400,
        ),
      );
      final api = ApiClient(baseUrl: 'http://api.test/api/v1/', session: session, httpClient: client);
      await expectLater(
        api.post('cases/', {}),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'validation_error')
              .having((e) => e.fieldError('title'), 'title', contains('at least 5')),
        ),
      );
    });

    test('401 clears the session', () async {
      final client = MockClient(
        (_) async => http.Response('{"error":{"code":"not_authenticated","message":"x","details":{}}}', 401),
      );
      final api = ApiClient(baseUrl: 'http://api.test/', session: session, httpClient: client);
      await expectLater(api.get('cases/'), throwsA(isA<ApiException>()));
      expect(session.isSignedIn, isFalse);
    });

    test('non-JSON server error gives a safe message', () async {
      final client = MockClient((_) async => http.Response('<html>Server Error</html>', 500));
      final api = ApiClient(baseUrl: 'http://api.test/', session: session, httpClient: client);
      await expectLater(
        api.get('cases/'),
        throwsA(isA<ApiException>().having((e) => e.message, 'message', contains('try again later'))),
      );
    });

    test('network failure becomes a retryable ApiException', () async {
      final client = MockClient((_) async => throw http.ClientException('Connection refused'));
      final api = ApiClient(baseUrl: 'http://api.test/', session: session, httpClient: client);
      await expectLater(
        api.get('cases/'),
        throwsA(isA<ApiException>().having((e) => e.isNetwork, 'isNetwork', isTrue)),
      );
    });

    test('multipart submission sends fields and repeated attachment parts', () async {
      late http.Request seen;
      final client = MockClient((req) async {
        seen = req;
        return http.Response(jsonEncode(caseJson(id: 9)), 201);
      });
      final repo = ApiCaseRepository(
        ApiClient(baseUrl: 'http://api.test/api/v1/', session: session, httpClient: client),
      );
      await repo.submitCase(
        const NewCase(
          caseType: 'complaint',
          categoryId: 3,
          title: 'Broken chair',
          description: 'Chair leg is broken.',
          location: 'Room 1',
          priority: 'normal',
          declarationAccepted: true,
        ),
        [
          UploadFile(name: 'a.png', bytes: [1, 2]),
          UploadFile(name: 'b.png', bytes: [3]),
        ],
      );
      final body = utf8.decode(seen.bodyBytes, allowMalformed: true);
      expect(seen.headers['content-type'], startsWith('multipart/form-data'));
      expect('name="attachments"'.allMatches(body).length, 2);
      expect(body, contains('name="declaration_accepted"'));
    });
  });
}
