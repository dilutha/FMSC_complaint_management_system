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
import 'features/home/home_page.dart';
import 'features/notifications/data/notifications.dart';
import 'features/staff/data/staff_cases.dart';
import 'features/suggestions/data/suggestions.dart';
import 'platform/app_shell.dart';
import 'platform/platform_scope.dart';

void main() {
  final session = PlatformAuthSession(SecureTokenStore());
  if (AppConfig.looksMisconfigured) {
    debugPrint('WARNING: API_BASE_URL uses 10.0.2.2, which only works inside the Android emulator. '
        'Use http://127.0.0.1:8000/api/v1/ for web and desktop.');
  }
  final api = ApiClient(baseUrl: AppConfig.apiBaseUrl, session: session, timeout: AppConfig.requestTimeout);
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
    required this.staffCases,
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
    staffCases: ApiStaffCaseRepository(api),
  );

  final PlatformAuthSession session;
  final AuthRepository auth;
  final CaseRepository caseRepository;
  final NotificationRepository notifications;
  final DashboardRepository dashboard;
  final SuggestionRepository suggestions;
  final AdminRepository admin;
  final StaffCaseRepository staffCases;
  final AttachmentPicker pickAttachments;

  @override
  State<FmscApp> createState() => _FmscAppState();
}

class _FmscAppState extends State<FmscApp> {
  late final UnreadCounter _unread = UnreadCounter(widget.notifications);
  final _navigator = GlobalKey<NavigatorState>();
  SessionState? _lastState;

  /// When the session ends (sign-out or expired token), close every pushed
  /// screen so nothing from the previous user stays visible.
  void _onSession() {
    final state = widget.session.state;
    if (state == SessionState.signedOut && _lastState == SessionState.signedIn) {
      _navigator.currentState?.popUntil((r) => r.isFirst);
    }
    _lastState = state;
  }

  @override
  void initState() {
    super.initState();
    _lastState = widget.session.state;
    widget.session.addListener(_onSession);
    widget.session.revokeOnServer = widget.auth.revoke;
    if (widget.session.state == SessionState.restoring) widget.session.restore(widget.auth.me);
  }

  @override
  void dispose() {
    widget.session.removeListener(_onSession);
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
      staffCases: widget.staffCases,
      child: CaseScope(
        repository: widget.caseRepository,
        pickAttachments: widget.pickAttachments,
        child: MaterialApp(
          navigatorKey: _navigator,
          title: 'FMSC Complaints & Suggestions',
          debugShowCheckedModeBanner: false,
          theme: buildUsjTheme(),
          home: ListenableBuilder(
            listenable: widget.session,
            builder: (context, _) => switch (widget.session.state) {
              SessionState.restoring => const Scaffold(body: LoadingView(message: 'Signing you in…')),
              SessionState.signedIn => AppShell(key: ValueKey(widget.session.user?.id)),
              // Public home page; its Login buttons open the existing sign-in screen.
              SessionState.signedOut => Builder(
                builder: (context) => HomePage(
                  onLogin: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const LoginScreen(), settings: const RouteSettings(name: 'login')),
                  ),
                  // Demo list: opens the same sign-in screen with the account pre-filled.
                  onDemoLogin: (username, password) => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => LoginScreen(initialUsername: username, initialPassword: password),
                      settings: const RouteSettings(name: 'login'),
                    ),
                  ),
                ),
              ),
            },
          ),
        ),
      ),
    );
  }
}
