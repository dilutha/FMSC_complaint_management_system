import 'package:flutter/material.dart';

import 'app/config.dart';
import 'core/api_client.dart';
import 'design/theme.dart';
import 'design/widgets.dart';
import 'features/admin/data/admin.dart';
import 'features/auth/data/auth_repository.dart';
import 'features/auth/data/platform_auth_session.dart';
import 'features/auth/data/token_store.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/cases/case_scope.dart';
import 'features/cases/data/case_repository.dart';
import 'features/cases/platform_attachment_picker.dart';
import 'features/dashboard/data/dashboard.dart';
import 'features/notifications/data/notifications.dart';
import 'features/suggestions/data/suggestions.dart';
import 'platform/app_shell.dart';
import 'platform/platform_scope.dart';

void main() {
  final session = PlatformAuthSession(SecureTokenStore());
  final api = ApiClient(baseUrl: AppConfig.apiBaseUrl, session: session);
  runApp(FmscApp.fromApi(session: session, api: api));
}

/// The integrated app: authentication, the role-based shell and both
/// members' modules (CaseScope for cases, PlatformScope for platform features).
class FmscApp extends StatefulWidget {
  const FmscApp({
    super.key,
    required this.session,
    required this.auth,
    required this.caseRepository,
    required this.notifications,
    required this.dashboard,
    required this.suggestions,
    required this.admin,
    this.pickAttachments = pickAttachmentsFromDevice,
  });

  factory FmscApp.fromApi({required PlatformAuthSession session, required ApiClient api}) => FmscApp(
    session: session,
    auth: ApiAuthRepository(api),
    caseRepository: ApiCaseRepository(api),
    notifications: ApiNotificationRepository(api),
    dashboard: ApiDashboardRepository(api),
    suggestions: ApiSuggestionRepository(api),
    admin: ApiAdminRepository(api),
  );

  final PlatformAuthSession session;
  final AuthRepository auth;
  final CaseRepository caseRepository;
  final NotificationRepository notifications;
  final DashboardRepository dashboard;
  final SuggestionRepository suggestions;
  final AdminRepository admin;
  final AttachmentPicker pickAttachments;

  @override
  State<FmscApp> createState() => _FmscAppState();
}

class _FmscAppState extends State<FmscApp> {
  late final UnreadCounter _unread = UnreadCounter(widget.notifications);

  @override
  void initState() {
    super.initState();
    widget.session.revokeOnServer = widget.auth.revoke;
    if (widget.session.state == SessionState.restoring) widget.session.restore(widget.auth.me);
  }

  @override
  void dispose() {
    _unread.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PlatformScope(
      session: widget.session,
      auth: widget.auth,
      notifications: widget.notifications,
      unread: _unread,
      dashboard: widget.dashboard,
      suggestions: widget.suggestions,
      admin: widget.admin,
      child: CaseScope(
        repository: widget.caseRepository,
        pickAttachments: widget.pickAttachments,
        child: MaterialApp(
          title: 'FMSC Complaints & Suggestions',
          debugShowCheckedModeBanner: false,
          theme: buildUsjTheme(),
          home: ListenableBuilder(
            listenable: widget.session,
            builder: (context, _) => switch (widget.session.state) {
              SessionState.restoring => const Scaffold(body: LoadingView(message: 'Signing you in…')),
              SessionState.signedIn => AppShell(key: ValueKey(widget.session.user?.id)),
              SessionState.signedOut => const LoginScreen(),
            },
          ),
        ),
      ),
    );
  }
}
