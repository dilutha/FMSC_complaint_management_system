import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/platform_scope.dart';
import '../../cases/case_routes.dart';
import '../../cases/presentation/submit_case_screen.dart';
import '../../staff/data/staff_cases.dart';
import '../data/overview.dart';
import 'dashboard_screen.dart';

/// The landing dashboard for every role. Content depends on the workspace the
/// server returns (never on anything the client chooses):
/// complainer · department · case_admin · admin · management.
class RoleDashboardScreen extends StatefulWidget {
  const RoleDashboardScreen({super.key, this.onOpenCases});

  /// Switches the shell to its case list (used by "View all" links).
  final VoidCallback? onOpenCases;

  @override
  State<RoleDashboardScreen> createState() => _RoleDashboardScreenState();
}

class _RoleDashboardScreenState extends State<RoleDashboardScreen> {
  DashboardOverview? _data;
  ApiException? _error;
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_started) {
      _started = true;
      _load();
    }
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final data = await PlatformScope.of(context).dashboard.overview();
      if (mounted) setState(() => _data = data);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _openCase(int id) async {
    await CaseRoutes.openCase(context, id);
    if (mounted) _load();
  }

  Future<void> _submit(String type) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => SubmitCaseScreen(initialType: type)));
    if (mounted) _load();
  }

  String _title(DashboardOverview d) {
    final user = PlatformScope.of(context).session.user;
    return switch (d.workspace) {
      'complainer' => '${user?.roleLabel ?? d.roleLabel} dashboard',
      'department' => '${d.departments.isEmpty ? 'Department' : d.departments.join(', ')} dashboard',
      'case_admin' => 'Case administrator dashboard',
      'admin' => 'Admin dashboard',
      _ => 'Faculty overview',
    };
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const UsjLogo(size: 30),
            const SizedBox(width: Space.md),
            Flexible(child: Text(d == null ? 'Dashboard' : _title(d), overflow: TextOverflow.ellipsis)),
          ],
        ),
      ),
      body: () {
        if (_error != null && d == null) return MessageView.error(message: _error!.message, onRetry: _load);
        if (d == null) return const LoadingView(message: 'Loading your dashboard…');
        return RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(Space.lg, Space.lg, Space.lg, Space.xxl),
            children: [
              _Greeting(name: PlatformScope.of(context).session.user?.displayName ?? '', data: d),
              const SizedBox(height: Space.lg),
              if (d.workspace == 'complainer') ...[
                _SubmitActions(onSubmit: _submit),
                const SizedBox(height: Space.lg),
              ],
              _Tiles(data: d),
              const SizedBox(height: Space.lg),
              ..._sections(d),
            ],
          ),
        );
      }(),
    );
  }

  List<Widget> _sections(DashboardOverview d) {
    final sections = <Widget>[];
    void add(Widget w) => sections
      ..add(w)
      ..add(const SizedBox(height: Space.md));

    final recentTitle = switch (d.workspace) {
      'complainer' => 'My recent submissions',
      'department' => 'Recent assignments',
      'case_admin' => 'Awaiting review (urgent first)',
      _ => 'Recently updated cases',
    };
    add(SectionCard(
      title: recentTitle,
      trailing: widget.onOpenCases == null
          ? null
          : TextButton(onPressed: widget.onOpenCases, child: const Text('View all')),
      child: d.recent.isEmpty
          ? Text(
              switch (d.workspace) {
                'complainer' => 'You have not submitted anything yet. Use the buttons above to get started.',
                'department' => 'No cases are assigned to your department right now.',
                'case_admin' => 'Nothing is waiting for review. Well done!',
                _ => 'No cases yet.',
              },
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: UsjColors.textSecondary),
            )
          : Column(
              children: [
                for (final c in d.recent)
                  _CaseRow(
                    row: c,
                    actionLabel: d.workspace == 'case_admin' ? 'Review' : null,
                    onTap: () => _openCase(c.id),
                  ),
              ],
            ),
    ));

    if (d.byDepartment.isNotEmpty) {
      add(SectionCard(
        title: 'Department workload (active cases)',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            BreakdownList(rows: [for (final x in d.byDepartment) (label: x.name, count: x.active)]),
            const SizedBox(height: Space.sm),
            for (final x in d.byDepartment.where((x) => x.overdue > 0))
              Text('${x.name}: ${x.overdue} overdue', style: const TextStyle(color: UsjColors.error)),
          ],
        ),
      ));
    }
    if (d.byStatus.isNotEmpty) {
      add(SectionCard(title: 'Cases by status', child: BreakdownList(rows: d.byStatus, hideZero: true)));
    }
    if (d.activity.isNotEmpty) {
      add(SectionCard(
        title: 'Recent case activity',
        child: Column(
          children: [
            for (final a in d.activity)
              ListTile(
                contentPadding: EdgeInsets.zero,
                minTileHeight: kMinTouchTarget,
                leading: const Icon(Icons.history, color: UsjColors.textSecondary),
                title: Text('${a.caseNumber} → ${a.status}'),
                subtitle: Text(
                  '${a.actor} · ${formatDateTime(a.at)}${a.message.isEmpty ? '' : '\n“${a.message}”'}',
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
                onTap: () => _openCase(a.caseId),
              ),
          ],
        ),
      ));
    }
    if (d.workspace == 'admin' || d.workspace == 'management' || d.workspace == 'case_admin') {
      add(Card(
        clipBehavior: Clip.antiAlias,
        child: ListTile(
          leading: const Icon(Icons.insights_outlined, color: UsjColors.maroon),
          title: const Text('Reports and analytics'),
          subtitle: const Text('Trends, response times, ageing and exports'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DashboardScreen())),
        ),
      ));
    }
    return sections;
  }
}

