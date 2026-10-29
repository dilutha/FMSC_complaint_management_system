import 'package:flutter/material.dart';

import '../../../core/format.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/paged_list.dart';
import '../../../platform/platform_routes.dart';
import '../../../platform/platform_scope.dart';
import '../data/suggestions.dart';

/// Five filters only (Hick's law); each maps to suggestion status values.
enum SuggestionFilter {
  toEvaluate('To evaluate', 'submitted,under_evaluation'),
  inImplementation('In implementation', 'accepted,planned'),
  implemented('Implemented', 'implemented'),
  declined('Declined', 'declined'),
  all('All', null);

  const SuggestionFilter(this.label, this.statuses);
  final String label;
  final String? statuses;
}

class SuggestionsScreen extends StatefulWidget {
  const SuggestionsScreen({super.key});

  @override
  State<SuggestionsScreen> createState() => _SuggestionsScreenState();
}

class _SuggestionsScreenState extends State<SuggestionsScreen> {
  SuggestionFilter _filter = SuggestionFilter.toEvaluate;
  int _reload = 0;

  @override
  Widget build(BuildContext context) {
    final repo = PlatformScope.of(context).suggestions;
    return Scaffold(
      appBar: AppBar(title: const Text('Suggestions')),
      body: Column(
        children: [
          SizedBox(
            height: kMinTouchTarget + Space.lg,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.sm),
              children: [
                for (final f in SuggestionFilter.values)
                  Padding(
                    padding: const EdgeInsets.only(right: Space.sm),
                    child: ChoiceChip(
                      label: Text(f.label),
                      selected: f == _filter,
                      onSelected: (_) => setState(() => _filter = f),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: PagedList<SuggestionSummary>(
              reloadKey: (_filter, _reload),
              loadingMessage: 'Loading suggestions…',
              load: (page) => repo.list(page: page, statuses: _filter.statuses),
              empty: MessageView(
                icon: Icons.lightbulb_outline,
                title: 'No suggestions here',
                message: _filter == SuggestionFilter.toEvaluate ? 'Nothing is waiting for a decision.' : null,
              ),
              itemBuilder: (context, s, _) => _SuggestionTile(
                suggestion: s,
                onTap: () async {
                  await PlatformRoutes.openSuggestion(context, s.id);
                  if (mounted) setState(() => _reload++);
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SuggestionTile extends StatelessWidget {
  const _SuggestionTile({required this.suggestion, required this.onTap});
  final SuggestionSummary suggestion;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final s = suggestion;
    final theme = Theme.of(context);
    final details = [
      s.caseNumber,
      s.category,
      if (s.responsibleUnit != null) s.responsibleUnit!.name,
      if (s.targetDate != null) 'Target ${formatDate(s.targetDate!)}',
    ].join(' · ');
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.md),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(s.title, style: theme.textTheme.titleMedium, maxLines: 2, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: Space.xs),
                  Text(details, style: theme.textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary)),
                  const SizedBox(height: Space.sm),
                  SuggestionStatusBadge(status: s.status, label: s.statusLabel),
                ],
              ),
            ),
            const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }
}
