import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../core/format.dart';
import '../../../design/theme.dart';
import '../../../design/widgets.dart';
import '../case_scope.dart';
import '../data/models.dart';
import 'attachment_saver.dart';

/// Attachments are fetched through the authenticated API (never a public URL).
class AttachmentViewerScreen extends StatefulWidget {
  const AttachmentViewerScreen({super.key, required this.attachment});
  final Attachment attachment;

  @override
  State<AttachmentViewerScreen> createState() => _AttachmentViewerScreenState();
}

class _AttachmentViewerScreenState extends State<AttachmentViewerScreen> {
  Future<Uint8List>? _bytes;
  bool _saving = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _bytes ??= _load();
  }

  Future<Uint8List> _load() async =>
      Uint8List.fromList(await CaseScope.of(context).repository.downloadAttachment(widget.attachment));

  Future<void> _save(Uint8List bytes) async {
    setState(() => _saving = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final location = await saveAttachment(widget.attachment.name, bytes);
      messenger.showSnackBar(SnackBar(content: Text('Saved to $location')));
    } catch (_) {
      messenger.showSnackBar(const SnackBar(content: Text('Could not save the file on this device.')));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.attachment;
    return Scaffold(
      appBar: AppBar(title: Text(a.name, overflow: TextOverflow.ellipsis)),
      body: FutureBuilder<Uint8List>(
        future: _bytes,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const LoadingView(message: 'Downloading…');
          if (snap.hasError) {
            final e = snap.error;
            return MessageView.error(
              message: e is ApiException ? e.message : 'Could not open this attachment.',
              onRetry: () => setState(() {
                _bytes = _load();
              }),
            );
          }
          final bytes = snap.data!;
          return Column(
            children: [
              Expanded(
                child: a.isImage
                    ? InteractiveViewer(
                        child: Center(
                          child: Image.memory(
                            bytes,
                            semanticLabel: a.name,
                            errorBuilder: (_, _, _) => const MessageView(
                              icon: Icons.broken_image_outlined,
                              title: 'Image cannot be displayed',
                            ),
                          ),
                        ),
                      )
                    : MessageView(
                        icon: Icons.videocam_outlined,
                        title: a.name,
                        message: '${formatBytes(a.size)} · Save the video to play it in your device’s player.',
                      ),
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.all(Space.lg),
                  child: SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: _saving ? null : () => _save(bytes),
                      icon: const Icon(Icons.download),
                      label: Text(_saving ? 'Saving…' : 'Save to device'),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
