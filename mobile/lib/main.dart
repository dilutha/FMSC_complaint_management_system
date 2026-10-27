import 'package:flutter/material.dart';

import 'app/config.dart';
import 'core/api_client.dart';
import 'design/theme.dart';
import 'features/cases/case_routes.dart';
import 'features/cases/case_scope.dart';
import 'features/cases/data/case_repository.dart';
import 'features/cases/platform_attachment_picker.dart';
import 'integration/auth_session.dart';
import 'integration/placeholder_sign_in_screen.dart';

void main() {
  final session = InMemoryAuthSession();
  final api = ApiClient(baseUrl: AppConfig.apiBaseUrl, session: session);
  runApp(FmscCasesApp(session: session, api: api, repository: ApiCaseRepository(api)));
}

/// Standalone shell for the case module. When Member B's app shell is merged,
/// it supplies its own [AuthSession] and navigation and mounts [CaseScope]
/// plus [CaseRoutes] instead of this widget.
class FmscCasesApp extends StatelessWidget {
  const FmscCasesApp({
    super.key,
    required this.session,
    required this.api,
    required this.repository,
    this.pickAttachments = pickAttachmentsFromDevice,
  });

  final AuthSession session;
  final ApiClient api;
  final CaseRepository repository;
  final AttachmentPicker pickAttachments;

  @override
  Widget build(BuildContext context) {
    return CaseScope(
      repository: repository,
      pickAttachments: pickAttachments,
      child: MaterialApp(
        title: 'FMSC Cases',
        debugShowCheckedModeBanner: false,
        theme: buildUsjTheme(),
        home: ListenableBuilder(
          listenable: session,
          builder: (context, _) => switch (session) {
            _ when session.isSignedIn => CaseRoutes.myCases(),
            final InMemoryAuthSession placeholder => PlaceholderSignInScreen(api: api, session: placeholder),
            _ => const Scaffold(body: Center(child: Text('Please sign in.'))),
          },
        ),
      ),
    );
  }
}
