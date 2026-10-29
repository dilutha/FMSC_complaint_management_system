import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/platform_scope.dart';
import '../../cases/case_scope.dart';
import '../data/dashboard.dart';
import 'dashboard_filters_sheet.dart';
import 'dashboard_lists.dart';

enum Period {
  days30('30 days', 30),
  days90('90 days', 90),
  months12('12 months', 365),
  all('All time', null);

  const Period(this.label, this.days);
  final String label;
  final int? days;
}

const _statusOptions = [
  (value: 'submitted', label: 'Submitted'),
  (value: 'under_review', label: 'Under Review'),
  (value: 'waiting_for_information', label: 'Waiting for Information'),
  (value: 'assigned', label: 'Assigned'),
  (value: 'in_progress', label: 'In Progress'),
  (value: 'solved', label: 'Solved – Awaiting Verification'),
  (value: 'closed', label: 'Closed'),
  (value: 'rejected', label: 'Rejected'),
  (value: 'reopened', label: 'Reopened'),
];

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Period _period = Period.days90;
  DashboardFilters _filters = const DashboardFilters();
  DashboardSummary? _summary;
  Trends? _trends;
  ApiException? _error;
  bool _loading = false;
  bool _started = false;
  List<({int id, String name})> _units = const [];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_started) {
      _started = true;
      _filters = _withPeriod(_filters, _period);
      _load();
    }
  }

  DashboardFilters _withPeriod(DashboardFilters f, Period p) {
    final today = DateUtils.dateOnly(DateTime.now());
    return DashboardFilters(
      dateFrom: p.days == null ? null : today.subtract(Duration(days: p.days! - 1)),
      dateTo: p.days == null ? null : today,
      categoryId: f.categoryId,
      priority: f.priority,
      caseType: f.caseType,
      status: f.status,
      authorityId: f.authorityId,
      location: f.location,
    );
  }

  Future<void> _load() async {
    final repo = PlatformScope.of(context).dashboard;
    final filters = _filters;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([repo.summary(filters), repo.trends(filters)]);
      if (!mounted || filters != _filters) return;
      setState(() {
        _summary = results[0] as DashboardSummary;
        _trends = results[1] as Trends;
      });
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openFilters() async {
    final scope = PlatformScope.of(context);
    final cases = CaseScope.of(context).repository;
    List<({int id, String name})> categories = const [];
    try {
      categories = [for (final c in await cases.getCategories()) (id: c.id, name: c.name)];
      if (_units.isEmpty) {
        final workload = await scope.dashboard.workload(const DashboardFilters());
        _units = [for (final r in workload.rows) (id: r.authorityId, name: r.authorityName)];
      }
    } on ApiException {
      // Filters still open; the lists that failed to load are simply omitted.
    }
    if (!mounted) return;
    final result = await showFormSheet<DashboardFilters>(
      context,
      title: 'Filter dashboard',
      child: DashboardFiltersSheet(initial: _filters, categories: categories, units: _units, statuses: _statusOptions),
    );
    if (result != null && mounted) {
      setState(() => _filters = result);
      _load();
    }
  }

  void _open(Widget screen) =>
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => DashboardFiltersHolder(filters: _filters, child: screen)));

  @override
  Widget build(BuildContext context) {
    final refinements = _filters.refinementCount;
    return Scaffold(
      appBar: AppBar(title: const Text('Management dashboard')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(Space.lg, Space.md, Space.lg, 0),
            child: Row(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: SegmentedButton<Period>(
                      segments: [for (final p in Period.values) ButtonSegment(value: p, label: Text(p.label))],
                      selected: {_period},
                      showSelectedIcon: false,
                      onSelectionChanged: (s) {
                        setState(() {
                          _period = s.first;
                          _filters = _withPeriod(_filters, _period);
                        });
                        _load();
                      },
                    ),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.sm),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    _rangeText(),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: _openFilters,
                  icon: const Icon(Icons.tune),
                  label: Text(refinements == 0 ? 'Filters' : 'Filters ($refinements)'),
                ),
              ],
            ),
          ),
          if (_loading && _summary != null) const LinearProgressIndicator(minHeight: 2),
          Expanded(child: _body()),
        ],
      ),
    );
  }

  String _rangeText() {
    final f = _filters;
    if (f.dateFrom == null) return 'Cases submitted at any time';
    return 'Cases submitted ${formatDate(f.dateFrom!)} – ${formatDate(f.dateTo!)}';
  }

  Widget _body() {
    if (_error != null && _summary == null) return MessageView.error(message: _error!.message, onRetry: _load);
    final s = _summary;
    if (s == null) return const LoadingView(message: 'Loading dashboard…');
    final rates = s.rates;
    String days(double? v) => v == null ? '–' : '${v.toStringAsFixed(1)} d';
    String hours(double? v) => v == null ? '–' : '${v.toStringAsFixed(1)} h';

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.lg, Space.xxl),
        children: [
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: Space.md),
              child: Text('Could not refresh: ${_error!.message}', style: const TextStyle(color: UsjColors.error)),
            ),
          if (s.total('total') == 0)
            const Padding(
              padding: EdgeInsets.only(bottom: Space.md),
              child: MessageView(
                icon: Icons.insights_outlined,
                title: 'No cases match these filters',
                message: 'Try a longer period or clear the filters.',
              ),
            ),
          _KpiGrid(
            tiles: [
              KpiTile(
                label: 'Total cases',
                value: '${s.total('total')}',
                hint: '${s.total('complaints')} complaints · ${s.total('suggestions')} suggestions',
              ),
              KpiTile(label: 'Open', value: '${s.total('open')}', hint: 'Not closed or rejected'),
              KpiTile(
                label: 'Overdue',
                value: '${s.total('overdue')}',
                hint: '${rates['overdue']!.percent} of active cases',
                alert: s.total('overdue') > 0,
              ),
              KpiTile(label: 'Not attempted', value: '${s.total('not_attempted')}', hint: 'Still “Submitted”'),
              KpiTile(
                label: 'Not started',
                value: '${s.total('not_started')}',
                hint: 'Assigned, work not started',
                onTap: () => _open(const AgeingScreen()),
              ),
              KpiTile(label: 'Urgent', value: '${s.total('urgent')}', hint: '${s.total('normal')} normal'),
              KpiTile(
                label: 'Median resolution',
                value: days(s.resolutionDays.median),
                hint: 'Submitted → solved · ${s.resolutionDays.sampleSize} cases',
              ),
              KpiTile(
                label: 'Median first response',
                value: hours(s.firstResponseHours.median),
                hint: 'Submitted → first review · ${s.firstResponseHours.sampleSize} cases',
              ),
              KpiTile(
                label: 'Reopening rate',
                value: rates['reopening']!.percent,
                hint: '${rates['reopening']!.numerator} of ${rates['reopening']!.denominator} solved cases',
              ),
              KpiTile(
                label: 'Repeat issues',
                value: rates['repeat_issue']!.percent,
                hint: 'Linked to an earlier case',
              ),
            ],
          ),
          const SizedBox(height: Space.lg),
          _NavCard(
            icon: Icons.groups_outlined,
            title: 'Responsible unit workload',
            subtitle: 'Active, not started and overdue cases per unit',
            onTap: () => _open(const WorkloadScreen()),
          ),
          _NavCard(
            icon: Icons.hourglass_bottom,
            title: 'Ageing report',
            subtitle: 'Not-started cases by age in days',
            onTap: () => _open(const AgeingScreen()),
          ),
          _NavCard(
            icon: Icons.table_rows_outlined,
            title: 'Case report',
            subtitle: 'Every matching case, newest first',
            onTap: () => _open(const CaseReportScreen()),
          ),
          const SizedBox(height: Space.lg),
          SectionCard(title: 'Cases by status', child: BreakdownList(rows: s.byStatus, hideZero: true)),
          const SizedBox(height: Space.md),
          SectionCard(title: 'Cases by category', child: BreakdownList(rows: s.byCategory)),
          const SizedBox(height: Space.md),
          SectionCard(
            title: 'Priority and type',
            child: Column(children: [BreakdownList(rows: s.byPriority), BreakdownList(rows: s.byCaseType)]),
          ),
          const SizedBox(height: Space.md),
          SectionCard(
            title: 'Most reported locations',
            child: BreakdownList(rows: s.byLocation, emptyText: 'No locations recorded.'),
          ),
          const SizedBox(height: Space.md),
          SectionCard(
            title: 'Suggestions',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                BreakdownList(rows: s.suggestionsByStatus, hideZero: true, emptyText: 'No suggestions.'),
                const SizedBox(height: Space.sm),
                Text(
                  'Implementation rate: ${s.suggestionImplementation.percent} '
                  '(${s.suggestionImplementation.numerator} of ${s.suggestionImplementation.denominator} accepted)',
                ),
              ],
            ),
          ),
          if (_trends != null && _trends!.points.isNotEmpty) ...[
            const SizedBox(height: Space.md),
            SectionCard(title: 'Trend (${_trends!.interval}ly)', child: _TrendTable(trends: _trends!)),
          ],
          const SizedBox(height: Space.md),
          const _Definitions(),
        ],
      ),
    );
  }
}

