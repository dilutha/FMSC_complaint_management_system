import 'package:flutter/material.dart';

import 'usj_colors.dart';

/// Spacing scale (4-pt grid) used everywhere for consistent rhythm.
abstract final class Space {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 24.0;
  static const xxl = 32.0;
}

/// Minimum touch target (Material / WCAG 2.5.8 guidance).
const kMinTouchTarget = 48.0;

ThemeData buildUsjTheme() {
  const scheme = ColorScheme(
    brightness: Brightness.light,
    primary: UsjColors.red,
    onPrimary: Colors.white,
    primaryContainer: Color(0xFFFBE4E3),
    onPrimaryContainer: UsjColors.maroon,
    secondary: UsjColors.yellow,
    onSecondary: UsjColors.textPrimary,
    secondaryContainer: Color(0xFFFFF8C4),
    onSecondaryContainer: UsjColors.textPrimary,
    tertiary: UsjColors.blue,
    onTertiary: Colors.white,
    error: UsjColors.error,
    onError: Colors.white,
    surface: UsjColors.surface,
    onSurface: UsjColors.textPrimary,
    onSurfaceVariant: UsjColors.textSecondary,
    surfaceContainerLowest: UsjColors.surface,
    surfaceContainerLow: UsjColors.background,
    surfaceContainer: UsjColors.surfaceMuted,
    outline: UsjColors.border,
    outlineVariant: Color(0xFFE4E4E8),
  );

  final base = ThemeData(useMaterial3: true, colorScheme: scheme);
  final text = base.textTheme.apply(bodyColor: UsjColors.textPrimary, displayColor: UsjColors.textPrimary);

  final focusBorder = OutlineInputBorder(
    borderRadius: BorderRadius.circular(8),
    borderSide: const BorderSide(color: UsjColors.blue, width: 2),
  );

  return base.copyWith(
    scaffoldBackgroundColor: UsjColors.background,
    textTheme: text.copyWith(
      titleLarge: text.titleLarge?.copyWith(fontWeight: FontWeight.w600),
      titleMedium: text.titleMedium?.copyWith(fontWeight: FontWeight.w600),
      bodyLarge: text.bodyLarge?.copyWith(height: 1.45),
      bodyMedium: text.bodyMedium?.copyWith(height: 1.45),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: UsjColors.maroon,
      foregroundColor: Colors.white,
      elevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: UsjColors.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: UsjColors.border),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(kMinTouchTarget * 2, kMinTouchTarget),
        backgroundColor: UsjColors.red,
        foregroundColor: Colors.white,
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(kMinTouchTarget * 2, kMinTouchTarget),
        foregroundColor: UsjColors.maroon,
        side: const BorderSide(color: UsjColors.border),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(kMinTouchTarget, kMinTouchTarget),
        foregroundColor: UsjColors.maroon,
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: UsjColors.surface,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: UsjColors.border),
      ),
      focusedBorder: focusBorder,
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: UsjColors.error),
      ),
      focusedErrorBorder: focusBorder.copyWith(borderSide: const BorderSide(color: UsjColors.error, width: 2)),
      contentPadding: const EdgeInsets.symmetric(horizontal: Space.md, vertical: Space.md),
      helperMaxLines: 2,
      errorMaxLines: 3,
    ),
    chipTheme: base.chipTheme.copyWith(
      selectedColor: UsjColors.yellow,
      checkmarkColor: UsjColors.textPrimary,
      labelStyle: const TextStyle(color: UsjColors.textPrimary),
      side: const BorderSide(color: UsjColors.border),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size(kMinTouchTarget, kMinTouchTarget)),
        backgroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? UsjColors.yellow : UsjColors.surface,
        ),
        foregroundColor: const WidgetStatePropertyAll(UsjColors.textPrimary),
      ),
    ),
    navigationBarTheme: const NavigationBarThemeData(
      indicatorColor: UsjColors.yellow,
      backgroundColor: UsjColors.surface,
    ),
    focusColor: UsjColors.blue.withValues(alpha: 0.16),
    dividerTheme: const DividerThemeData(color: UsjColors.border, space: 1),
    snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
  );
}
