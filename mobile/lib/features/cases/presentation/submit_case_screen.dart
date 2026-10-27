import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../case_scope.dart';
import '../data/models.dart';
import 'submission_confirmation_screen.dart';

class SubmitCaseScreen extends StatefulWidget {
  const SubmitCaseScreen({super.key});

  @override
  State<SubmitCaseScreen> createState() => _SubmitCaseScreenState();
}

class _SubmitCaseScreenState extends State<SubmitCaseScreen> {
  final _formKey = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _description = TextEditingController();
  final _location = TextEditingController();

  String _caseType = 'complaint';
  String _priority = 'normal';
  int? _categoryId;
  bool _declaration = false;
  bool _declarationError = false;
  final _files = <UploadFile>[];

  late Future<(List<Category>, CaseOptions)> _setup;
  bool _submitting = false;
  ApiException? _serverError;
  bool _initialised = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialised) {
      _initialised = true;
      _setup = _load();
    }
  }

  Future<(List<Category>, CaseOptions)> _load() async {
    final repo = CaseScope.of(context).repository;
    return (await repo.getCategories(), await repo.getOptions());
  }

  @override
  void dispose() {
    _title.dispose();
    _description.dispose();
    _location.dispose();
    super.dispose();
  }

  String? _server(String field) => _serverError?.fieldError(field);

  Future<void> _pickFiles(AttachmentLimits limits) async {
    final picked = await CaseScope.of(context).pickAttachments(allowedExtensions: limits.allowedExtensions);
    if (!mounted || picked.isEmpty) return;
    final problems = <String>[];
    setState(() {
      for (final f in picked) {
        final problem = limits.validate(f.name, f.size);
        if (problem != null) {
          problems.add(problem);
        } else if (_files.length >= limits.maxPerCase) {
          problems.add('You can attach up to ${limits.maxPerCase} files.');
          break;
        } else {
          _files.add(f);
        }
      }
    });
    if (problems.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(problems.join('\n'))));
    }
  }

  Future<void> _submit() async {
    setState(() {
      _serverError = null;
      _declarationError = !_declaration;
    });
    final valid = _formKey.currentState!.validate();
    if (!valid || !_declaration) return;

    setState(() => _submitting = true);
    try {
      final created = await CaseScope.of(context).repository.submitCase(
        NewCase(
          caseType: _caseType,
          categoryId: _categoryId!,
          title: _title.text.trim(),
          description: _description.text.trim(),
          location: _location.text.trim(),
          priority: _priority,
          declarationAccepted: _declaration,
        ),
        List.of(_files),
      );
      if (!mounted) return;
      Navigator.of(
        context,
      ).pushReplacement(MaterialPageRoute(builder: (_) => SubmissionConfirmationScreen(created: created)));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _serverError = e);
      _formKey.currentState!.validate(); // show server field errors inline
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Submit a case')),
      body: FutureBuilder<(List<Category>, CaseOptions)>(
        future: _setup,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const LoadingView(message: 'Preparing form…');
          if (snap.hasError) {
            final message = snap.error is ApiException
                ? (snap.error as ApiException).message
                : 'Could not load the form.';
            return MessageView.error(
              message: message,
              onRetry: () => setState(() {
                _setup = _load();
              }),
            );
          }
          final (categories, options) = snap.data!;
          return _form(categories, options);
        },
      ),
    );
  }

  Widget _form(List<Category> categories, CaseOptions options) {
    final theme = Theme.of(context);
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(Space.lg),
        children: [
          SectionCard(
            title: 'What are you reporting?',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Type', style: theme.textTheme.labelLarge),
                const SizedBox(height: Space.sm),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'complaint', label: Text('Complaint'), icon: Icon(Icons.report_outlined)),
                    ButtonSegment(value: 'suggestion', label: Text('Suggestion'), icon: Icon(Icons.lightbulb_outline)),
                  ],
                  selected: {_caseType},
                  onSelectionChanged: _submitting ? null : (v) => setState(() => _caseType = v.first),
                ),
                const SizedBox(height: Space.lg),
                Text('Priority', style: theme.textTheme.labelLarge),
                const SizedBox(height: Space.sm),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'normal', label: Text('Normal')),
                    ButtonSegment(value: 'urgent', label: Text('Urgent'), icon: Icon(Icons.priority_high)),
                  ],
                  selected: {_priority},
                  onSelectionChanged: _submitting ? null : (v) => setState(() => _priority = v.first),
                ),
                const SizedBox(height: Space.xs),
                Text(
                  'Choose Urgent only for safety risks or issues stopping teaching or exams. '
                  'An administrator may adjust it.',
                  style: theme.textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(height: Space.lg),
          SectionCard(
            title: 'Details',
            child: Column(
              children: [
                DropdownButtonFormField<int>(
                  initialValue: _categoryId,
                  decoration: InputDecoration(labelText: 'Category *', errorText: _server('category_id')),
                  items: [for (final c in categories) DropdownMenuItem(value: c.id, child: Text(c.name))],
                  onChanged: _submitting ? null : (v) => setState(() => _categoryId = v),
                  validator: (v) => v == null ? 'Choose a category.' : null,
                ),
                const SizedBox(height: Space.lg),
                TextFormField(
                  controller: _location,
                  enabled: !_submitting,
                  textInputAction: TextInputAction.next,
                  maxLength: 200,
                  decoration: InputDecoration(
                    labelText: 'Location *',
                    hintText: 'e.g. Building B, Room 204',
                    errorText: _server('location'),
                  ),
                  validator: (v) => (v ?? '').trim().length < 2 ? 'Tell us where the issue is.' : null,
                ),
                const SizedBox(height: Space.sm),
                TextFormField(
                  controller: _title,
                  enabled: !_submitting,
                  textInputAction: TextInputAction.next,
                  maxLength: 150,
                  decoration: InputDecoration(
                    labelText: 'Title *',
                    hintText: 'A short summary',
                    errorText: _server('title'),
                  ),
                  validator: (v) => (v ?? '').trim().length < 5 ? 'Use at least 5 characters.' : null,
                ),
                const SizedBox(height: Space.sm),
                TextFormField(
                  controller: _description,
                  enabled: !_submitting,
                  minLines: 4,
                  maxLines: 8,
                  maxLength: 5000,
                  decoration: InputDecoration(
                    labelText: 'Description *',
                    hintText: 'What happened, when, and how it affects you',
                    alignLabelWithHint: true,
                    errorText: _server('description'),
                  ),
                  validator: (v) =>
                      (v ?? '').trim().length < 10 ? 'Describe the issue in at least 10 characters.' : null,
                ),
              ],
            ),
          ),
          const SizedBox(height: Space.lg),
          SectionCard(title: 'Evidence (optional)', child: _attachments(options.attachments)),
          const SizedBox(height: Space.lg),
          _declarationTile(),
          const SizedBox(height: Space.lg),
          FilledButton.icon(
            onPressed: _submitting ? null : _submit,
            icon: _submitting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.send),
            label: Text(_submitting ? 'Submitting…' : 'Submit case'),
          ),
          const SizedBox(height: Space.sm),
          OutlinedButton(
            onPressed: _submitting ? null : () => Navigator.of(context).maybePop(),
            child: const Text('Cancel'),
          ),
          const SizedBox(height: Space.xl),
        ],
      ),
    );
  }

  Widget _attachments(AttachmentLimits limits) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Photos (${limits.maxImageBytes ~/ (1024 * 1024)} MB max) or videos '
          '(${limits.maxVideoBytes ~/ (1024 * 1024)} MB max). Up to ${limits.maxPerCase} files.',
          style: theme.textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
        ),
        const SizedBox(height: Space.sm),
        for (var i = 0; i < _files.length; i++)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(
              AttachmentLimits.imageExtensions.contains(_files[i].name.split('.').last.toLowerCase())
                  ? Icons.image_outlined
                  : Icons.videocam_outlined,
            ),
            title: Text(_files[i].name, maxLines: 1, overflow: TextOverflow.ellipsis),
            subtitle: Text(formatBytes(_files[i].size)),
            trailing: IconButton(
              tooltip: 'Remove ${_files[i].name}',
              icon: const Icon(Icons.close),
              onPressed: _submitting ? null : () => setState(() => _files.removeAt(i)),
            ),
          ),
        OutlinedButton.icon(
          onPressed: _submitting || _files.length >= limits.maxPerCase ? null : () => _pickFiles(limits),
          icon: const Icon(Icons.attach_file),
          label: const Text('Add photo or video'),
        ),
        if (_server('attachments') != null)
          Padding(
            padding: const EdgeInsets.only(top: Space.sm),
            child: Text(_server('attachments')!, style: const TextStyle(color: UsjColors.error)),
          ),
      ],
    );
  }

  Widget _declarationTile() {
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CheckboxListTile(
            value: _declaration,
            onChanged: _submitting
                ? null
                : (v) => setState(() {
                    _declaration = v ?? false;
                    if (_declaration) _declarationError = false;
                  }),
            controlAffinity: ListTileControlAffinity.leading,
            title: const Text('I confirm that the information submitted is accurate to the best of my knowledge.'),
          ),
          if (_declarationError || _server('declaration_accepted') != null)
            const Padding(
              padding: EdgeInsets.fromLTRB(Space.lg, 0, Space.lg, Space.md),
              child: Text('Please confirm the declaration to submit.', style: TextStyle(color: UsjColors.error)),
            ),
        ],
      ),
    );
  }
}
