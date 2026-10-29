import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/platform_scope.dart';
import '../../cases/data/models.dart';

/// Server minimums (apps/cases/services/workflow.py).
const minStaffMessage = 5;
const minResolutionNote = 10;

const _statusLabels = {
  'under_review': 'Under review',
  'waiting_for_information': 'Waiting for information',
  'in_progress': 'In progress',
  'solved': 'Resolved (record resolution)',
  'closed': 'Closed',
  'rejected': 'Rejected',
  'reopened': 'Reopened',
};

/// Staff actions shown inside the case-detail screen (Member A's screen hosts it):
/// case administrators review, assign and change status; the assigned
/// department changes status. Every change requires a message, saved by the
/// server in the same transaction as the change. Only actions listed in the
/// server's `allowed_actions` are offered.
class CaseStaffActions extends StatelessWidget {
  const CaseStaffActions({super.key, required this.detail, required this.onChanged});
  final CaseDetail detail;
  final VoidCallback onChanged;

  /// Statuses this user may move the case to (excluding assignment, which has its own form).
  static List<String> statusTargets(CaseDetail c) =>
      [for (final t in c.actions.transitions) if (t != 'assigned') t];

  static bool shouldShow(BuildContext context, CaseDetail c) {
    final user = PlatformScope.maybeOf(context)?.session.user;
    if (user == null || user.isComplainer) return false;
    return c.actions.canAssign || statusTargets(c).isNotEmpty;
  }

  @override
  Widget build(BuildContext context) {
    final targets = statusTargets(detail);
    final reassign = detail.assignedAuthority != null;
    return SectionCard(
      title: 'Case actions',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Each action is recorded in the case history with your message.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
          ),
          const SizedBox(height: Space.md),
          if (detail.actions.canAssign)
            FilledButton.icon(
              icon: const Icon(Icons.assignment_ind_outlined),
              label: Text(reassign ? 'Reassign to another department' : 'Assign to a department'),
              onPressed: () async {
                final ok = await showFormSheet<bool>(
                  context,
                  title: reassign ? 'Reassign case' : 'Assign case',
                  child: _AssignForm(detail: detail),
                );
                if (ok == true && context.mounted) {
                  showSuccess(context, 'Case assigned. The department can now see it.');
                  onChanged();
                }
              },
            ),
          if (detail.actions.canAssign && targets.isNotEmpty) const SizedBox(height: Space.sm),
          if (targets.isNotEmpty)
            OutlinedButton.icon(
              icon: const Icon(Icons.published_with_changes),
              label: const Text('Update status'),
              onPressed: () async {
                final ok = await showFormSheet<bool>(
                  context,
                  title: 'Update status',
                  child: _StatusForm(detail: detail, targets: targets),
                );
                if (ok == true && context.mounted) {
                  showSuccess(context, 'Status updated and message recorded.');
                  onChanged();
                }
              },
            ),
        ],
      ),
    );
  }
}

String? _minLength(String? v, int min, String empty) {
  final text = (v ?? '').trim();
  if (text.isEmpty) return empty;
  if (text.length < min) return 'Enter at least $min characters.';
  return null;
}

class _AssignForm extends StatefulWidget {
  const _AssignForm({required this.detail});
  final CaseDetail detail;

  @override
  State<_AssignForm> createState() => _AssignFormState();
}

