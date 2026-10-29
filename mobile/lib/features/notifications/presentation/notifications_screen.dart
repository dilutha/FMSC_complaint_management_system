import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/paged_list.dart';
import '../../../platform/platform_routes.dart';
import '../../../platform/platform_scope.dart';
import '../data/notifications.dart';

const _icons = <String, IconData>{
  'case_submitted': Icons.outbox_outlined,
  'new_case': Icons.inbox_outlined,
  'case_assigned': Icons.assignment_ind_outlined,
  'status_update': Icons.update,
  'information_requested': Icons.help_outline,
  'case_update': Icons.chat_bubble_outline,
  'deadline_reminder': Icons.alarm,
  'escalation': Icons.warning_amber_rounded,
  'case_solved': Icons.task_alt,
  'resolution_verified': Icons.verified_outlined,
  'case_reopened': Icons.replay,
  'case_rejected': Icons.block,
  'suggestion_decision': Icons.gavel_outlined,
  'suggestion_update': Icons.lightbulb_outline,
};

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final _listKey = GlobalKey<PagedListState<AppNotification>>();
  bool _unreadOnly = false;
  int _reload = 0;

  Future<void> _open(AppNotification n, int index) async {
    final scope = PlatformScope.of(context);
    if (!n.isRead) {
      try {
        final updated = await scope.notifications.markRead(n.id);
        _listKey.currentState?.replace(index, updated);
        scope.unread.set(scope.unread.count - 1);
      } on ApiException {
        // Opening the record still works; it will show as unread until next refresh.
      }
    }
    if (!mounted) return;
    await PlatformRoutes.openTarget(context, n.targetType, n.targetId);
  }

  Future<void> _markAll() async {
    final scope = PlatformScope.of(context);
    try {
      await scope.notifications.markAllRead();
      scope.unread.set(0);
      setState(() => _reload++);
      if (mounted) showSuccess(context, 'All notifications marked as read.');
    } on ApiException catch (e) {
      if (mounted) showSuccess(context, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scope = PlatformScope.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          ListenableBuilder(
            listenable: scope.unread,
            builder: (context, _) => scope.unread.count == 0
                ? const SizedBox.shrink()
                : TextButton(
                    onPressed: _markAll,
                    style: TextButton.styleFrom(foregroundColor: Colors.white),
                    child: const Text('Mark all read'),
                  ),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(Space.lg, Space.md, Space.lg, Space.sm),
            child: SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: false, label: Text('All')),
                ButtonSegment(value: true, label: Text('Unread')),
              ],
              selected: {_unreadOnly},
              showSelectedIcon: false,
              onSelectionChanged: (s) => setState(() => _unreadOnly = s.first),
            ),
          ),
          Expanded(
            child: PagedList<AppNotification>(
              key: _listKey,
              reloadKey: (_unreadOnly, _reload),
              loadingMessage: 'Loading notifications…',
              load: (page) async {
                final result = await scope.notifications.list(page: page, unreadOnly: _unreadOnly);
                if (page == 1) scope.unread.refresh();
                return result;
              },
              empty: MessageView(
                icon: Icons.notifications_none,
                title: _unreadOnly ? 'No unread notifications' : 'No notifications yet',
                message: 'Updates about your cases and suggestions will appear here.',
              ),
              itemBuilder: (context, n, i) => _NotificationTile(notification: n, onTap: () => _open(n, i)),
            ),
          ),
        ],
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.notification, required this.onTap});
  final AppNotification notification;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final n = notification;
    final theme = Theme.of(context);
    final unread = !n.isRead;
    return Semantics(
      button: true,
      label: '${unread ? 'Unread. ' : ''}${n.title}. ${n.body} ${formatDateTime(n.createdAt)}',
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        child: Container(
          color: unread ? UsjColors.infoBg.withValues(alpha: 0.45) : null,
          constraints: const BoxConstraints(minHeight: kMinTouchTarget + 16),
          padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(_icons[n.eventType] ?? Icons.notifications_none, color: UsjColors.textSecondary),
              const SizedBox(width: Space.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      n.title,
                      style: theme.textTheme.bodyLarge?.copyWith(fontWeight: unread ? FontWeight.w700 : FontWeight.w400),
                    ),
                    if (n.body.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        n.body,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodyMedium?.copyWith(color: UsjColors.textSecondary),
                      ),
                    ],
                    const SizedBox(height: Space.xs),
                    Text(formatDateTime(n.createdAt), style: theme.textTheme.bodySmall),
                  ],
                ),
              ),
              if (unread) ...[
                const SizedBox(width: Space.sm),
                // Dot plus a text label: unread state is not shown by colour alone.
                const Column(
                  children: [
                    Icon(Icons.circle, size: 10, color: UsjColors.red),
                    Text('New', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
