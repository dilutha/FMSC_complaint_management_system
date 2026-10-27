import 'package:flutter/material.dart';

import 'presentation/case_detail_screen.dart';
import 'presentation/my_cases_screen.dart';
import 'presentation/submit_case_screen.dart';

/// SHARED CONTRACT with Member B (navigation): entry points the app shell,
/// home screen and notification taps use to open case screens.
abstract final class CaseRoutes {
  static Widget myCases() => const MyCasesScreen();

  static Future<void> openSubmit(BuildContext context) =>
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SubmitCaseScreen()));

  /// Open a case by id, e.g. from a "case solved" notification.
  static Future<void> openCase(BuildContext context, int caseId) =>
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => CaseDetailScreen(caseId: caseId)));
}
