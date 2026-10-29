import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../case_scope.dart';
import '../data/models.dart';
import 'attachment_viewer_screen.dart';
import 'case_timeline.dart';
import 'reopen_case_screen.dart';
import 'verify_resolution_screen.dart';
import '../../staff/presentation/case_staff_actions.dart';

class CaseDetailScreen extends StatefulWidget {
  const CaseDetailScreen({super.key, required this.caseId});
  final int caseId;

  @override
  State<CaseDetailScreen> createState() => _CaseDetailScreenState();
}

class _CaseDetailScreenState extends State<CaseDetailScreen> {
  Future<(CaseDetail, List<TimelineEntry>)>? _future;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _future ??= _load();
  }

  Future<(CaseDetail, List<TimelineEntry>)> _load() async {
    final repo = CaseScope.of(context).repository;
    final results = await Future.wait([repo.getCase(widget.caseId), repo.getTimeline(widget.caseId)]);
    return (results[0] as CaseDetail, results[1] as List<TimelineEntry>);
  }

  Future<void> _refresh() async {
    final next = _load();
    setState(() {
      _future = next;
    });
    try {
      await next;
    } catch (_) {
      // Shown by the FutureBuilder's error state.
    }
  }

  Future<void> _push(Widget screen) async {
    final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => screen));
    if (changed == true && mounted) _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Case details')),
      body: FutureBuilder<(CaseDetail, List<TimelineEntry>)>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done && !snap.hasData) {
            return const LoadingView(message: 'Loading case…');
          }
          if (snap.hasError) {
            final e = snap.error;
            if (e is ApiException && e.statusCode == 404) {
              return const MessageView(
                icon: Icons.search_off,
                title: 'Case not found',
                message: 'It may have been removed, or you may not have access to it.',
              );
            }
            return MessageView.error(
              message: e is ApiException ? e.message : 'Could not load this case.',
              onRetry: _refresh,
            );
          }
          final (detail, timeline) = snap.data!;
          return RefreshIndicator(onRefresh: _refresh, child: _content(detail, timeline));
        },
      ),
    );
  }

  Widget _content(CaseDetail c, List<TimelineEntry> timeline) {
    final theme = Theme.of(context);
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(Space.lg),
      children: [
        Text(c.caseNumber, style: theme.textTheme.labelLarge?.copyWith(color: UsjColors.textSecondary)),
        const SizedBox(height: Space.xs),
        Semantics(header: true, child: Text(c.title, style: theme.textTheme.headlineSmall)),
        const SizedBox(height: Space.md),
        Wrap(
          spacing: Space.sm,
          runSpacing: Space.sm,
          children: [
            StatusBadge(status: c.status, label: c.statusLabel),
            PriorityBadge(priority: c.priority),
            if (c.isOverdue) const OverdueBadge(),
          ],
        ),
        // Member B: staff review, assignment and status actions (hidden for complainers).
        if (CaseStaffActions.shouldShow(context, c)) ...[
          const SizedBox(height: Space.lg),
          CaseStaffActions(detail: c, onChanged: _refresh),
        ],
        if (c.actions.canVerifyResolution) ...[
          const SizedBox(height: Space.lg),
          _VerifyBanner(
            detail: c,
            onRespond: () => _push(VerifyResolutionScreen(detail: c)),
          ),
        ],
        const SizedBox(height: Space.lg),
        SectionCard(
          title: 'Summary',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              LabeledValue(label: 'Type', value: c.caseTypeLabel),
              LabeledValue(label: 'Category', value: c.category.name),
              LabeledValue(label: 'Location', value: c.location),
              LabeledValue(label: 'Submitted', value: formatDateTime(c.createdAt)),
              LabeledValue(label: 'Responsible unit', value: c.assignedAuthority?.name ?? 'Not assigned yet'),
              if (c.deadlineAt != null && c.closedAt == null)
                LabeledValue(label: 'Target resolution date', value: formatDate(c.deadlineAt!)),
              if (c.requestedPriority != c.priority)
                LabeledValue(
                  label: 'Priority you requested',
                  value: c.requestedPriority == 'urgent' ? 'Urgent' : 'Normal',
                ),
            ],
          ),
        ),
        const SizedBox(height: Space.lg),
        SectionCard(
          title: 'Description',
          child: SelectableText(c.description, style: theme.textTheme.bodyLarge),
        ),
        if (c.latestResolution != null) ...[
          const SizedBox(height: Space.lg),
          SectionCard(
            title: 'Resolution',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(c.latestResolution!.note, style: theme.textTheme.bodyLarge),
                const SizedBox(height: Space.sm),
                Text('Recorded ${formatDateTime(c.latestResolution!.resolvedAt)}', style: theme.textTheme.bodySmall),
              ],
            ),
          ),
        ],
        const SizedBox(height: Space.lg),
        SectionCard(
          title: 'Attachments (${c.attachments.length})',
          child: c.attachments.isEmpty
              ? Text('No attachments.', style: theme.textTheme.bodyMedium?.copyWith(color: UsjColors.textSecondary))
              : Column(
                  children: [
                    for (final a in c.attachments)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(a.isImage ? Icons.image_outlined : Icons.videocam_outlined),
                        title: Text(a.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Text(
                          '${a.kind == 'completion' ? 'Completion evidence' : 'Evidence'} · ${formatBytes(a.size)}',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _push(AttachmentViewerScreen(attachment: a)),
                      ),
                  ],
                ),
        ),
        const SizedBox(height: Space.lg),
        SectionCard(
          title: 'Progress',
          child: CaseTimeline(entries: timeline),
        ),
        if (c.actions.canComment) ...[
          const SizedBox(height: Space.lg),
          _CommentBox(caseId: c.id, waitingForInfo: c.status == 'waiting_for_information', onPosted: _refresh),
        ],
        if (c.actions.canReopen && !c.actions.canVerifyResolution) ...[
          const SizedBox(height: Space.lg),
          OutlinedButton.icon(
            onPressed: () => _push(ReopenCaseScreen(detail: c)),
            icon: const Icon(Icons.replay),
            label: const Text('Problem returned? Reopen case'),
          ),
        ],
        const SizedBox(height: Space.xl),
      ],
    );
  }
}

