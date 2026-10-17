import 'dart:convert';

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

/// Text size steps, as in the web's accessibility settings; the first two
/// go below the system size (Dynamic Type), for people who set it large.
const textScales = [0.85, 0.9, 1.0, 1.15, 1.3, 1.5];

/// Accessibility display options, per device (same as the web's).
class DisplayPrefs {
  const DisplayPrefs({
    this.textScale = 1,
    this.atkinson = false,
    this.autoFull = true,
    this.theme = 'system',
  });

  /// On top of the system text size (Dynamic Type).
  final double textScale;

  /// Atkinson Hyperlegible instead of the system font.
  final bool atkinson;

  /// Load the full article when the feed only has an excerpt.
  final bool autoFull;

  /// Appearance: `system` (follows the device), `light` or `dark`.
  final String theme;

  DisplayPrefs copyWith({
    double? textScale,
    bool? atkinson,
    bool? autoFull,
    String? theme,
  }) => DisplayPrefs(
    textScale: textScale ?? this.textScale,
    atkinson: atkinson ?? this.atkinson,
    autoFull: autoFull ?? this.autoFull,
    theme: theme ?? this.theme,
  );
}

class DisplayPrefsNotifier extends Notifier<DisplayPrefs> {
  static const _scale = 'ufeed_text_scale';
  static const _font = 'ufeed_atkinson';
  static const _full = 'ufeed_auto_full';
  static const _theme = 'ufeed_theme';

  @override
  DisplayPrefs build() {
    final p = ref.read(prefsProvider);
    return DisplayPrefs(
      textScale: p.getDouble(_scale) ?? 1,
      atkinson: p.getBool(_font) ?? false,
      autoFull: p.getBool(_full) ?? true,
      theme: const {'light', 'dark'}.contains(p.getString(_theme))
          ? p.getString(_theme)!
          : 'system',
    );
  }

  void update(DisplayPrefs next) {
    state = next;
    final p = ref.read(prefsProvider);
    p.setDouble(_scale, next.textScale);
    p.setBool(_font, next.atkinson);
    p.setBool(_full, next.autoFull);
    p.setString(_theme, next.theme);
  }
}

final displayPrefsProvider =
    NotifierProvider<DisplayPrefsNotifier, DisplayPrefs>(
      DisplayPrefsNotifier.new,
    );

/// Read-aloud preferences, per device (same as the web's).
class SpeechPrefs {
  const SpeechPrefs({
    this.server = false,
    this.gender = 'f',
    this.rate = 1,
    this.autoRead = false,
    this.myLanguage = false,
    this.radioPosts = 10,
    this.radioMinutes = 30,
    this.offlineAudio = false,
  });

  /// The server's neural voice (plan feature) instead of the device's.
  final bool server;
  final String gender; // server voice: f | m
  final double rate; // 0.75 … 2
  final bool autoRead; // accessibility: start reading when an article opens
  final bool myLanguage; // translate articles in another language first
  final int radioPosts; // Post radio: stop after this many (0 = plan max)
  final int radioMinutes; // ...or after this many minutes (0 = plan max)
  final bool offlineAudio; // keep the server voice of saved articles

  static const rates = [0.75, 0.85, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0];

  SpeechPrefs copyWith({
    bool? server,
    String? gender,
    double? rate,
    bool? autoRead,
    bool? myLanguage,
    int? radioPosts,
    int? radioMinutes,
    bool? offlineAudio,
  }) => SpeechPrefs(
    server: server ?? this.server,
    gender: gender ?? this.gender,
    rate: rate ?? this.rate,
    autoRead: autoRead ?? this.autoRead,
    myLanguage: myLanguage ?? this.myLanguage,
    radioPosts: radioPosts ?? this.radioPosts,
    radioMinutes: radioMinutes ?? this.radioMinutes,
    offlineAudio: offlineAudio ?? this.offlineAudio,
  );

  Map<String, Object> toJson() => {
    'server': server,
    'gender': gender,
    'rate': rate,
    'autoRead': autoRead,
    'myLanguage': myLanguage,
    'radioPosts': radioPosts,
    'radioMinutes': radioMinutes,
    'offlineAudio': offlineAudio,
  };

  factory SpeechPrefs.fromJson(Map<String, dynamic> j) => SpeechPrefs(
    server: j['server'] as bool? ?? false,
    gender: j['gender'] as String? ?? 'f',
    rate: (j['rate'] as num?)?.toDouble() ?? 1,
    autoRead: j['autoRead'] as bool? ?? false,
    myLanguage: j['myLanguage'] as bool? ?? false,
    radioPosts: j['radioPosts'] as int? ?? 10,
    radioMinutes: j['radioMinutes'] as int? ?? 30,
    offlineAudio: j['offlineAudio'] as bool? ?? false,
  );
}

class SpeechPrefsNotifier extends Notifier<SpeechPrefs> {
  static const _key = 'ufeed_speech';

  @override
  SpeechPrefs build() {
    final raw = ref.read(prefsProvider).getString(_key);
    if (raw == null) return const SpeechPrefs();
    try {
      return SpeechPrefs.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } on Object {
      return const SpeechPrefs();
    }
  }

  void update(SpeechPrefs next) {
    state = next;
    ref.read(prefsProvider).setString(_key, jsonEncode(next.toJson()));
  }
}

final speechPrefsProvider = NotifierProvider<SpeechPrefsNotifier, SpeechPrefs>(
  SpeechPrefsNotifier.new,
);