class _Greeting extends StatelessWidget {
  const _Greeting({required this.name, required this.data});
  final String name;
  final DashboardOverview data;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final subtitle = switch (data.workspace) {
      'complainer' => 'Track your complaints and suggestions, and see every update.',
      'department' => 'Cases assigned to your department. Every status update needs a short message.',
      'case_admin' => 'Review new cases, assign them to the right department and follow their progress.',
      'admin' => 'Faculty-wide monitoring. You can read every case and add messages.',
      _ => 'Faculty-wide overview.',
    };
    return Container(
      padding: const EdgeInsets.all(Space.lg),
      decoration: BoxDecoration(
        color: UsjColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: const Border(left: BorderSide(color: UsjColors.gold, width: 6)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Welcome${name.isEmpty ? '' : ', $name'}', style: theme.textTheme.titleLarge),
          const SizedBox(height: Space.xs),
          Text(subtitle, style: theme.textTheme.bodyMedium?.copyWith(color: UsjColors.textSecondary)),
        ],
      ),
    );
  }
}

class _SubmitActions extends StatelessWidget {
  const _SubmitActions({required this.onSubmit});
  final ValueChanged<String> onSubmit;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: Space.md,
      runSpacing: Space.md,
      children: [
        FilledButton.icon(
          onPressed: () => onSubmit('complaint'),
          icon: const Icon(Icons.report_problem_outlined),
          label: const Text('Submit complaint'),
        ),
        FilledButton.icon(
          onPressed: () => onSubmit('suggestion'),
          style: FilledButton.styleFrom(backgroundColor: UsjColors.blue),
          icon: const Icon(Icons.lightbulb_outline),
          label: const Text('Submit suggestion'),
        ),
      ],
    );
  }
}

class _Tiles extends StatelessWidget {
  const _Tiles({required this.data});
  final DashboardOverview data;