class _VerifyBanner extends StatelessWidget {
  const _VerifyBanner({required this.detail, required this.onRespond});
  final CaseDetail detail;
  final VoidCallback onRespond;

  @override
  Widget build(BuildContext context) {
    final due = detail.verificationDueAt;
    return Container(
      padding: const EdgeInsets.all(Space.lg),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBE0),
        border: const Border(left: BorderSide(color: UsjColors.gold, width: 4)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Is the issue resolved?', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: Space.xs),
          Text(
            due == null
                ? 'Please confirm the resolution or tell us if the problem persists.'
                : 'Please respond by ${formatDate(due)}. If we do not hear from you, the case will close automatically.',
          ),
          const SizedBox(height: Space.md),
          FilledButton(onPressed: onRespond, child: const Text('Respond')),
        ],
      ),
    );
  }
}

class _CommentBox extends StatefulWidget {
  const _CommentBox({required this.caseId, required this.waitingForInfo, required this.onPosted});
  final int caseId;
  final bool waitingForInfo;
  final Future<void> Function() onPosted;

  @override
  State<_CommentBox> createState() => _CommentBoxState();
}

class _CommentBoxState extends State<_CommentBox> {
  final _controller = TextEditingController();
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty) {
      setState(() => _error = 'Enter a message first.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await CaseScope.of(
        context,
      ).repository.addComment(widget.caseId, text, kind: widget.waitingForInfo ? 'information_response' : 'comment');
      _controller.clear();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Message added')));
      await widget.onPosted();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.fieldError('body') ?? e.message);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: widget.waitingForInfo ? 'Provide the requested information' : 'Add a message',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _controller,
            enabled: !_sending,
            minLines: 2,
            maxLines: 5,
            maxLength: 5000,
            decoration: InputDecoration(labelText: 'Message', errorText: _error),
          ),
          const SizedBox(height: Space.sm),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton(onPressed: _sending ? null : _send, child: Text(_sending ? 'Sending…' : 'Send')),
          ),
        ],
      ),
    );
  }
}
