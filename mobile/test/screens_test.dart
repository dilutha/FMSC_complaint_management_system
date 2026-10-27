import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fmsc_cases/core/api_client.dart';
import 'package:fmsc_cases/design/widgets.dart';
import 'package:fmsc_cases/features/cases/data/models.dart';
import 'package:fmsc_cases/features/cases/presentation/case_detail_screen.dart';
import 'package:fmsc_cases/features/cases/presentation/my_cases_screen.dart';
import 'package:fmsc_cases/features/cases/presentation/submission_confirmation_screen.dart';
import 'package:fmsc_cases/features/cases/presentation/submit_case_screen.dart';

import 'fakes.dart';

CaseSummary summary(int id, {String status = 'submitted', String label = 'Submitted'}) =>
    CaseSummary.fromJson(caseJson(id: id, status: status, statusLabel: label, title: 'Case number $id'));

void main() {
  group('MyCasesScreen', () {
    testWidgets('shows cases with text status labels', (tester) async {
      final repo = FakeCaseRepository()
        ..pages[1] = PageResult(
          count: 2,
          hasNext: false,
          items: [
            summary(1),
            summary(2, status: 'solved', label: 'Solved'),
          ],
        );
      await tester.pumpWidget(wrap(const MyCasesScreen(), repo));
      expect(find.text('Loading your cases…'), findsOneWidget);
      await tester.pumpAndSettle();
      expect(find.text('Case number 1'), findsOneWidget);
      expect(find.text('Solved – please confirm'), findsOneWidget);
      expect(find.text('2 cases'), findsOneWidget);
    });

    testWidgets('empty state offers submission', (tester) async {
      await tester.pumpWidget(wrap(const MyCasesScreen(), FakeCaseRepository()));
      await tester.pumpAndSettle();
      expect(find.text('You have not submitted any cases yet'), findsOneWidget);
      expect(find.text('Submit a case'), findsOneWidget);
    });

    testWidgets('error state retries', (tester) async {
      final repo = FakeCaseRepository()
        ..listError = ApiException(statusCode: 0, code: 'network', message: 'No connection to the server.');
      await tester.pumpWidget(wrap(const MyCasesScreen(), repo));
      await tester.pumpAndSettle();
      expect(find.text('No connection to the server.'), findsOneWidget);
      repo
        ..listError = null
        ..pages[1] = PageResult(count: 1, hasNext: false, items: [summary(5)]);
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Case number 5'), findsOneWidget);
    });

    testWidgets('loads the next page when scrolled', (tester) async {
      final repo = FakeCaseRepository()
        ..pages[1] = PageResult(count: 25, hasNext: true, items: [for (var i = 1; i <= 20; i++) summary(i)])
        ..pages[2] = PageResult(count: 25, hasNext: false, items: [for (var i = 21; i <= 25; i++) summary(i)]);
      await tester.pumpWidget(wrap(const MyCasesScreen(), repo));
      await tester.pumpAndSettle();
      await tester.dragUntilVisible(find.text('Case number 25'), find.byType(ListView), const Offset(0, -400));
      expect(find.text('Case number 25'), findsOneWidget);
      expect(repo.listCalls, 2);
    });
  });

  group('SubmitCaseScreen', () {
    testWidgets('validates required fields and declaration', (tester) async {
      final repo = FakeCaseRepository();
      await tester.pumpWidget(wrap(const SubmitCaseScreen(), repo));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Submit case'), 300, scrollable: find.byType(Scrollable).first);
      await tester.tap(find.text('Submit case'));
      await tester.pumpAndSettle();
      expect(find.text('Choose a category.'), findsOneWidget);
      expect(find.text('Please confirm the declaration to submit.'), findsOneWidget);
      expect(repo.lastSubmitted, isNull);
    });

    testWidgets('submits and shows the reference number', (tester) async {
      final repo = FakeCaseRepository();
      await tester.pumpWidget(wrap(const SubmitCaseScreen(), repo));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Urgent'));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<int>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Classroom').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextFormField, 'Location *'), 'Hall A');
      await tester.enterText(find.widgetWithText(TextFormField, 'Title *'), 'Projector broken');
      await tester.enterText(find.widgetWithText(TextFormField, 'Description *'), 'It will not turn on at all.');
      await tester.scrollUntilVisible(find.byType(CheckboxListTile), 300, scrollable: find.byType(Scrollable).first);
      await tester.tap(find.byType(CheckboxListTile));
      await tester.scrollUntilVisible(find.text('Submit case'), 300, scrollable: find.byType(Scrollable).first);
      await tester.tap(find.text('Submit case'));
      await tester.pumpAndSettle();

      expect(repo.lastSubmitted!.priority, 'urgent');
      expect(repo.lastSubmitted!.categoryId, 3);
      expect(find.byType(SubmissionConfirmationScreen), findsOneWidget);
      expect(find.text('FMSC-2026-00042'), findsOneWidget);
    });

    testWidgets('shows server-side field errors', (tester) async {
      final repo = FakeCaseRepository()
        ..submitError = ApiException(
          statusCode: 400,
          code: 'validation_error',
          message: 'Please correct the highlighted fields.',
          details: {
            'title': ['Title is not allowed.'],
          },
        );
      await tester.pumpWidget(wrap(const SubmitCaseScreen(), repo));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<int>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Classroom').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextFormField, 'Location *'), 'Hall A');
      await tester.enterText(find.widgetWithText(TextFormField, 'Title *'), 'Projector broken');
      await tester.enterText(find.widgetWithText(TextFormField, 'Description *'), 'It will not turn on at all.');
      await tester.scrollUntilVisible(find.byType(CheckboxListTile), 300, scrollable: find.byType(Scrollable).first);
      await tester.tap(find.byType(CheckboxListTile));
      await tester.scrollUntilVisible(find.text('Submit case'), 300, scrollable: find.byType(Scrollable).first);
      await tester.tap(find.text('Submit case'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Title is not allowed.'),
        -300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Title is not allowed.'), findsOneWidget);
    });

    testWidgets('rejects disallowed attachments before upload', (tester) async {
      final repo = FakeCaseRepository();
      await tester.pumpWidget(
        wrap(
          const SubmitCaseScreen(),
          repo,
          picker: ({required List<String> allowedExtensions}) async => [
            UploadFile(name: 'ok.png', bytes: [1]),
            UploadFile(name: 'bad.exe', bytes: [1]),
          ],
        ),
      );
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Add photo or video'), 300, scrollable: find.byType(Scrollable).first);
      await tester.tap(find.text('Add photo or video'));
      await tester.pumpAndSettle();
      expect(find.text('ok.png'), findsOneWidget);
      expect(find.textContaining('“bad.exe” is not an allowed type'), findsOneWidget);
    });
  });

  group('CaseDetailScreen', () {
    testWidgets('shows timeline and verification prompt for solved cases', (tester) async {
      final repo = FakeCaseRepository()
        ..detail = CaseDetail.fromJson(
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
              'note': 'Replaced the projector lamp.',
              'resolved_at': '2026-10-22T08:00:00Z',
              'outcome': 'pending',
              'submitter_feedback': '',
              'outcome_at': null,
            },
          ),
        )
        ..timeline = [
          TimelineEntry(
            type: 'status_change',
            at: DateTime(2026, 10, 20),
            title: 'Submitted',
            body: 'Case submitted.',
            actorName: 'You',
          ),
          TimelineEntry(
            type: 'status_change',
            at: DateTime(2026, 10, 22),
            title: 'Solved – Awaiting Verification',
            body: 'Replaced the projector lamp.',
            actorName: 'Responsible authority',
          ),
        ];
      await tester.pumpWidget(wrap(const CaseDetailScreen(caseId: 1), repo));
      await tester.pumpAndSettle();
      expect(find.text('Is the issue resolved?'), findsOneWidget);

      await tester.tap(find.text('Respond'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('No, the problem persists'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Submit response'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Tell us what is still wrong'), findsOneWidget);
      await tester.enterText(find.byType(TextField), 'Still flickering');
      await tester.tap(find.text('Submit response'));
      await tester.pumpAndSettle();
      expect(repo.lastVerification, (confirmed: false, feedback: 'Still flickering'));

      await tester.scrollUntilVisible(find.text('Progress'), 300, scrollable: find.byType(Scrollable).first);
      expect(find.text('Submitted'), findsWidgets);
    });

    testWidgets('closed case offers reopening with required reason', (tester) async {
      final repo = FakeCaseRepository()
        ..detail = CaseDetail.fromJson(
          caseJson(
            status: 'closed',
            statusLabel: 'Closed',
            actions: {
              'transitions': ['reopened'],
              'can_verify_resolution': false,
              'can_reopen': true,
              'can_comment': false,
            },
          ),
        );
      await tester.pumpWidget(wrap(const CaseDetailScreen(caseId: 1), repo));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Problem returned? Reopen case'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Problem returned? Reopen case'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Reopen case'));
      await tester.pumpAndSettle();
      expect(find.text('Please explain why (at least 5 characters).'), findsOneWidget);
      await tester.enterText(find.byType(TextFormField), 'The leak is back again');
      await tester.tap(find.text('Reopen case'));
      await tester.pumpAndSettle();
      expect(repo.lastReopenReason, 'The leak is back again');
    });

    testWidgets('404 shows not found state', (tester) async {
      final repo = FakeCaseRepository()
        ..detailError = ApiException(statusCode: 404, code: 'not_found', message: 'Not found.');
      await tester.pumpWidget(wrap(const CaseDetailScreen(caseId: 99), repo));
      await tester.pumpAndSettle();
      expect(find.text('Case not found'), findsOneWidget);
    });
  });

  testWidgets('status badge exposes a text label for accessibility', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: StatusBadge(status: 'rejected', label: 'Rejected'),
        ),
      ),
    );
    expect(find.text('Rejected'), findsOneWidget);
    expect(find.bySemanticsLabel('Status: Rejected'), findsOneWidget);
  });
}
