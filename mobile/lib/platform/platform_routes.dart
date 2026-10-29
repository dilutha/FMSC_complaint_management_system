import 'package:flutter/material.dart';

import '../features/cases/case_routes.dart';
import '../features/suggestions/presentation/suggestion_detail_screen.dart';

/// SHARED CONTRACT (navigation): how platform screens open records.
/// Case records always open Member A's case-detail screen; there is no
/// second case-detail implementation.
abstract final class PlatformRoutes {
  static Future<void> openSuggestion(BuildContext context, int id) =>
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => SuggestionDetailScreen(suggestionId: id)));

  /// Follows a notification's navigation target: {"type": "case" | "suggestion", "id"}.
  static Future<void> openTarget(BuildContext context, String? type, int? id) async {
    if (id == null) return;
    if (type == 'suggestion') return openSuggestion(context, id);
    return CaseRoutes.openCase(context, id);
  }
}
