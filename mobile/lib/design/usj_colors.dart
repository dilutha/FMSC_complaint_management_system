import 'package:flutter/material.dart';

/// Colour tokens. See docs/DESIGN_SYSTEM.md for sources and contrast checks.
///
/// Brand values are transcribed from the colour palettes published on the
/// official USJ branding page (https://www.sjp.ac.lk/branding-and-visual-identity/,
/// images "USJP Logo Color Palette" and "USJP Website Color Palette").
/// Neutral and semantic colours are project choices, NOT university colours.
abstract final class UsjColors {
  // --- Official: USJP Logo Color Palette ---
  static const red = Color(0xFFC1282D); // HEX #c1282d · RGB 193,40,45
  static const yellow = Color(0xFFF9EB24); // HEX #f9eb24 · RGB 249,235,36
  static const black = Color(0xFF010101); // HEX #010101 · RGB 1,1,1

  // --- Official: USJP Website Color Palette ---
  static const maroon = Color(0xFF800000); // HEX #800000 · RGB 127,20,22 (as published)
  static const blue = Color(0xFF314E86); // HEX #314e86 · RGB 49,78,134
  static const paleBlue = Color(0xFFCBE2F1); // HEX #cbe2f1 · RGB 203,226,241
  static const gold = Color(0xFFE9AD21); // HEX #e9ad21 · RGB 233,173,33
  static const softYellow = Color(0xFFF7D739); // HEX #f7d739 · RGB 247,215,57

  // --- Project neutrals (not brand colours) ---
  static const surface = Color(0xFFFFFFFF);
  static const background = Color(0xFFF6F6F7);
  static const surfaceMuted = Color(0xFFEFEFF1);
  static const border = Color(0xFFD6D6DB);
  static const textPrimary = Color(0xFF1C1C21);
  static const textSecondary = Color(0xFF55555F);

  // --- Project semantic colours (not brand colours), all ≥ 4.5:1 on white ---
  static const success = Color(0xFF1E6B34);
  static const successBg = Color(0xFFE3F2E7);
  static const warning = Color(0xFF7A4E00);
  static const warningBg = Color(0xFFFFF3D1);
  static const error = Color(0xFFB3261E);
  static const errorBg = Color(0xFFFBE4E2);
  static const info = blue; // official website blue doubles as the info tone
  static const infoBg = Color(0xFFE6EEF7);
  static const neutral = Color(0xFF4A4A52);
  static const neutralBg = Color(0xFFECECEF);
}
