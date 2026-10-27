import 'package:flutter/widgets.dart';

import '../../core/api_client.dart';
import 'data/case_repository.dart';

/// Lets the user choose evidence files. Injected so tests and Member B's
/// shell can replace the platform picker.
typedef AttachmentPicker = Future<List<UploadFile>> Function({required List<String> allowedExtensions});

/// Provides case-module dependencies to every case screen.
class CaseScope extends InheritedWidget {
  const CaseScope({super.key, required this.repository, required this.pickAttachments, required super.child});

  final CaseRepository repository;
  final AttachmentPicker pickAttachments;

  static CaseScope of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<CaseScope>();
    assert(scope != null, 'CaseScope not found. Wrap the app (or case routes) in CaseScope.');
    return scope!;
  }

  @override
  bool updateShouldNotify(CaseScope oldWidget) =>
      repository != oldWidget.repository || pickAttachments != oldWidget.pickAttachments;
}