class _AssignFormState extends State<_AssignForm> {
  final _formKey = GlobalKey<FormState>();
  final _message = TextEditingController();
  final _note = TextEditingController();
  List<({int id, String name})>? _departments;
  int? _department;
  ApiException? _error;
  bool _busy = false;
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
    try {
      final all = await PlatformScope.of(context).staffCases.departments();
      if (mounted) {
        setState(() => _departments = [
              for (final d in all) if (d.id != widget.detail.assignedAuthority?.id) d,
            ]);
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  @override
  void dispose() {
    _message.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy || !_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await PlatformScope.of(context).staffCases.assign(
        widget.detail.id,
        departmentId: _department!,
        message: _message.text.trim(),
        internalNote: _note.text,
      );
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final departments = _departments;
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('${widget.detail.caseNumber} · ${widget.detail.title}', style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: Space.md),
          if (departments == null && _error == null) const LinearProgressIndicator(),
          if (departments != null)
            DropdownButtonFormField<int>(
              initialValue: _department,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: 'Resolving department',
                errorText: _error?.fieldError('authority_id'),
              ),
              items: [for (final d in departments) DropdownMenuItem(value: d.id, child: Text(d.name))],
              onChanged: _busy ? null : (v) => setState(() => _department = v),
              validator: (v) => v == null ? 'Choose the department that will resolve this case.' : null,
            ),
          const SizedBox(height: Space.md),
          TextFormField(
            controller: _message,
            enabled: !_busy,
            minLines: 2,
            maxLines: 5,
            maxLength: 2000,
            decoration: InputDecoration(
              labelText: 'Assignment message',
              helperText: 'Why this department? Shown in the case history to everyone following the case.',
              errorText: _error?.fieldError('message'),
              alignLabelWithHint: true,
            ),
            validator: (v) => _minLength(v, minStaffMessage, 'An assignment message is required.'),
          ),
          TextFormField(
            controller: _note,
            enabled: !_busy,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'Internal note (optional, staff only)'),
          ),
          if (_error != null && _error!.details.isEmpty) ...[
            const SizedBox(height: Space.md),
            Text(_error!.message, style: const TextStyle(color: UsjColors.error)),
          ],
          const SizedBox(height: Space.lg),
          FilledButton(onPressed: _busy ? null : _submit, child: Text(_busy ? 'Assigning…' : 'Assign case')),
        ],
      ),
    );
  }
}

class _StatusForm extends StatefulWidget {
  const _StatusForm({required this.detail, required this.targets});
  final CaseDetail detail;
  final List<String> targets;

  @override
  State<_StatusForm> createState() => _StatusFormState();
}

class _StatusFormState extends State<_StatusForm> {
  final _formKey = GlobalKey<FormState>();
  final _message = TextEditingController();
  late String _target = widget.targets.first;
  ApiException? _error;
  bool _busy = false;

  bool get _resolving => _target == 'solved';

  @override
  void dispose() {
    _message.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy || !_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final text = _message.text.trim();
    try {
      await PlatformScope.of(context).staffCases.changeStatus(
        widget.detail.id,
        toStatus: _target,
        message: _resolving ? '' : text,
        resolutionNote: _resolving ? text : '',
      );
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              const Text('Current: '),
              StatusBadge(status: widget.detail.status, label: widget.detail.statusLabel),
            ],
          ),
          const SizedBox(height: Space.md),
          DropdownButtonFormField<String>(
            initialValue: _target,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'New status'),
            items: [
              for (final t in widget.targets) DropdownMenuItem(value: t, child: Text(_statusLabels[t] ?? t)),
            ],
            onChanged: _busy ? null : (v) => setState(() => _target = v!),
          ),
          const SizedBox(height: Space.md),
          TextFormField(
            controller: _message,
            enabled: !_busy,
            minLines: 3,
            maxLines: 6,
            maxLength: _resolving ? 5000 : 2000,
            decoration: InputDecoration(
              labelText: _resolving ? 'Resolution details' : 'Message explaining this update',
              helperText: _resolving
                  ? 'What was done. The complainant is asked to confirm it.'
                  : 'Saved with the status change and shown in the case history.',
              errorText: _error?.fieldError(_resolving ? 'resolution_note' : 'reason'),
              alignLabelWithHint: true,
            ),
            validator: (v) => _resolving
                ? _minLength(v, minResolutionNote, 'Describe how the case was resolved.')
                : _minLength(v, minStaffMessage, 'A message is required for every status change.'),
          ),
          if (_error != null && _error!.details.isEmpty) ...[
            const SizedBox(height: Space.md),
            Text(_error!.message, style: const TextStyle(color: UsjColors.error)),
          ],
          const SizedBox(height: Space.lg),
          FilledButton(onPressed: _busy ? null : _submit, child: Text(_busy ? 'Saving…' : 'Save update')),
        ],
      ),
    );
  }
}
