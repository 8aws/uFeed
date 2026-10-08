import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../features/home/article_tile.dart';

/// Loaded once in main() and overridden there.
final prefsProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('prefsProvider is set in main()'),
);

/// The list layout, remembered on this device (like the web's view menu).
class ListStyleNotifier extends Notifier<ListStyle> {
  static const _key = 'ufeed_view';

  @override
  ListStyle build() {
    final saved = ref.read(prefsProvider).getString(_key);
    return ListStyle.values.firstWhere(
      (s) => s.name == saved,
      orElse: () => ListStyle.cardList,
    );
  }

  void set(ListStyle style) {
    state = style;
    ref.read(prefsProvider).setString(_key, style.name);
  }
}

final listStyleProvider = NotifierProvider<ListStyleNotifier, ListStyle>(
  ListStyleNotifier.new,
);

/// Text size steps, as in the web's accessibility settings.
const textScales = [1.0, 1.15, 1.3, 1.5];

/// Accessibility display options, per device (same as the web's).
class DisplayPrefs {
  const DisplayPrefs({
    this.textScale = 1,
    this.atkinson = false,
    this.autoFull = true,
  });

  /// On top of the system text size (Dynamic Type).
  final double textScale;

  /// Atkinson Hyperlegible instead of the system font.
  final bool atkinson;

  /// Load the full article when the feed only has an excerpt.
  final bool autoFull;

  DisplayPrefs copyWith({double? textScale, bool? atkinson, bool? autoFull}) =>
      DisplayPrefs(
        textScale: textScale ?? this.textScale,
        atkinson: atkinson ?? this.atkinson,
        autoFull: autoFull ?? this.autoFull,
      );
}

class DisplayPrefsNotifier extends Notifier<DisplayPrefs> {
  static const _scale = 'ufeed_text_scale';
  static const _font = 'ufeed_atkinson';
  static const _full = 'ufeed_auto_full';

  @override
  DisplayPrefs build() {
    final p = ref.read(prefsProvider);
    return DisplayPrefs(
      textScale: p.getDouble(_scale) ?? 1,
      atkinson: p.getBool(_font) ?? false,
      autoFull: p.getBool(_full) ?? true,
    );
  }

  void update(DisplayPrefs next) {
    state = next;
    final p = ref.read(prefsProvider);
    p.setDouble(_scale, next.textScale);
    p.setBool(_font, next.atkinson);
    p.setBool(_full, next.autoFull);
  }
}

final displayPrefsProvider =
    NotifierProvider<DisplayPrefsNotifier, DisplayPrefs>(
      DisplayPrefsNotifier.new,
    );
