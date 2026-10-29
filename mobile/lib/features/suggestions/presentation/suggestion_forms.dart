import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../platform/platform_scope.dart';
import '../data/suggestions.dart';

/// Minimum reason length; matches the server rule (MIN_REASON = 10).
const minReasonLength = 10;

enum SuggestionAction {
  startEvaluation('start_evaluation', 'Start evaluation', Icons.manage_search, 'Evaluation started.'),
  accept('accept', 'Accept for implementation', Icons.thumb_up_alt_outlined, 'Suggestion accepted.'),
  plan('plan', 'Set target date', Icons.event_outlined, 'Plan saved.'),
  recordProgress('record_progress', 'Add progress update', Icons.trending_up, 'Progress recorded.'),
  markImplemented('mark_implemented', 'Mark as implemented', Icons.task_alt, 'Marked as implemented.'),
  decline('decline', 'Decline', Icons.block, 'Suggestion declined.'),
  reconsider('reconsider', 'Reconsider', Icons.replay, 'Suggestion reopened for evaluation.');

  const SuggestionAction(this.apiName, this.label, this.icon, this.successMessage);
  final String apiName;
  final String label;
  final IconData icon;
  final String successMessage;
}

/// Shows the form for [action]; returns the updated suggestion, or null if cancelled.
Future<SuggestionDetail?> runSuggestionAction(BuildContext context, SuggestionDetail detail, SuggestionAction action) {
  return showFormSheet<SuggestionDetail>(
    context,
    title: action.label,
    child: _ActionForm(detail: detail, action: action),
  );
}

class _ActionForm extends StatefulWidget {
  const _ActionForm({required this.detail, required this.action});
  final SuggestionDetail detail;
  final SuggestionAction action;

  @override
  State<_ActionForm> createState() => _ActionFormState();
}

class _ActionFormState extends State<_ActionForm> {
  final _formKey = GlobalKey<FormState>();
  final _text = TextEditingController();
  DateTime? _date;
  int? _unitId;
  double _percent = 0;
  bool _includePercent = false;
  List<({int id, String name})>? _units;
  ApiException? _error;
  bool _busy = false;

  SuggestionAction get _action => widget.action;

