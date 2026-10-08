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