class _KpiGrid extends StatelessWidget {
  const _KpiGrid({required this.tiles});
  final List<Widget> tiles;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= 900 ? 4 : (constraints.maxWidth >= 560 ? 3 : 2);
        final width = (constraints.maxWidth - Space.md * (columns - 1)) / columns;
        return Wrap(
          spacing: Space.md,
          runSpacing: Space.md,
          children: [for (final t in tiles) SizedBox(width: width, child: t)],
        );
      },
    );
  }
}

class _NavCard extends StatelessWidget {
  const _NavCard({required this.icon, required this.title, required this.subtitle, required this.onTap});
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: Space.sm),
    child: Card(
      clipBehavior: Clip.antiAlias,
      child: ListTile(
        minTileHeight: kMinTouchTarget + 8,
        leading: Icon(icon, color: UsjColors.maroon),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    ),
  );
}

class _TrendTable extends StatelessWidget {
  const _TrendTable({required this.trends});
  final Trends trends;

  @override
  Widget build(BuildContext context) {
    final rows = trends.points.length > 12 ? trends.points.sublist(trends.points.length - 12) : trends.points;
    final style = Theme.of(context).textTheme.bodyMedium?.copyWith(fontFeatures: const [FontFeature.tabularFigures()]);
    final head = Theme.of(context).textTheme.labelMedium?.copyWith(color: UsjColors.textSecondary);
    String label(DateTime d) => trends.interval == 'month' ? formatDate(d).split(' ').skip(1).join(' ') : formatDate(d);
    return Table(
      columnWidths: const {0: FlexColumnWidth(2), 1: FlexColumnWidth(), 2: FlexColumnWidth(), 3: FlexColumnWidth()},
      children: [
        TableRow(children: [
          Text(trends.interval == 'month' ? 'Month' : (trends.interval == 'week' ? 'Week of' : 'Day'), style: head),
          Text('Submitted', style: head, textAlign: TextAlign.end),
          Text('Solved', style: head, textAlign: TextAlign.end),
          Text('Closed', style: head, textAlign: TextAlign.end),
        ]),
        for (final p in rows)
          TableRow(children: [
            Padding(padding: const EdgeInsets.symmetric(vertical: Space.xs), child: Text(label(p.period), style: style)),
            Text('${p.submitted}', style: style, textAlign: TextAlign.end),
            Text('${p.solved}', style: style, textAlign: TextAlign.end),
            Text('${p.closed}', style: style, textAlign: TextAlign.end),
          ]),
      ],
    );
  }
}

class _Definitions extends StatelessWidget {
  const _Definitions();

  @override
  Widget build(BuildContext context) => const Card(
    child: ExpansionTile(
      leading: Icon(Icons.info_outline),
      title: Text('How these figures are calculated'),
      childrenPadding: EdgeInsets.fromLTRB(Space.lg, 0, Space.lg, Space.lg),
      expandedCrossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '• The period selects cases by submission date; figures show those cases as they are now.\n'
          '• Open: not closed and not rejected. Overdue: still active and past its deadline.\n'
          '• Resolution time: from submission until the case was marked solved.\n'
          '• First response: from submission until an administrator first acted on the case.\n'
          '• Reopening rate: solved cases that were later reopened.\n'
          '• Repeat issues: cases an administrator linked to an earlier case as a duplicate or related issue.\n'
          '• Case volume reflects the kind of issues a unit handles and is not on its own a measure of performance.',
        ),
      ],
    ),
  );
}
