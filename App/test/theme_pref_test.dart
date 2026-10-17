import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ufeed/core/prefs.dart';

Future<ProviderContainer> _container() async {
  final prefs = await SharedPreferences.getInstance();
  return ProviderContainer(overrides: [prefsProvider.overrideWithValue(prefs)]);
}

void main() {
  test('appearance follows the device until the person picks one', () async {
    SharedPreferences.setMockInitialValues({});
    final c = await _container();
    addTearDown(c.dispose);
    expect(c.read(displayPrefsProvider).theme, 'system');

    final n = c.read(displayPrefsProvider.notifier);
    n.update(c.read(displayPrefsProvider).copyWith(theme: 'dark'));
    expect(c.read(displayPrefsProvider).theme, 'dark');

    // Remembered on the next start.
    final again = await _container();
    addTearDown(again.dispose);
    expect(again.read(displayPrefsProvider).theme, 'dark');
  });

  test('an unknown saved value falls back to the system setting', () async {
    SharedPreferences.setMockInitialValues({'ufeed_theme': 'sepia'});
    final c = await _container();
    addTearDown(c.dispose);
    expect(c.read(displayPrefsProvider).theme, 'system');
  });
}
