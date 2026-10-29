import 'package:flutter/material.dart';

import '../features/auth/data/current_user.dart';
import '../features/cases/case_routes.dart';
import '../features/dashboard/presentation/dashboard_screen.dart';
import '../features/notifications/presentation/notifications_screen.dart';
import '../features/profile/profile_screen.dart';
import '../features/suggestions/presentation/suggestions_screen.dart';
import 'platform_scope.dart';

class _Destination {
  const _Destination(this.label, this.icon, this.selectedIcon, this.builder);
  final String label;
  final IconData icon;
  final IconData selectedIcon;
  final WidgetBuilder builder;
}

/// Main navigation: a standard bottom navigation bar (Jakob's law) with at
/// most five role-appropriate destinations (Hick's law). Entries are hints
/// only; the server enforces every permission.
List<_Destination> _destinationsFor(CurrentUser user) => [
  _Destination('Cases', Icons.folder_outlined, Icons.folder, (_) => CaseRoutes.myCases()),
  if (user.canViewDashboard)
    _Destination('Dashboard', Icons.insights_outlined, Icons.insights, (_) => const DashboardScreen()),
  if (user.seesSuggestionQueue)
    _Destination('Suggestions', Icons.lightbulb_outline, Icons.lightbulb, (_) => const SuggestionsScreen()),
  _Destination('Alerts', Icons.notifications_none, Icons.notifications, (_) => const NotificationsScreen()),
  _Destination('Profile', Icons.person_outline, Icons.person, (_) => const ProfileScreen()),
];

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> with WidgetsBindingObserver {
  int _index = 0;
  bool _started = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_started) {
      _started = true;
      PlatformScope.of(context).unread.refresh();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && mounted) PlatformScope.of(context).unread.refresh();
  }

  @override
  Widget build(BuildContext context) {
    final scope = PlatformScope.of(context);
    final user = scope.session.user!;
    final destinations = _destinationsFor(user);
    final index = _index.clamp(0, destinations.length - 1);
    return Scaffold(
      body: IndexedStack(
        index: index,
        children: [for (final d in destinations) Builder(builder: d.builder)],
      ),
      bottomNavigationBar: ListenableBuilder(
        listenable: scope.unread,
        builder: (context, _) => NavigationBar(
          selectedIndex: index,
          onDestinationSelected: (i) {
            setState(() => _index = i);
            if (destinations[i].label == 'Alerts') scope.unread.refresh();
          },
          destinations: [
            for (final d in destinations)
              NavigationDestination(
                label: d.label,
                tooltip: d.label == 'Alerts' && scope.unread.count > 0
                    ? 'Notifications, ${scope.unread.count} unread'
                    : d.label,
                icon: _withBadge(d, d.icon, scope.unread.count),
                selectedIcon: _withBadge(d, d.selectedIcon, scope.unread.count),
              ),
          ],
        ),
      ),
    );
  }

  Widget _withBadge(_Destination d, IconData icon, int unread) {
    if (d.label != 'Alerts' || unread == 0) return Icon(icon);
    return Badge(label: Text(unread > 99 ? '99+' : '$unread'), child: Icon(icon));
  }
}
