import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/platform_scope.dart';
import '../../cases/case_routes.dart';
import '../data/suggestions.dart';
import 'suggestion_forms.dart';

/// Suggestion decision details and implementation tracking. The full case
/// (attachments, comments, verification) opens in the case module's screen.
class SuggestionDetailScreen extends StatefulWidget {
  const SuggestionDetailScreen({super.key, required this.suggestionId});
  final int suggestionId;

  @override
  State<SuggestionDetailScreen> createState() => _SuggestionDetailScreenState();
}

class _SuggestionDetailScreenState extends State<SuggestionDetailScreen> {
  SuggestionDetail? _detail;
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
      final detail = await PlatformScope.of(context).suggestions.get(widget.suggestionId);
      if (mounted) setState(() => _detail = detail);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _act(SuggestionAction action) async {
    final updated = await runSuggestionAction(context, _detail!, action);
    if (updated != null && mounted) {
      setState(() => _detail = updated);
      showSuccess(context, action.successMessage);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_detail?.summary.caseNumber ?? 'Suggestion')),
      body: _body(),
    );
  }

  Widget _body() {
    if (_error != null && _detail == null) {
      if (_error!.statusCode == 404) {
        return const MessageView(
          icon: Icons.search_off,
          title: 'Suggestion not found',
          message: 'It may have been removed, or you may not have access to it.',
        );
      }
      return MessageView.error(message: _error!.message, onRetry: _load);
    }
    final d = _detail;
    if (d == null) return const LoadingView(message: 'Loading suggestion…');
    final s = d.summary;
    final theme = Theme.of(context);
    final actions = [for (final a in SuggestionAction.values) if (d.can(a.apiName)) a];

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(Space.lg, Space.lg, Space.lg, Space.xxl),
        children: [
          Text(s.title, style: theme.textTheme.titleLarge),
          const SizedBox(height: Space.sm),
          Wrap(spacing: Space.sm, children: [SuggestionStatusBadge(status: s.status, label: s.statusLabel)]),
          const SizedBox(height: Space.lg),
          if (actions.isNotEmpty) ...[
            _ActionBar(actions: actions, onAction: _act),
            const SizedBox(height: Space.lg),
          ],
          SectionCard(
            title: 'Suggestion',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(d.description, style: theme.textTheme.bodyLarge),
                const SizedBox(height: Space.md),
                LabeledValue(label: 'Category', value: s.category),
                LabeledValue(label: 'Location', value: s.location),
                LabeledValue(label: 'Submitted', value: '${formatDateTime(s.createdAt)} by ${d.submittedBy}'),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () => CaseRoutes.openCase(context, s.id),
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('Open full case'),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: Space.md),
          SectionCard(title: 'Decision', child: _DecisionView(detail: d)),
          if (const {'accepted', 'planned', 'implemented'}.contains(s.status)) ...[
            const SizedBox(height: Space.md),
            SectionCard(title: 'Implementation', child: _ImplementationView(detail: d)),
          ],
          if (d.history.isNotEmpty) ...[
            const SizedBox(height: Space.md),
            SectionCard(title: 'Decision history', child: _HistoryView(history: d.history)),
          ],
        ],
      ),
    );
  }
}

class _ActionBar extends StatelessWidget {
  const _ActionBar({required this.actions, required this.onAction});
  final List<SuggestionAction> actions;
  final ValueChanged<SuggestionAction> onAction;

  @override
  Widget build(BuildContext context) {
    // One primary action, the rest outlined (clear hierarchy, few choices).
    final primary = actions.first;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FilledButton.icon(onPressed: () => onAction(primary), icon: Icon(primary.icon), label: Text(primary.label)),
        for (final a in actions.skip(1)) ...[
          const SizedBox(height: Space.sm),
          OutlinedButton.icon(onPressed: () => onAction(a), icon: Icon(a.icon), label: Text(a.label)),
        ],
      ],
    );
  }
}

class _DecisionView extends StatelessWidget {
  const _DecisionView({required this.detail});
  final SuggestionDetail detail;