  @override
  void initState() {
    super.initState();
    _date = widget.detail.summary.targetDate;
    _unitId = widget.detail.summary.responsibleUnit?.id;
    _percent = widget.detail.summary.progressPercent.clamp(0, 99).toDouble();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_action == SuggestionAction.accept && _units == null) _loadUnits();
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _loadUnits() async {
    try {
      final units = await PlatformScope.of(context).suggestions.units();
      if (mounted) setState(() => _units = units);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _pickDate() async {
    final today = DateUtils.dateOnly(DateTime.now());
    final picked = await showDatePicker(
      context: context,
      initialDate: _date != null && !_date!.isBefore(today) ? _date! : today,
      firstDate: today, // the server rejects past dates too
      lastDate: today.add(const Duration(days: 365 * 3)),
      helpText: 'Target completion date',
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final repo = PlatformScope.of(context).suggestions;
    final id = widget.detail.summary.id;
    final text = _text.text.trim();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = switch (_action) {
        SuggestionAction.startEvaluation => await repo.decide(id, 'start_evaluation'),
        SuggestionAction.accept => await repo.decide(id, 'accept', unitId: _unitId, reason: text, targetDate: _date),
        SuggestionAction.decline => await repo.decide(id, 'decline', reason: text),
        SuggestionAction.reconsider => await repo.decide(id, 'reconsider', reason: text),
        SuggestionAction.plan => await repo.plan(id, targetDate: _date!, note: text),
        SuggestionAction.recordProgress =>
          await repo.recordProgress(id, note: text, percent: _includePercent ? _percent.round() : null),
        SuggestionAction.markImplemented => await repo.markImplemented(id, text),
      };
      if (mounted) Navigator.pop(context, result);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String? _required(String? v, String message, {int min = 1}) {
    final value = (v ?? '').trim();
    if (value.isEmpty) return message;
    if (value.length < min) return 'Enter at least $min characters.';
    return null;
  }

  Widget _textField({required String label, String? helper, String? Function(String?)? validator, String? field}) =>
      TextFormField(
        controller: _text,
        enabled: !_busy,
        minLines: 3,
        maxLines: 6,
        maxLength: 2000,
        decoration: InputDecoration(
          labelText: label,
          helperText: helper,
          alignLabelWithHint: true,
          errorText: field == null ? null : _error?.fieldError(field),
        ),
        validator: validator,
      );

  List<Widget> _fields() {
    switch (_action) {
      case SuggestionAction.startEvaluation:
        return [const Text('The submitter will be told that their suggestion is being evaluated.')];
      case SuggestionAction.accept:
        return [
          if (_units == null && _error == null) const LinearProgressIndicator(),
          if (_units != null)
            DropdownButtonFormField<int>(
              initialValue: _unitId,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: 'Responsible unit',
                errorText: _error?.fieldError('responsible_unit_id'),
              ),
              items: [for (final u in _units!) DropdownMenuItem(value: u.id, child: Text(u.name))],
              onChanged: _busy ? null : (v) => setState(() => _unitId = v),
              validator: (v) => v == null ? 'Choose the unit that will implement it.' : null,
            ),
          const SizedBox(height: Space.md),
          _dateField(optional: true),
          const SizedBox(height: Space.md),
          _textField(label: 'Decision note (optional)', helper: 'Shared with the responsible unit.'),
        ];
      case SuggestionAction.decline:
      case SuggestionAction.reconsider:
        return [
          _textField(
            label: 'Reason',
            field: 'reason',
            helper: _action == SuggestionAction.decline
                ? 'The submitter will see this reason.'
                : 'Why the suggestion is being evaluated again.',
            validator: (v) => _required(v, 'A reason is required.', min: minReasonLength),
          ),
        ];
      case SuggestionAction.plan:
        return [
          _dateField(optional: false),
          const SizedBox(height: Space.md),
          _textField(label: 'Plan (optional)', helper: 'What will be done and by whom.'),
        ];
      case SuggestionAction.recordProgress:
        return [
          _textField(label: 'Progress update', field: 'note', validator: (v) => _required(v, 'Describe the progress made.')),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Record percentage complete'),
            value: _includePercent,
            onChanged: _busy ? null : (v) => setState(() => _includePercent = v),
          ),
          if (_includePercent)
            Row(
              children: [
                Expanded(
                  child: Slider(
                    value: _percent,
                    max: 99,
                    divisions: 99,
                    label: '${_percent.round()}%',
                    semanticFormatterCallback: (v) => '${v.round()} percent',
                    onChanged: _busy ? null : (v) => setState(() => _percent = v),
                  ),
                ),
                SizedBox(width: 48, child: Text('${_percent.round()}%', textAlign: TextAlign.end)),
              ],
            ),
          Text(
            'Use “Mark as implemented” when the work is complete.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
          ),
        ];
      case SuggestionAction.markImplemented:
        return [
          _textField(
            label: 'What was implemented',
            field: 'summary',
            helper: 'The submitter is asked to confirm this, as with a solved case.',
            validator: (v) => _required(v, 'Describe what was implemented.', min: minReasonLength),
          ),
        ];
    }
  }

  Widget _dateField({required bool optional}) => FormField<DateTime>(
    initialValue: _date,
    validator: (_) => !optional && _date == null ? 'Choose a target date.' : null,
    builder: (state) => InputDecorator(
      decoration: InputDecoration(
        labelText: optional ? 'Target date (optional)' : 'Target date',
        errorText: state.errorText ?? _error?.fieldError('target_date'),
        suffixIcon: const Icon(Icons.calendar_today_outlined),
      ),
      child: InkWell(
        onTap: _busy ? null : _pickDate,
        child: Semantics(
          button: true,
          label: 'Target date: ${_date == null ? 'not set' : formatDate(_date!)}. Tap to choose.',
          excludeSemantics: true,
          child: SizedBox(
            height: 24,
            child: Text(_date == null ? 'Choose a date' : formatDate(_date!)),
          ),
        ),
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final generalError = _error != null && _error!.details.isEmpty ? _error!.message : null;
    final destructive = _action == SuggestionAction.decline;
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          ..._fields(),
          if (generalError != null) ...[
            const SizedBox(height: Space.md),
            Semantics(liveRegion: true, child: Text(generalError, style: const TextStyle(color: UsjColors.error))),
          ],
          const SizedBox(height: Space.xl),
          FilledButton(
            onPressed: _busy ? null : _submit,
            style: destructive ? FilledButton.styleFrom(backgroundColor: UsjColors.maroon) : null,
            child: Text(_busy ? 'Saving…' : _action.label),
          ),
          const SizedBox(height: Space.sm),
          TextButton(onPressed: _busy ? null : () => Navigator.pop(context), child: const Text('Cancel')),
        ],
      ),
    );
  }
}