  @override
  Widget build(BuildContext context) {
    final d = data;
    final tiles = switch (d.workspace) {
      'complainer' => [
        KpiTile(label: 'Submitted by me', value: '${d.count('total')}'),
        KpiTile(label: 'Open', value: '${d.count('open')}', hint: 'Not closed or rejected'),
        KpiTile(label: 'Being reviewed or processed', value: '${d.count('processing')}'),
        KpiTile(label: 'Resolved', value: '${d.count('resolved')}'),
        KpiTile(label: 'Pending suggestions', value: '${d.count('pending_suggestions')}'),
      ],
      'department' => [
        KpiTile(label: 'Assigned to us', value: '${d.count('total')}'),
        KpiTile(label: 'Newly assigned', value: '${d.count('assigned')}'),
        KpiTile(label: 'Awaiting action', value: '${d.count('awaiting_action')}', hint: 'Assigned or reopened'),
        KpiTile(label: 'In progress', value: '${d.count('in_progress')}'),
        KpiTile(label: 'Resolved', value: '${d.count('resolved')}'),
        KpiTile(label: 'Overdue', value: '${d.count('overdue')}', alert: d.count('overdue') > 0),
      ],
      'case_admin' => [
        KpiTile(label: 'Total cases', value: '${d.count('total')}'),
        KpiTile(label: 'New (unreviewed)', value: '${d.count('new')}'),
        KpiTile(label: 'Awaiting review', value: '${d.count('awaiting_review')}'),
        KpiTile(label: 'Unassigned', value: '${d.count('unassigned')}'),
        KpiTile(label: 'Awaiting department', value: '${d.count('assigned')}'),
        KpiTile(label: 'In progress', value: '${d.count('in_progress')}'),
        KpiTile(label: 'Resolved', value: '${d.count('resolved')}'),
        KpiTile(label: 'Needs reassignment', value: '${d.count('needs_reassignment')}',
            hint: 'Reopened or unit inactive', alert: d.count('needs_reassignment') > 0),
        KpiTile(label: 'Overdue', value: '${d.count('overdue')}', alert: d.count('overdue') > 0),
      ],
      _ => [
        KpiTile(label: 'Total cases', value: '${d.count('total')}'),
        KpiTile(label: 'Newly submitted', value: '${d.count('new')}'),
        KpiTile(label: 'Awaiting review', value: '${d.count('awaiting_review')}'),
        KpiTile(label: 'Assigned to departments', value: '${d.count('assigned')}'),
        KpiTile(label: 'In progress', value: '${d.count('in_progress')}'),
        KpiTile(label: 'Resolved', value: '${d.count('resolved')}'),
        KpiTile(label: 'Overdue', value: '${d.count('overdue')}', alert: d.count('overdue') > 0),
      ],
    };
    return LayoutBuilder(
      builder: (context, c) {
        final columns = c.maxWidth >= 900 ? 4 : (c.maxWidth >= 560 ? 3 : 2);
        final width = (c.maxWidth - Space.md * (columns - 1)) / columns;
        return Wrap(
          spacing: Space.md,
          runSpacing: Space.md,
          children: [for (final t in tiles) SizedBox(width: width, child: t)],
        );
      },
    );
  }
}

class _CaseRow extends StatelessWidget {
  const _CaseRow({required this.row, required this.onTap, this.actionLabel});
  final StaffCaseRow row;
  final VoidCallback onTap;
  final String? actionLabel;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      minTileHeight: kMinTouchTarget + 8,
      title: Text(row.title, maxLines: 2, overflow: TextOverflow.ellipsis),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: Space.xs),
        child: Wrap(
          spacing: Space.sm,
          runSpacing: Space.xs,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text([
              row.caseNumber,
              if (row.caseType == 'suggestion') 'Suggestion',
              ?row.submitterType,
              ?row.department,
            ].join(' · ')),
            StatusBadge(status: row.status, label: row.statusLabel),
            if (row.priority == 'urgent') const PriorityBadge(priority: 'urgent'),
            if (row.isOverdue) const OverdueBadge(),
          ],
        ),
      ),
      trailing: actionLabel == null
          ? const Icon(Icons.chevron_right)
          : OutlinedButton(onPressed: onTap, child: Text(actionLabel!)),
      onTap: onTap,
    );
  }
}