  @override
  Widget build(BuildContext context) {
    final d = detail;
    if (d.decidedAt == null) {
      return Text(
        d.summary.status == 'under_evaluation'
            ? 'This suggestion is being evaluated. No decision has been made yet.'
            : 'No decision has been made yet.',
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LabeledValue(
          label: 'Decision',
          value: d.summary.status == 'declined' ? 'Declined' : 'Accepted for implementation',
        ),
        if (d.decisionReason.isNotEmpty) LabeledValue(label: 'Reason', value: d.decisionReason),
        LabeledValue(label: 'Decided', value: '${formatDateTime(d.decidedAt!)}${d.decidedBy != null ? ' by ${d.decidedBy}' : ''}'),
        if (d.summary.responsibleUnit != null)
          LabeledValue(label: 'Responsible unit', value: d.summary.responsibleUnit!.name),
      ],
    );
  }
}

class _ImplementationView extends StatelessWidget {
  const _ImplementationView({required this.detail});
  final SuggestionDetail detail;

  @override
  Widget build(BuildContext context) {
    final d = detail;
    final s = d.summary;
    final theme = Theme.of(context);
    final overdue = s.targetDate != null &&
        s.status != 'implemented' &&
        s.targetDate!.isBefore(DateUtils.dateOnly(DateTime.now()));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          label: 'Progress ${s.progressPercent} percent',
          excludeSemantics: true,
          child: Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: s.progressPercent / 100,
                    minHeight: 10,
                    color: s.status == 'implemented' ? UsjColors.success : UsjColors.blue,
                    backgroundColor: UsjColors.surfaceMuted,
                  ),
                ),
              ),
              const SizedBox(width: Space.md),
              Text('${s.progressPercent}%', style: theme.textTheme.titleMedium),
            ],
          ),
        ),
        const SizedBox(height: Space.md),
        if (s.targetDate != null)
          Row(
            children: [
              Expanded(child: LabeledValue(label: 'Target date', value: formatDate(s.targetDate!))),
              if (overdue) const OverdueBadge(),
            ],
          ),
        if (d.planNote.isNotEmpty) LabeledValue(label: 'Plan', value: d.planNote),
        if (d.implementedAt != null) LabeledValue(label: 'Implemented', value: formatDateTime(d.implementedAt!)),
        if (d.implementationSummary.isNotEmpty) LabeledValue(label: 'What was done', value: d.implementationSummary),
        if (d.progress.isNotEmpty) ...[
          const SizedBox(height: Space.sm),
          Text('Progress updates', style: theme.textTheme.titleSmall),
          const SizedBox(height: Space.sm),
          for (final p in d.progress.reversed)
            Padding(
              padding: const EdgeInsets.only(bottom: Space.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(p.note, style: theme.textTheme.bodyMedium),
                  Text(
                    '${formatDateTime(p.createdAt)} · ${p.author}'
                    '${p.percentComplete != null ? ' · ${p.percentComplete}%' : ''}',
                    style: theme.textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
                  ),
                ],
              ),
            ),
        ] else if (s.status != 'implemented')
          Text('No progress updates yet.', style: theme.textTheme.bodyMedium?.copyWith(color: UsjColors.textSecondary)),
      ],
    );
  }
}

class _HistoryView extends StatelessWidget {
  const _HistoryView({required this.history});
  final List<SuggestionHistoryEntry> history;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      children: [
        for (final h in history.reversed)
          Padding(
            padding: const EdgeInsets.only(bottom: Space.md),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Padding(
                  padding: EdgeInsets.only(top: 4),
                  child: Icon(Icons.circle, size: 10, color: UsjColors.textSecondary),
                ),
                const SizedBox(width: Space.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(h.toStatusLabel, style: theme.textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w600)),
                      if (h.reason.isNotEmpty) Text(h.reason, style: theme.textTheme.bodyMedium),
                      Text(
                        '${formatDateTime(h.createdAt)} · ${h.actor}',
                        style: theme.textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
