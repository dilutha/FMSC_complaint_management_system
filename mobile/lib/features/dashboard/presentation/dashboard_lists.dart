import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/paged_list.dart';
import '../../../platform/platform_scope.dart';
import '../../cases/case_routes.dart';
import '../data/dashboard.dart';

/// Passes the dashboard's current filters to the drill-down screens.
class DashboardFiltersHolder extends InheritedWidget {
  const DashboardFiltersHolder({super.key, required this.filters, required super.child});
  final DashboardFilters filters;

  static DashboardFilters of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<DashboardFiltersHolder>()?.filters ?? const DashboardFilters();

  @override
  bool updateShouldNotify(DashboardFiltersHolder old) => filters != old.filters;
}

/// Loads one value with loading / error-with-retry states.
class _Loader<T> extends StatefulWidget {
  const _Loader({required this.load, required this.builder, required this.loadingMessage});
  final Future<T> Function(BuildContext context) load;
  final Widget Function(BuildContext context, T value, Future<void> Function() reload) builder;
  final String loadingMessage;

  @override
  State<_Loader<T>> createState() => _LoaderState<T>();
}

class _LoaderState<T> extends State<_Loader<T>> {
  T? _value;
  ApiException? _error;
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_started) {
      _started = true;
      _reload();
    }
  }

  Future<void> _reload() async {
    setState(() => _error = null);
    try {
      final value = await widget.load(context);
      if (mounted) setState(() => _value = value);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null && _value == null) return MessageView.error(message: _error!.message, onRetry: _reload);
    if (_value == null) return LoadingView(message: widget.loadingMessage);
    return RefreshIndicator(onRefresh: _reload, child: widget.builder(context, _value as T, _reload));
  }
}

class WorkloadScreen extends StatelessWidget {
  const WorkloadScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Unit workload')),
      body: _Loader<Workload>(
        loadingMessage: 'Loading workload…',
        load: (c) => PlatformScope.of(c).dashboard.workload(DashboardFiltersHolder.of(c)),
        builder: (context, w, _) => ListView(
          padding: const EdgeInsets.all(Space.lg),
          children: [
            Card(
              color: UsjColors.infoBg,
              child: Padding(
                padding: const EdgeInsets.all(Space.md),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.info_outline, color: UsjColors.info),
                    const SizedBox(width: Space.sm),
                    Expanded(child: Text(w.note)),
                  ],
                ),
              ),
            ),
            const SizedBox(height: Space.md),
            if (w.rows.isEmpty)
              const MessageView(icon: Icons.groups_outlined, title: 'No responsible units yet'),
            for (final r in w.rows) ...[
              SectionCard(
                title: r.authorityName,
                trailing: r.overdue > 0
                    ? Text('${r.overdue} overdue',
                        style: const TextStyle(color: UsjColors.error, fontWeight: FontWeight.w600))
                    : null,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: Space.xl,
                      runSpacing: Space.sm,
                      children: [
                        _Stat('Active', r.active),
                        _Stat('Not started', r.notStarted),
                        _Stat('In progress', r.inProgress),
                        _Stat('Waiting for info', r.waiting),
                        _Stat('Awaiting confirmation', r.awaitingVerification),
                        _Stat('Resolved', r.resolved),
                      ],
                    ),
                    const SizedBox(height: Space.sm),
                    Text(
                      'Average age of open cases: ${_days(r.averageOpenAgeDays)} · '
                      'Median resolution: ${_days(r.medianResolutionDays)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: Space.md),
            ],
          ],
        ),
      ),
    );
  }

  static String _days(double? v) => v == null ? '–' : '${v.toStringAsFixed(1)} days';
}

class _Stat extends StatelessWidget {
  const _Stat(this.label, this.value);
  final String label;
  final int value;

  @override
  Widget build(BuildContext context) => Semantics(
    label: '$label: $value',
    excludeSemantics: true,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('$value', style: Theme.of(context).textTheme.titleLarge),
        Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary)),
      ],
    ),
  );
}

class _CaseRow extends StatelessWidget {
  const _CaseRow(this.c);
  final ReportCase c;

  @override
  Widget build(BuildContext context) => ListTile(
    minTileHeight: kMinTouchTarget + 16,
    title: Text(c.title, maxLines: 2, overflow: TextOverflow.ellipsis),
    subtitle: Padding(
      padding: const EdgeInsets.only(top: Space.xs),
      child: Wrap(
        spacing: Space.sm,
        runSpacing: Space.xs,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Text('${c.caseNumber} · ${c.authority ?? 'Unassigned'} · ${c.ageDays} days old'),
          StatusBadge(status: c.status, label: c.statusLabel),
          if (c.priority == 'urgent') const PriorityBadge(priority: 'urgent'),
          if (c.isOverdue) const OverdueBadge(),
        ],
      ),
    ),
    trailing: const Icon(Icons.chevron_right),
    // Opens Member A's case-detail screen (shared navigation contract).
    onTap: () => CaseRoutes.openCase(context, c.id),
  );
}

class AgeingScreen extends StatelessWidget {
  const AgeingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ageing report')),
      body: _Loader<Ageing>(
        loadingMessage: 'Loading ageing report…',
        load: (c) => PlatformScope.of(c).dashboard.ageing(DashboardFiltersHolder.of(c)),
        builder: (context, a, _) => ListView(
          padding: const EdgeInsets.symmetric(vertical: Space.lg),
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: Space.lg),
              child: SectionCard(
                title: 'Not-started cases by age',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${a.count} case${a.count == 1 ? '' : 's'} assigned but not started'
                      '${a.averageAgeDays == null ? '' : ' · average ${a.averageAgeDays!.toStringAsFixed(1)} days'}',
                    ),
                    const SizedBox(height: Space.sm),
                    BreakdownList(rows: a.buckets),
                  ],
                ),
              ),
            ),
            const SizedBox(height: Space.md),
            if (a.oldest.isEmpty)
              const MessageView(icon: Icons.check_circle_outline, title: 'No cases are waiting to be started')
            else ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.sm),
                child: Semantics(
                  header: true,
                  child: Text('Oldest first', style: Theme.of(context).textTheme.titleMedium),
                ),
              ),
              for (final c in a.oldest) ...[_CaseRow(c), const Divider(height: 1)],
            ],
          ],
        ),
      ),
    );
  }
}

class CaseReportScreen extends StatelessWidget {
  const CaseReportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final filters = DashboardFiltersHolder.of(context);
    final repo = PlatformScope.of(context).dashboard;
    return Scaffold(
      appBar: AppBar(title: const Text('Case report')),
      body: PagedList<ReportCase>(
        loadingMessage: 'Loading report…',
        load: (page) => repo.report(filters, page: page),
        header: (context, count) => Padding(
          padding: const EdgeInsets.fromLTRB(Space.lg, Space.md, Space.lg, Space.sm),
          child: Text('$count matching case${count == 1 ? '' : 's'}',
              style: Theme.of(context).textTheme.titleSmall),
        ),
        empty: const MessageView(icon: Icons.search_off, title: 'No cases match these filters'),
        itemBuilder: (context, c, _) => _CaseRow(c),
      ),
    );
  }
}
