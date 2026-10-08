import 'package:flutter/material.dart';

/// The web app's palette (Frontend/src/app.css), so both clients look alike.
class UColors extends ThemeExtension<UColors> {
  const UColors({
    required this.bg,
    required this.surface,
    required this.border,
    required this.text,
    required this.muted,
    required this.accent,
    required this.accentSoft,
    required this.danger,
  });

  final Color bg;
  final Color surface;
  final Color border;
  final Color text;
  final Color muted;
  final Color accent;
  final Color accentSoft;
  final Color danger;

  static const light = UColors(
    bg: Color(0xFFF7F7F8),
    surface: Color(0xFFFFFFFF),
    border: Color(0xFFE5E7EB),
    text: Color(0xFF1F2937),
    muted: Color(0xFF6B7280),
    accent: Color(0xFF2563EB),
    accentSoft: Color(0xFFEFF6FF),
    danger: Color(0xFFDC2626),
  );

  static const dark = UColors(
    bg: Color(0xFF0F172A),
    surface: Color(0xFF111827),
    border: Color(0xFF1F2937),
    text: Color(0xFFE5E7EB),
    muted: Color(0xFF9CA3AF),
    accent: Color(0xFF60A5FA),
    accentSoft: Color(0xFF1E293B),
    danger: Color(0xFFF87171),
  );

  @override
  UColors copyWith() => this;

  @override
  UColors lerp(UColors? other, double t) {
    if (other == null) return this;
    Color l(Color a, Color b) => Color.lerp(a, b, t)!;
    return UColors(
      bg: l(bg, other.bg),
      surface: l(surface, other.surface),
      border: l(border, other.border),
      text: l(text, other.text),
      muted: l(muted, other.muted),
      accent: l(accent, other.accent),
      accentSoft: l(accentSoft, other.accentSoft),
      danger: l(danger, other.danger),
    );
  }
}

extension UColorsX on BuildContext {
  UColors get colors => Theme.of(this).extension<UColors>()!;
}

ThemeData buildTheme(Brightness brightness, {String? fontFamily}) {
  final c = brightness == Brightness.dark ? UColors.dark : UColors.light;
  final scheme =
      ColorScheme.fromSeed(
        seedColor: c.accent,
        brightness: brightness,
      ).copyWith(
        primary: c.accent,
        surface: c.surface,
        onSurface: c.text,
        error: c.danger,
        outlineVariant: c.border,
      );
  return ThemeData(
    colorScheme: scheme,
    fontFamily: fontFamily,
    scaffoldBackgroundColor: c.bg,
    dividerColor: c.border,
    appBarTheme: AppBarTheme(
      backgroundColor: c.surface,
      foregroundColor: c.text,
      elevation: 0,
      scrolledUnderElevation: 0.5,
    ),
    drawerTheme: DrawerThemeData(backgroundColor: c.surface),
    extensions: [c],
  );
}
