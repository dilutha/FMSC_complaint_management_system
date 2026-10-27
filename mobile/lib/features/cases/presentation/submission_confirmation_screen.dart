import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../data/models.dart';
import 'case_detail_screen.dart';

class SubmissionConfirmationScreen extends StatelessWidget {
  const SubmissionConfirmationScreen({super.key, required this.created});
  final CaseDetail created;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Case submitted'), automaticallyImplyLeading: false),
      body: ListView(
        padding: const EdgeInsets.all(Space.xl),
        children: [
          const Icon(Icons.check_circle, size: 64, color: UsjColors.success, semanticLabel: 'Success'),
          const SizedBox(height: Space.lg),
          Semantics(
            liveRegion: true,
            child: Text(
              'Thank you. Your ${created.caseTypeLabel.toLowerCase()} has been received.',
              style: theme.textTheme.titleLarge,
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: Space.xl),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(Space.lg),
              child: Column(
                children: [
                  Text('Your reference number', style: theme.textTheme.labelLarge),
                  const SizedBox(height: Space.sm),
                  SelectableText(
                    created.caseNumber,
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: UsjColors.maroon,
                    ),
                  ),
                  const SizedBox(height: Space.sm),
                  TextButton.icon(
                    onPressed: () {
                      Clipboard.setData(ClipboardData(text: created.caseNumber));
                      ScaffoldMessenger.of(
                        context,
                      ).showSnackBar(const SnackBar(content: Text('Reference number copied')));
                    },
                    icon: const Icon(Icons.copy),
                    label: const Text('Copy'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: Space.lg),
          SectionCard(
            title: 'What happens next',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                StatusBadge(status: created.status, label: created.statusLabel),
                const SizedBox(height: Space.md),
                const Text(
                  '1. An administrator reviews your case.\n'
                  '2. It is assigned to the responsible unit.\n'
                  '3. You can follow progress in My cases and will be notified when it is solved.',
                ),
              ],
            ),
          ),
          const SizedBox(height: Space.xl),
          FilledButton(
            onPressed: () => Navigator.of(
              context,
            ).pushReplacement(MaterialPageRoute(builder: (_) => CaseDetailScreen(caseId: created.id))),
            child: const Text('View case'),
          ),
          const SizedBox(height: Space.sm),
          OutlinedButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Back to my cases')),
        ],
      ),
    );
  }
}
