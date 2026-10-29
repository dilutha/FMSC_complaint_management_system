import 'package:flutter/material.dart';

import 'theme.dart';
import 'tokens.dart';
import 'usj_colors.dart';

/// A headline number with its definition (stat tile). The label states what
/// is counted so the number is never ambiguous.
class KpiTile extends StatelessWidget {
  const KpiTile({super.key, required this.label, required this.value, this.hint, this.onTap, this.alert = false});
  final String label;
  final String value;
  final String? hint;
  final VoidCallback? onTap;

  /// Draws attention (e.g. overdue > 0) with an icon and border, not colour alone.
  final bool alert;

  @override
  Widget build(BuildContext context) {
    final content = Padding(
      padding: const EdgeInsets.all(Space.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              if (alert) ...[
                const Icon(Icons.warning_amber_rounded, size: 16, color: UsjColors.error),
                const SizedBox(width: Space.xs),
              ],
              Expanded(child: Text(label, style: TextRoles.label(context), maxLines: 2)),
            ],
          ),
          const SizedBox(height: Space.xs),
          Text(value, style: TextRoles.kpiValue(context)),
          if (hint != null) ...[
            const SizedBox(height: 2),
            Text(hint!, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary)),
          ],
        ],
      ),
    );
    return Semantics(
      label: '$label: $value${hint != null ? ', $hint' : ''}',
      button: onTap != null,
      excludeSemantics: true,
      child: Card(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Radii.md),
          side: BorderSide(color: alert ? UsjColors.error : UsjColors.border),
        ),
        clipBehavior: Clip.antiAlias,
        child: onTap == null ? content : InkWell(onTap: onTap, child: content),
      ),
    );
  }
}

/// One labelled magnitude bar. Value is printed as text; the bar is a visual aid.
class BarRow extends StatelessWidget {
  const BarRow({super.key, required this.label, required this.count, required this.max, this.onTap});
  final String label;
  final int count;
  final int max;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final fraction = max <= 0 ? 0.0 : (count / max).clamp(0.0, 1.0);
    final row = Padding(
      padding: const EdgeInsets.symmetric(vertical: Space.xs),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(label, style: Theme.of(context).textTheme.bodyMedium)),
              Text(
                '$count',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
          const SizedBox(height: Space.xs),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: fraction,
              minHeight: 8,
              color: ChartColors.bar,
              backgroundColor: ChartColors.track,
            ),
          ),
        ],
      ),
    );
    return Semantics(
      label: '$label: $count',
      excludeSemantics: true,
      button: onTap != null,
      child: onTap == null ? row : InkWell(onTap: onTap, child: row),
    );
  }
}

/// A titled list of [BarRow]s with an empty state.
class BreakdownList extends StatelessWidget {
  const BreakdownList({super.key, required this.rows, this.hideZero = false, this.emptyText = 'No cases.'});
  final List<({String label, int count})> rows;
  final bool hideZero;
  final String emptyText;

  @override
  Widget build(BuildContext context) {
    final visible = hideZero ? rows.where((r) => r.count > 0).toList() : rows;
    if (visible.isEmpty || visible.every((r) => r.count == 0)) {
      return Text(emptyText, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: UsjColors.textSecondary));
    }
    final max = visible.map((r) => r.count).fold<int>(0, (a, b) => a > b ? a : b);
    return Column(children: [for (final r in visible) BarRow(label: r.label, count: r.count, max: max)]);
  }
}

class _SuggestionTone {
  const _SuggestionTone(this.fg, this.bg, this.icon);
  final Color fg;
  final Color bg;
  final IconData icon;
}

const _suggestionTones = <String, _SuggestionTone>{
  'submitted': _SuggestionTone(UsjColors.info, UsjColors.infoBg, Icons.outbox_outlined),
  'under_evaluation': _SuggestionTone(UsjColors.info, UsjColors.infoBg, Icons.manage_search),
  'accepted': _SuggestionTone(UsjColors.success, UsjColors.successBg, Icons.thumb_up_alt_outlined),
  'planned': _SuggestionTone(UsjColors.info, UsjColors.infoBg, Icons.event_outlined),
  'implemented': _SuggestionTone(UsjColors.success, UsjColors.successBg, Icons.task_alt),
  'declined': _SuggestionTone(UsjColors.neutral, UsjColors.neutralBg, Icons.block),
};

/// Suggestion status as icon + text (never colour alone).
class SuggestionStatusBadge extends StatelessWidget {
  const SuggestionStatusBadge({super.key, required this.status, required this.label});
  final String status;
  final String label;

  @override
  Widget build(BuildContext context) {
    final tone = _suggestionTones[status] ??
        const _SuggestionTone(UsjColors.neutral, UsjColors.neutralBg, Icons.circle_outlined);
    return Semantics(
      label: 'Suggestion status: $label',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: Space.sm, vertical: Space.xs),
        decoration: BoxDecoration(color: tone.bg, borderRadius: BorderRadius.circular(Radii.pill)),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(tone.icon, size: 16, color: tone.fg),
            const SizedBox(width: Space.xs),
            Flexible(
              child: Text(
                label,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: tone.fg, fontWeight: FontWeight.w600, fontSize: 13),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Shows a modal form sheet with consistent padding and keyboard handling.
Future<T?> showFormSheet<T>(BuildContext context, {required String title, required Widget child}) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    elevation: Elevations.overlay,
    builder: (context) => Padding(
      padding: EdgeInsets.only(
        left: Space.lg,
        right: Space.lg,
        bottom: MediaQuery.viewInsetsOf(context).bottom + Space.lg,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Semantics(header: true, child: Text(title, style: Theme.of(context).textTheme.titleLarge)),
            const SizedBox(height: Space.lg),
            child,
          ],
        ),
      ),
    ),
  );
}

/// Short confirmation feedback after a successful action.
void showSuccess(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message)));
}
