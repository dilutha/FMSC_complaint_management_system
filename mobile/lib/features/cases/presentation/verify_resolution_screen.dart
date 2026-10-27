import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/theme.dart';
import '../../../design/widgets.dart';
import '../case_scope.dart';
import '../data/models.dart';

/// Pops `true` when the case changed.
class VerifyResolutionScreen extends StatefulWidget {
  const VerifyResolutionScreen({super.key, required this.detail});
  final CaseDetail detail;

  @override
  State<VerifyResolutionScreen> createState() => _VerifyResolutionScreenState();
}

class _VerifyResolutionScreenState extends State<VerifyResolutionScreen> {
  bool? _resolved;
  final _feedback = TextEditingController();
  String? _feedbackError;
  String? _formError;
  bool _sending = false;

  @override
  void dispose() {
    _feedback.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_resolved == null) {
      setState(() => _formError = 'Choose one of the options above.');
      return;
    }
    if (_resolved == false && _feedback.text.trim().length < 5) {
      setState(() => _feedbackError = 'Tell us what is still wrong (at least 5 characters).');
      return;
    }
    setState(() {
      _sending = true;
      _feedbackError = null;
      _formError = null;
    });
    try {
      final updated = await CaseScope.of(
        context,
      ).repository.verifyResolution(widget.detail.id, confirmed: _resolved!, feedback: _feedback.text.trim());
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            updated.status == 'closed'
                ? 'Thank you. The case is now closed.'
                : 'Thank you. The case has been reopened and the team has been informed.',
          ),
        ),
      );
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _feedbackError = e.fieldError('feedback');
          _formError = _feedbackError == null ? e.message : null;
        });
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final res = widget.detail.latestResolution;
    return Scaffold(
      appBar: AppBar(title: const Text('Confirm resolution')),
      body: ListView(
        padding: const EdgeInsets.all(Space.lg),
        children: [
          if (res != null)
            SectionCard(
              title: 'What the team did',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(res.note),
                  const SizedBox(height: Space.sm),
                  Text('Marked solved ${formatDateTime(res.resolvedAt)}', style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
          const SizedBox(height: Space.lg),
          SectionCard(
            title: 'Is the issue resolved?',
            child: RadioGroup<bool>(
              groupValue: _resolved,
              onChanged: (v) {
                if (_sending) return;
                setState(() {
                  _resolved = v;
                  _formError = null;
                });
              },
              child: const Column(
                children: [
                  RadioListTile<bool>(
                    value: true,
                    title: Text('Yes, it is resolved'),
                    subtitle: Text('The case will be closed.'),
                    contentPadding: EdgeInsets.zero,
                  ),
                  RadioListTile<bool>(
                    value: false,
                    title: Text('No, the problem persists'),
                    subtitle: Text('The case will be reopened for further action.'),
                    contentPadding: EdgeInsets.zero,
                  ),
                ],
              ),
            ),
          ),
          if (_resolved == false) ...[
            const SizedBox(height: Space.lg),
            TextField(
              controller: _feedback,
              enabled: !_sending,
              minLines: 3,
              maxLines: 6,
              maxLength: 2000,
              decoration: InputDecoration(
                labelText: 'What is still wrong? *',
                alignLabelWithHint: true,
                errorText: _feedbackError,
              ),
            ),
          ],
          if (_formError != null)
            Padding(
              padding: const EdgeInsets.only(top: Space.sm),
              child: Text(_formError!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          const SizedBox(height: Space.lg),
          FilledButton(onPressed: _sending ? null : _submit, child: Text(_sending ? 'Sending…' : 'Submit response')),
        ],
      ),
    );
  }
}
