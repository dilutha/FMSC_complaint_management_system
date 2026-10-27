import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../case_scope.dart';
import '../data/models.dart';

/// Pops `true` when the case was reopened.
class ReopenCaseScreen extends StatefulWidget {
  const ReopenCaseScreen({super.key, required this.detail});
  final CaseDetail detail;

  @override
  State<ReopenCaseScreen> createState() => _ReopenCaseScreenState();
}

class _ReopenCaseScreenState extends State<ReopenCaseScreen> {
  final _formKey = GlobalKey<FormState>();
  final _reason = TextEditingController();
  bool _sending = false;
  String? _serverError;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() => _serverError = null);
    if (!_formKey.currentState!.validate()) return;
    setState(() => _sending = true);
    try {
      await CaseScope.of(context).repository.reopen(widget.detail.id, _reason.text.trim());
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Case reopened')));
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _serverError = e.fieldError('reason') ?? e.message);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Reopen ${widget.detail.caseNumber}')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(Space.lg),
          children: [
            const Text(
              'Reopen this case if the problem has come back or was not fully fixed. '
              'Your reason will be shared with the responsible unit.',
            ),
            const SizedBox(height: Space.lg),
            TextFormField(
              controller: _reason,
              enabled: !_sending,
              minLines: 3,
              maxLines: 6,
              maxLength: 2000,
              decoration: InputDecoration(
                labelText: 'Reason for reopening *',
                alignLabelWithHint: true,
                errorText: _serverError,
              ),
              validator: (v) => (v ?? '').trim().length < 5 ? 'Please explain why (at least 5 characters).' : null,
            ),
            const SizedBox(height: Space.lg),
            FilledButton.icon(
              onPressed: _sending ? null : _submit,
              icon: const Icon(Icons.replay),
              label: Text(_sending ? 'Reopening…' : 'Reopen case'),
            ),
            const SizedBox(height: Space.sm),
            OutlinedButton(
              onPressed: _sending ? null : () => Navigator.of(context).pop(false),
              child: const Text('Cancel'),
            ),
            const SizedBox(height: Space.md),
            const Text(
              'Note: closed cases can be reopened only for a limited period. After that, please submit a new case.',
              style: TextStyle(color: UsjColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}
