import 'package:flutter/material.dart';

import '../../../core/format.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../data/models.dart';

/// Vertical progress timeline, newest first.
class CaseTimeline extends StatelessWidget {
  const CaseTimeline({super.key, required this.entries});
  final List<TimelineEntry> entries;

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) return const Text('No activity yet.');
    final items = entries.reversed.toList();
    return Column(
      children: [
        for (var i = 0; i < items.length; i++)
          _TimelineRow(entry: items[i], isLast: i == items.length - 1, isLatest: i == 0),
      ],
    );
  }
}

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({required this.entry, required this.isLast, required this.isLatest});
  final TimelineEntry entry;
  final bool isLast;
  final bool isLatest;

  IconData get _icon => switch (entry.type) {
    'status_change' => Icons.flag_outlined,
    'assignment' => Icons.assignment_ind_outlined,
    'deadline_change' => Icons.event_outlined,
    'escalation' => Icons.warning_amber_outlined,
    _ => Icons.chat_bubble_outline,
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dotColor = isLatest ? UsjColors.red : UsjColors.textSecondary;
    return Semantics(
      container: true,
      label: '${entry.title}, ${formatDateTime(entry.at)}, by ${entry.actorName}. ${entry.body}',
      excludeSemantics: true,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: 32,
              child: Column(
                children: [
                  Icon(_icon, size: 20, color: dotColor),
                  if (!isLast) const Expanded(child: VerticalDivider(width: 2, thickness: 2, color: UsjColors.border)),
                ],
              ),
            ),
            const SizedBox(width: Space.sm),
            Expanded(
              child: Padding(
                padding: EdgeInsets.only(bottom: isLast ? 0 : Space.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      entry.title,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: isLatest ? FontWeight.w700 : FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${formatDateTime(entry.at)} · ${entry.actorName}',
                      style: theme.textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
                    ),
                    if (entry.body.isNotEmpty) ...[
                      const SizedBox(height: Space.xs),
                      Text(entry.body, style: theme.textTheme.bodyMedium),
                    ],
                    if (entry.attachmentIds.isNotEmpty) ...[
                      const SizedBox(height: Space.xs),
                      Text(
                        '${entry.attachmentIds.length} attachment(s) added',
                        style: theme.textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
