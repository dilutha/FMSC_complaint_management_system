import 'package:flutter/widgets.dart';

import '../features/admin/data/admin.dart';
import '../features/auth/data/auth_repository.dart';
import '../features/auth/data/platform_auth_session.dart';
import '../features/dashboard/data/dashboard.dart';
import '../features/notifications/data/notifications.dart';
import '../features/suggestions/data/suggestions.dart';

/// Provides platform (Member B) dependencies to every platform screen.
/// The case module keeps its own CaseScope.
class PlatformScope extends InheritedWidget {
  const PlatformScope({
    super.key,
    required this.session,
    required this.auth,
    required this.notifications,
    required this.unread,
    required this.dashboard,
    required this.suggestions,
    required this.admin,
    required super.child,
  });

  final PlatformAuthSession session;
  final AuthRepository auth;
  final NotificationRepository notifications;
  final UnreadCounter unread;
  final DashboardRepository dashboard;
  final SuggestionRepository suggestions;
  final AdminRepository admin;

  static PlatformScope of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<PlatformScope>();
    assert(scope != null, 'PlatformScope not found. Wrap the app in PlatformScope.');
    return scope!;
  }

  @override
  bool updateShouldNotify(PlatformScope old) =>
      session != old.session ||
      auth != old.auth ||
      notifications != old.notifications ||
      dashboard != old.dashboard ||
      suggestions != old.suggestions ||
      admin != old.admin;
}
