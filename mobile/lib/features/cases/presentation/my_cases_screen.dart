import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../case_scope.dart';
import '../data/models.dart';
import 'case_detail_screen.dart';
import 'submit_case_screen.dart';

/// Four filters only (Hick's law); each maps to backend status values.
enum CaseFilter {
  all('All', null),
  active('In progress', 'submitted,under_review,waiting_for_information,assigned,in_progress,reopened'),
  awaiting('To confirm', 'solved'),
  closed('Closed', 'closed,rejected');

  const CaseFilter(this.label, this.statuses);
  final String label;
  final String? statuses;
}

class MyCasesScreen extends StatefulWidget {
  const MyCasesScreen({super.key});

  @override
  State<MyCasesScreen> createState() => _MyCasesScreenState();
}

class _MyCasesScreenState extends State<MyCasesScreen> {
  final _scroll = ScrollController();
  final _items = <CaseSummary>[];
  CaseFilter _filter = CaseFilter.all;
  int _page = 0;
  int _count = 0;
  bool _hasNext = true;
  bool _loading = false;
  ApiException? _error;
  ApiException? _pageError;
  bool _initialised = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialised) {
      _initialised = true;
      _reload();
    }
  }

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 300) _loadMore();
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    setState(() {
      _items.clear();
      _page = 0;
      _hasNext = true;
      _error = null;
      _pageError = null;
    });
    await _loadMore();
  }

  Future<void> _loadMore() async {
    if (_loading || !_hasNext) return;
    setState(() {
      _loading = true;
      _pageError = null;
    });
    final filter = _filter;
    try {
      final result = await CaseScope.of(context).repository.listMyCases(page: _page + 1, statusFilter: filter.statuses);
      if (!mounted || filter != _filter) return;
      setState(() {
        _page += 1;
        _items.addAll(result.items);
        _count = result.count;
        _hasNext = result.hasNext;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        if (_items.isEmpty) {
          _error = e;
        } else {
          _pageError = e;
        }
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openSubmit() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SubmitCaseScreen()));
    if (mounted) _reload();
  }

  Future<void> _openCase(CaseSummary c) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => CaseDetailScreen(caseId: c.id)));
    if (mounted) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            UsjLogo(size: 32),
            SizedBox(width: Space.md),
            Text('My cases'),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openSubmit,
        backgroundColor: UsjColors.red,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: const Text('New case'),
        tooltip: 'Submit a new complaint or suggestion',
      ),
      body: Column(
        children: [
          _FilterBar(
            selected: _filter,
            onChanged: (f) {
              setState(() => _filter = f);
              _reload();
            },
          ),
          Expanded(child: _body()),
        ],
      ),
    );
  }

  Widget _body() {
    if (_error != null) return MessageView.error(message: _error!.message, onRetry: _reload);
    if (_items.isEmpty && _loading) return const LoadingView(message: 'Loading your cases…');
    if (_items.isEmpty) {
      return RefreshIndicator(
        onRefresh: _reload,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            const SizedBox(height: Space.xxl),
            MessageView(
              icon: Icons.inbox_outlined,
              title: _filter == CaseFilter.all ? 'You have not submitted any cases yet' : 'No cases in this list',
              message: _filter == CaseFilter.all
                  ? 'Report a problem or share a suggestion for the faculty.'
                  : 'Try another filter to see your other cases.',
              actionLabel: _filter == CaseFilter.all ? 'Submit a case' : null,
              onAction: _filter == CaseFilter.all ? _openSubmit : null,
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _reload,
      child: ListView.separated(
        controller: _scroll,
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.lg, 96),
        itemCount: _items.length + 2,
        separatorBuilder: (_, _) => const SizedBox(height: Space.sm),
        itemBuilder: (context, i) {
          if (i == 0) {
            return Semantics(
              liveRegion: true,
              child: Text(
                '$_count ${_count == 1 ? 'case' : 'cases'}',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(color: UsjColors.textSecondary),
              ),
            );
          }
          if (i == _items.length + 1) return _footer();
          final c = _items[i - 1];
          return _CaseTile(item: c, onTap: () => _openCase(c));
        },
      ),
    );
  }

  Widget _footer() {
    if (_loading) {
      return const Padding(
        padding: EdgeInsets.all(Space.lg),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (_pageError != null) {
      return Center(
        child: TextButton.icon(
          onPressed: _loadMore,
          icon: const Icon(Icons.refresh),
          label: Text('Could not load more. ${_pageError!.message} Tap to retry.'),
        ),
      );
    }
    return const SizedBox.shrink();
  }
}

class _FilterBar extends StatelessWidget {
  const _FilterBar({required this.selected, required this.onChanged});
  final CaseFilter selected;
  final ValueChanged<CaseFilter> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: UsjColors.surface,
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.sm),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            for (final f in CaseFilter.values)
              Padding(
                padding: const EdgeInsets.only(right: Space.sm),
                child: ChoiceChip(
                  label: Text(f.label),
                  selected: f == selected,
                  onSelected: (_) => onChanged(f),
                  materialTapTargetSize: MaterialTapTargetSize.padded,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _CaseTile extends StatelessWidget {
  const _CaseTile({required this.item, required this.onTap});
  final CaseSummary item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final awaiting = item.status == 'solved';
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(Space.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(item.caseNumber, style: theme.textTheme.labelLarge?.copyWith(color: UsjColors.textSecondary)),
                  const Spacer(),
                  Text(
                    item.caseTypeLabel,
                    style: theme.textTheme.labelMedium?.copyWith(color: UsjColors.textSecondary),
                  ),
                ],
              ),
              const SizedBox(height: Space.xs),
              Text(item.title, style: theme.textTheme.titleMedium, maxLines: 2, overflow: TextOverflow.ellipsis),
              const SizedBox(height: Space.xs),
              Text(
                '${item.category.name} · ${item.location}',
                style: theme.textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: Space.md),
              Wrap(
                spacing: Space.sm,
                runSpacing: Space.sm,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  StatusBadge(status: item.status, label: awaiting ? 'Solved – please confirm' : item.statusLabel),
                  if (item.priority == 'urgent') PriorityBadge(priority: item.priority),
                  if (item.isOverdue) const OverdueBadge(),
                  Text('Updated ${formatDate(item.updatedAt)}', style: theme.textTheme.bodySmall),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
