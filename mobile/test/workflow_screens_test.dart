import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fmsc_cases/features/cases/data/models.dart';
import 'package:fmsc_cases/features/cases/presentation/case_detail_screen.dart';
import 'package:fmsc_cases/features/cases/presentation/submit_case_screen.dart';
import 'package:fmsc_cases/features/dashboard/presentation/role_dashboard_screen.dart';
import 'package:fmsc_cases/features/auth/presentation/login_screen.dart';
import 'package:fmsc_cases/features/home/demo_accounts.dart';
import 'package:fmsc_cases/features/home/home_page.dart';
import 'package:fmsc_cases/main.dart';
import 'package:fmsc_cases/platform/app_shell.dart';
import 'package:fmsc_cases/features/staff/presentation/staff_cases_screen.dart';

import 'platform_fakes.dart';

Future<void> bigScreen(WidgetTester tester, {Size size = const Size(1280, 2400)}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

/// The "Sign in as this user" button on the demo card for [username].
Finder demoSignIn(String username) => find.descendant(
  of: find.ancestor(of: find.text(username), matching: find.byType(Column)).first,
  matching: find.text('Sign in as this user'),
);

void main() {
  group('Public home page', () {
    Widget page({VoidCallback? onLogin, VoidCallback? onDashboard}) =>
        MaterialApp(home: HomePage(onLogin: onLogin ?? () {}, onDashboard: onDashboard));

    testWidgets('shows every section without signing in', (tester) async {
      await bigScreen(tester);
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      for (final text in [
        "Your Voice Matters. Let's Improve Our Faculty Together.",
        'About the System',
        'How It Works',
        'Who Uses the System',
        'Resolving Departments',
        'Why Use It',
        'Frequently Asked Questions',
        'Have a Concern or an Idea to Share?',
        'University of Sri Jayewardenepura',
      ]) {
        expect(find.text(text), findsWidgets, reason: text);
      }
      for (final dept in ['IT Department', 'Maintenance Department', 'Examination Unit', "Dean's Office"]) {
        expect(find.text(dept), findsWidgets); // department card (and demo account card in debug builds)
      }
      for (final group in ['Complainers', 'Admins', 'Case Administrators', 'Resolving Departments']) {
        expect(find.text(group), findsWidgets);
      }
    });

    testWidgets('every Login button opens sign-in', (tester) async {
      await bigScreen(tester);
      var logins = 0;
      await tester.pumpWidget(page(onLogin: () => logins++));
      await tester.pumpAndSettle();
      final buttons = [find.text('Login').first, find.text('Login to Get Started'), find.text('Login').last];
      for (final b in buttons) {
        await tester.ensureVisible(b);
        await tester.pumpAndSettle();
        await tester.tap(b);
      }
      expect(logins, 3);
    });

    testWidgets('"Explore How It Works" scrolls to the workflow', (tester) async {
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      final step = find.text('A case administrator reviews it');
      final before = tester.getTopLeft(step).dy;
      await tester.tap(find.text('Explore How It Works'));
      await tester.pumpAndSettle();
      expect(tester.getTopLeft(step).dy, lessThan(before));
      expect(tester.getTopLeft(find.text('How It Works').first).dy, lessThan(600));
    });

    testWidgets('FAQ answers expand and match the real rules', (tester) async {
      await bigScreen(tester);
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      final question = find.text("Can I see another person's complaint?");
      await tester.ensureVisible(question);
      await tester.tap(question);
      await tester.pumpAndSettle();
      expect(find.textContaining('You can only see what you submitted'), findsOneWidget);
    });

    testWidgets('narrow screens use a menu', (tester) async {
      await bigScreen(tester, size: const Size(390, 844));
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Menu'));
      await tester.pumpAndSettle();
      expect(find.text('User Groups'), findsWidgets);
      expect(find.text('FAQ'), findsWidgets);
    });

    testWidgets('signed-in users see a dashboard action instead of Login', (tester) async {
      await bigScreen(tester);
      var dash = 0;
      await tester.pumpWidget(page(onDashboard: () => dash++));
      await tester.pumpAndSettle();
      expect(find.text('Login'), findsNothing);
      await tester.tap(find.text('Go to my dashboard').first);
      expect(dash, 1);
    });

    testWidgets('renders immediately with reduced motion', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(disableAnimations: true, size: Size(800, 600)),
          child: HomePage(onLogin: () {}),
        ),
      ));
      await tester.pump();
      final opacity = tester.widgetList<AnimatedOpacity>(find.byType(AnimatedOpacity)).first;
      expect(opacity.opacity, 1);
    });
  });

  group('Demo accounts on the home page', () {
    testWidgets('lists every demo user with the shared password', (tester) async {
      await bigScreen(tester, size: const Size(1280, 4000));
      await tester.pumpWidget(MaterialApp(home: HomePage(onLogin: () {}, showDemoAccounts: true)));
      await tester.pumpAndSettle();
      expect(find.text('Try the System with Demo Accounts'), findsOneWidget);
      for (final a in demoAccounts) {
        expect(find.text(a.username), findsOneWidget, reason: a.username);
      }
      expect(demoAccounts.map((a) => a.username).toSet(), {
        'demo_student', 'demo_lecturer', 'demo_non_academic', 'demo_system_admin', 'demo_case_admin',
        'demo_it', 'demo_maintenance', 'demo_exams', 'demo_deans_office', 'demo_management',
      });
      expect(find.text(demoPassword), findsOneWidget);
      expect(find.textContaining('Never use this password for a real account'), findsOneWidget);
    });

    testWidgets('"Sign in as this user" passes the account to sign-in', (tester) async {
      await bigScreen(tester, size: const Size(1280, 4000));
      String? user;
      String? pass;
      await tester.pumpWidget(MaterialApp(
        home: HomePage(onLogin: () {}, showDemoAccounts: true, onDemoLogin: (u, p) {
          user = u;
          pass = p;
        }),
      ));
      await tester.pumpAndSettle();
      await tester.ensureVisible(demoSignIn('demo_case_admin'));
      await tester.tap(demoSignIn('demo_case_admin'));
      expect((user, pass), ('demo_case_admin', 'Password@123'));
    });

    testWidgets('hidden when disabled and for signed-in users', (tester) async {
      await bigScreen(tester, size: const Size(1440, 4000));
      await tester.pumpWidget(MaterialApp(home: HomePage(onLogin: () {}, showDemoAccounts: false)));
      await tester.pumpAndSettle();
      expect(find.text('Try the System with Demo Accounts'), findsNothing);
      expect(find.text(demoPassword), findsNothing);
      expect(find.text('Demo Accounts'), findsNothing); // no nav link either
      await tester.pumpWidget(MaterialApp(home: HomePage(onLogin: () {}, onDashboard: () {}, showDemoAccounts: true)));
      await tester.pumpAndSettle();
      expect(find.text(demoPassword), findsNothing);
    });

    testWidgets('full app: demo card pre-fills sign-in and lands on the dashboard', (tester) async {
      await bigScreen(tester, size: const Size(1280, 5000));
      final h = PlatformHarness()..auth.signInResult = (token: 'tok', user: userFromFixture('complainer'));
      h.session.restore(() async => throw apiError(401, 'no token'));
      await tester.pumpWidget(FmscApp(
        session: h.session, auth: h.auth, caseRepository: h.cases, notifications: h.notifications,
        dashboard: h.dashboard, suggestions: h.suggestions, admin: h.admin, staffCases: h.staffCases,
        pickAttachments: ({required List<String> allowedExtensions}) async => const [],
      ));
      await tester.pumpAndSettle();
      await tester.ensureVisible(demoSignIn('demo_student'));
      await tester.pumpAndSettle();
      await tester.tap(demoSignIn('demo_student'));
      await tester.pumpAndSettle();
      expect(find.byType(LoginScreen), findsOneWidget);
      final fields = tester.widgetList<EditableText>(find.byType(EditableText)).map((e) => e.controller.text).toList();
      expect(fields, containsAll(['demo_student', 'Password@123']));
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.pumpAndSettle();
      expect(find.byType(AppShell), findsOneWidget);
      expect(find.text('Student dashboard'), findsOneWidget);
    });
  });

  group('Role dashboards', () {
    Future<PlatformHarness> show(WidgetTester tester, String workspace) async {
      await bigScreen(tester);
      final h = PlatformHarness(user: userFromFixture(workspace))..dashboard.overviewWorkspace = workspace;
      await tester.pumpWidget(h.wrap(const RoleDashboardScreen()));
      await tester.pumpAndSettle();
      return h;
    }

    testWidgets('complainer dashboard shows own counts and both submit actions', (tester) async {
      await show(tester, 'complainer');
      expect(find.text('Student dashboard'), findsOneWidget);
      expect(find.text('Submitted by me'), findsOneWidget);
      expect(find.text('Submit complaint'), findsOneWidget);
      await tester.tap(find.text('Submit suggestion'));
      await tester.pumpAndSettle();
      final screen = tester.widget<SubmitCaseScreen>(find.byType(SubmitCaseScreen));
      expect(screen.initialType, 'suggestion');
    });

    testWidgets('case administrator sees the review queue', (tester) async {
      await show(tester, 'case_admin');
      expect(find.text('Case administrator dashboard'), findsOneWidget);
      expect(find.text('Awaiting review (urgent first)'), findsOneWidget);
      expect(find.widgetWithText(OutlinedButton, 'Review'), findsWidgets);
      expect(find.text('Department workload (active cases)'), findsOneWidget);
    });

    testWidgets('admin dashboard is faculty-wide with recent activity', (tester) async {
      await show(tester, 'admin');
      expect(find.text('Admin dashboard'), findsOneWidget);
      expect(find.text('Recent case activity'), findsOneWidget);
      await tester.scrollUntilVisible(find.text('Reports and analytics'), 400, scrollable: find.byType(Scrollable).first);
      expect(find.text('Reports and analytics'), findsOneWidget);
      expect(find.text('Submit complaint'), findsNothing);
    });

    testWidgets('department dashboard names its own department', (tester) async {
      await show(tester, 'department');
      expect(find.text('IT Department dashboard'), findsOneWidget);
      expect(find.text('Assigned to us'), findsOneWidget);
      expect(find.text('Department workload (active cases)'), findsNothing);
    });

    testWidgets('error state retries', (tester) async {
      await bigScreen(tester);
      final h = PlatformHarness(user: userFromFixture('complainer'))..dashboard.error = apiError(0, 'No connection.');
      await tester.pumpWidget(h.wrap(const RoleDashboardScreen()));
      await tester.pumpAndSettle();
      expect(find.text('No connection.'), findsOneWidget);
      h.dashboard.error = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Submitted by me'), findsOneWidget);
    });
  });

  group('Case actions inside the case-detail screen', () {
    Future<PlatformHarness> open(WidgetTester tester, String workspace, String detailFixture) async {
      await bigScreen(tester, size: const Size(1000, 3000));
      final h = PlatformHarness(user: userFromFixture(workspace));
      h.cases.detail = CaseDetail.fromJson(fixture(detailFixture));
      await tester.pumpWidget(h.wrap(CaseDetailScreen(caseId: h.cases.detail!.id)));
      await tester.pumpAndSettle();
      return h;
    }

    testWidgets('case administrator assigns with a required message', (tester) async {
      final h = await open(tester, 'case_admin', 'case_detail_case_admin.json');
      expect(find.text('Case actions'), findsOneWidget);
      await tester.tap(find.text('Assign to a department'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Assign case'));
      await tester.pumpAndSettle();
      expect(find.text('Choose the department that will resolve this case.'), findsOneWidget);
      expect(find.text('An assignment message is required.'), findsOneWidget);
      expect(h.staffCases.calls, isEmpty);

      await tester.tap(find.byType(DropdownButtonFormField<int>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('IT Department').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextFormField, 'Assignment message'), 'Network faults go to IT.');
      await tester.tap(find.widgetWithText(FilledButton, 'Assign case'));
      await tester.pumpAndSettle();
      expect(h.staffCases.calls.single, startsWith('assign:${h.cases.detail!.id}:'));
      expect(h.staffCases.calls.single, endsWith(':Network faults go to IT.'));
      expect(find.text('Case assigned. The department can now see it.'), findsOneWidget);
    });

    testWidgets('a status change needs a message', (tester) async {
      final h = await open(tester, 'case_admin', 'case_detail_case_admin.json');
      await tester.tap(find.text('Update status'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Save update'));
      await tester.pumpAndSettle();
      expect(find.text('A message is required for every status change.'), findsOneWidget);
      await tester.enterText(find.widgetWithText(TextFormField, 'Message explaining this update'), 'Hi');
      await tester.tap(find.widgetWithText(FilledButton, 'Save update'));
      await tester.pumpAndSettle();
      expect(find.text('Enter at least 5 characters.'), findsOneWidget);
      await tester.enterText(
          find.widgetWithText(TextFormField, 'Message explaining this update'), 'Reviewing the report now.');
      await tester.tap(find.widgetWithText(FilledButton, 'Save update'));
      await tester.pumpAndSettle();
      expect(h.staffCases.calls.single, 'status:${h.cases.detail!.id}:under_review:Reviewing the report now.:');
    });

    testWidgets('department records a resolution but cannot assign', (tester) async {
      final h = await open(tester, 'department', 'case_detail_department.json');
      expect(find.text('Assign to a department'), findsNothing);
      expect(find.textContaining('Reassign'), findsNothing);
      await tester.tap(find.text('Update status'));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Resolved (record resolution)').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextFormField, 'Resolution details'), 'Too short');
      await tester.tap(find.widgetWithText(FilledButton, 'Save update'));
      await tester.pumpAndSettle();
      expect(find.text('Enter at least 10 characters.'), findsOneWidget);
      await tester.enterText(find.widgetWithText(TextFormField, 'Resolution details'), 'Results were republished.');
      await tester.tap(find.widgetWithText(FilledButton, 'Save update'));
      await tester.pumpAndSettle();
      expect(h.staffCases.calls.single, 'status:${h.cases.detail!.id}:solved::Results were republished.');
    });

    testWidgets('server errors are shown under the field', (tester) async {
      final h = await open(tester, 'case_admin', 'case_detail_case_admin.json');
      h.staffCases.actionError = apiError(400, 'Please correct the highlighted fields.', {
        'reason': ['Explain this status change.'],
      });
      await tester.tap(find.text('Update status'));
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextFormField, 'Message explaining this update'), 'Valid message');
      await tester.tap(find.widgetWithText(FilledButton, 'Save update'));
      await tester.pumpAndSettle();
      expect(find.text('Explain this status change.'), findsOneWidget);
      expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Save update')).onPressed, isNotNull);
    });

    testWidgets('complainers never see staff actions', (tester) async {
      await open(tester, 'complainer', 'case_detail_case_admin.json');
      expect(find.text('Case actions'), findsNothing);
    });
  });

  group('Responsive layout (no overflow)', () {
    for (final width in [360.0, 768.0, 1024.0, 1440.0]) {
      testWidgets('home page at ${width.toInt()} px', (tester) async {
        await bigScreen(tester, size: Size(width, 900));
        await tester.pumpWidget(MaterialApp(home: HomePage(onLogin: () {})));
        await tester.pumpAndSettle();
        await tester.drag(find.byType(SingleChildScrollView), const Offset(0, -6000));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      });
      for (final workspace in ['complainer', 'case_admin', 'admin', 'department']) {
        testWidgets('$workspace dashboard at ${width.toInt()} px', (tester) async {
          await bigScreen(tester, size: Size(width, 900));
          final h = PlatformHarness(user: userFromFixture(workspace))..dashboard.overviewWorkspace = workspace;
          await tester.pumpWidget(h.wrap(const RoleDashboardScreen()));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
        });
      }
    }
  });

  testWidgets('staff case list filters by status', (tester) async {
    await bigScreen(tester);
    final h = PlatformHarness(user: userFromFixture('case_admin'));
    await tester.pumpWidget(h.wrap(const StaffCasesScreen()));
    await tester.pumpAndSettle();
    expect(find.text('All cases'), findsOneWidget);
    expect(find.textContaining('FMSC-2026-'), findsWidgets);
    await tester.tap(find.widgetWithText(ChoiceChip, 'Awaiting review'));
    await tester.pumpAndSettle();
    expect(h.staffCases.lastFilter?.statuses, 'submitted,under_review,reopened');
    expect(find.text('Complainant type'), findsOneWidget);
  });
}
