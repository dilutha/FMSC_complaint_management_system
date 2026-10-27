import 'package:flutter/material.dart';

import 'theme.dart';
import 'usj_colors.dart';

class _Tone {
  const _Tone(this.fg, this.bg, this.icon);
  final Color fg;
  final Color bg;
  final IconData icon;
}

const _statusTones = <String, _Tone>{
  'submitted': _Tone(UsjColors.info, UsjColors.infoBg, Icons.outbox_outlined),
  'under_review': _Tone(UsjColors.info, UsjColors.infoBg, Icons.manage_search),
  'waiting_for_information': _Tone(UsjColors.warning, UsjColors.warningBg, Icons.help_outline),
  'assigned': _Tone(UsjColors.info, UsjColors.infoBg, Icons.assignment_ind_outlined),
  'in_progress': _Tone(UsjColors.info, UsjColors.infoBg, Icons.construction_outlined),
  'solved': _Tone(UsjColors.success, UsjColors.successBg, Icons.task_alt),
  'closed': _Tone(UsjColors.neutral, UsjColors.neutralBg, Icons.lock_outline),
  'rejected': _Tone(UsjColors.error, UsjColors.errorBg, Icons.block),
  'reopened': _Tone(UsjColors.warning, UsjColors.warningBg, Icons.replay),
};

/// Status is always shown as icon + text, never colour alone (WCAG 1.4.1).
class StatusBadge extends StatelessWidget {
  const StatusBadge({super.key, required this.status, required this.label});
  final String status;
  final String label;

  @override
  Widget build(BuildContext context) {
    final tone = _statusTones[status] ?? const _Tone(UsjColors.neutral, UsjColors.neutralBg, Icons.circle_outlined);
    return _Pill(fg: tone.fg, bg: tone.bg, icon: tone.icon, label: label, semantics: 'Status: $label');
  }
}

class PriorityBadge extends StatelessWidget {
  const PriorityBadge({super.key, required this.priority});
  final String priority;

  @override
  Widget build(BuildContext context) {
    final urgent = priority == 'urgent';
    return _Pill(
      fg: urgent ? UsjColors.error : UsjColors.neutral,
      bg: urgent ? UsjColors.errorBg : UsjColors.neutralBg,
      icon: urgent ? Icons.priority_high : Icons.remove,
      label: urgent ? 'Urgent' : 'Normal',
      semantics: 'Priority: ${urgent ? 'Urgent' : 'Normal'}',
    );
  }
}

class OverdueBadge extends StatelessWidget {
  const OverdueBadge({super.key});

  @override
  Widget build(BuildContext context) => const _Pill(
    fg: UsjColors.error,
    bg: UsjColors.errorBg,
    icon: Icons.schedule,
    label: 'Overdue',
    semantics: 'Overdue',
  );
}

class _Pill extends StatelessWidget {
  const _Pill({required this.fg, required this.bg, required this.icon, required this.label, required this.semantics});
  final Color fg;
  final Color bg;
  final IconData icon;
  final String label;
  final String semantics;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: semantics,
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: Space.sm, vertical: Space.xs),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: fg),
            const SizedBox(width: Space.xs),
            Flexible(
              child: Text(
                label,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: fg, fontWeight: FontWeight.w600, fontSize: 13),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class LoadingView extends StatelessWidget {
  const LoadingView({super.key, this.message = 'Loading…'});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Semantics(
        liveRegion: true,
        label: message,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: Space.md),
            Text(message, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      ),
    );
  }
}

class MessageView extends StatelessWidget {
  const MessageView({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.actionLabel,
    this.onAction,
    this.isError = false,
  });

  final IconData icon;
  final String title;
  final String? message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool isError;

  factory MessageView.error({required String message, required VoidCallback onRetry}) => MessageView(
    icon: Icons.error_outline,
    title: 'Something went wrong',
    message: message,
    actionLabel: 'Try again',
    onAction: onRetry,
    isError: true,
  );

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(Space.xl),
        child: Semantics(
          liveRegion: isError,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 48, color: isError ? UsjColors.error : UsjColors.textSecondary),
              const SizedBox(height: Space.md),
              Text(title, style: theme.textTheme.titleMedium, textAlign: TextAlign.center),
              if (message != null) ...[
                const SizedBox(height: Space.sm),
                Text(
                  message!,
                  style: theme.textTheme.bodyMedium?.copyWith(color: UsjColors.textSecondary),
                  textAlign: TextAlign.center,
                ),
              ],
              if (actionLabel != null && onAction != null) ...[
                const SizedBox(height: Space.lg),
                FilledButton(onPressed: onAction, child: Text(actionLabel!)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Groups related information under a heading (Miller's law: chunking).
class SectionCard extends StatelessWidget {
  const SectionCard({super.key, required this.title, required this.child, this.trailing});
  final String title;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(Space.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Semantics(header: true, child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
                ),
                ?trailing,
              ],
            ),
            const SizedBox(height: Space.md),
            child,
          ],
        ),
      ),
    );
  }
}

class LabeledValue extends StatelessWidget {
  const LabeledValue({super.key, required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: Space.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: theme.textTheme.labelMedium?.copyWith(color: UsjColors.textSecondary)),
          const SizedBox(height: 2),
          Text(value, style: theme.textTheme.bodyLarge),
        ],
      ),
    );
  }
}

/// Official USJ logo, rendered with its original colours and aspect ratio.
class UsjLogo extends StatelessWidget {
  const UsjLogo({super.key, this.size = 40});
  final double size;

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      'assets/branding/usj_logo.png',
      width: size,
      height: size,
      fit: BoxFit.contain,
      semanticLabel: 'University of Sri Jayewardenepura logo',
    );
  }
}
