import 'package:flutter/material.dart';

import 'usj_colors.dart';

/// Shared non-colour tokens. Colours live in [UsjColors] and spacing in
/// `Space` (theme.dart); see docs/DESIGN_SYSTEM.md for usage rules.
abstract final class Radii {
  static const sm = 8.0; // inputs, buttons, bars
  static const md = 12.0; // cards, sheets
  static const pill = 999.0; // badges
}

/// Flat surfaces separated by borders; elevation only for overlays.
abstract final class Elevations {
  static const none = 0.0;
  static const overlay = 3.0; // bottom sheets, menus
}

/// Single hue used for magnitude bars on the dashboard (official USJ blue).
/// One series per chart, so no categorical palette is needed.
abstract final class ChartColors {
  static const bar = UsjColors.blue;
  static const track = UsjColors.surfaceMuted;
}

/// Type scale used by platform screens (Material 3 defaults, documented here
/// so both members use the same roles).
abstract final class TextRoles {
  static TextStyle? kpiValue(BuildContext c) =>
      Theme.of(c).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w600, fontFeatures: _tabular);
  static TextStyle? label(BuildContext c) =>
      Theme.of(c).textTheme.labelMedium?.copyWith(color: UsjColors.textSecondary);
  static const _tabular = [FontFeature.tabularFigures()];
}
