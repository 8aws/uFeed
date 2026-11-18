import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ufeed/notify/new_articles.dart';

void main() {
  group('what a check decides', () {
    test('new articles at or over the minimum are told, and remembered', () {
      final d = decideNotification(total: 17, baseline: 12, min: 5);
      expect(d.show, isTrue);
      expect(d.count, 5);
      expect(d.baseline, 17);
    });

    test('fewer than the minimum wait quietly and add up', () {
      final first = decideNotification(total: 14, baseline: 12, min: 5);
      expect(first.show, isFalse);
      expect(first.baseline, 12); // still waiting
      final later = decideNotification(
        total: 18,
        baseline: first.baseline,
        min: 5,
      );
      expect(later.show, isTrue);
      expect(later.count, 6);
    });

    test('reading lowers the baseline so only what arrives after counts', () {
      final d = decideNotification(total: 3, baseline: 12, min: 1);
      expect(d.show, isFalse);
      expect(d.baseline, 3);
      expect(decideNotification(total: 4, baseline: 3, min: 1).show, isTrue);
    });
  });

  test('the text follows the language, singular and plural', () {
    expect(notificationText('es', 1).body, '1 artículo nuevo');
    expect(notificationText('es', 7).body, '7 artículos nuevos');
    expect(notificationText('en', 1).body, '1 new article');
    expect(notificationText('en', 2).body, '2 new articles');
  });

  group('the background check', () {
    Future<(SharedPreferences, List<String>)> setup(
      Map<String, Object> v,
    ) async {
      SharedPreferences.setMockInitialValues(v);
      return (await SharedPreferences.getInstance(), <String>[]);
    }

    test('does nothing when notifications are off', () async {
      final (prefs, shown) = await setup({});
      var asked = false;
      final did = await checkForNew(
        prefs: prefs,
        totalUnread: () async {
          asked = true;
          return 50;
        },
        show: (t, b, n) async => shown.add(b),
      );
      expect(did, isFalse);
      expect(asked, isFalse); // not even a request to the server
      expect(shown, isEmpty);
    });

    test('tells about what is new and keeps the new baseline', () async {
      final (prefs, shown) = await setup({
        'ufeed_notify': true,
        'ufeed_notify_base': 10,
        'ufeed_notify_min': 1,
      });
      final did = await checkForNew(
        prefs: prefs,
        language: () => 'es',
        totalUnread: () async => 13,
        show: (t, b, n) async => shown.add('$b/$n'),
      );
      expect(did, isTrue);
      expect(shown, ['3 artículos nuevos/13']);
      expect(prefs.getInt('ufeed_notify_base'), 13);
      // The same total again: nothing new.
      expect(
        await checkForNew(
          prefs: prefs,
          totalUnread: () async => 13,
          show: (t, b, n) async => shown.add(b),
        ),
        isFalse,
      );
    });

    test('no connection or no session leaves everything as it was', () async {
      final (prefs, shown) = await setup({
        'ufeed_notify': true,
        'ufeed_notify_base': 10,
      });
      expect(
        await checkForNew(
          prefs: prefs,
          totalUnread: () async => null,
          show: (t, b, n) async => shown.add(b),
        ),
        isFalse,
      );
      expect(prefs.getInt('ufeed_notify_base'), 10);
    });

    test('the first check only learns the total, it does not tell', () async {
      final (prefs, shown) = await setup({'ufeed_notify': true});
      await checkForNew(
        prefs: prefs,
        totalUnread: () async => 40,
        show: (t, b, n) async => shown.add(b),
      );
      expect(shown, isEmpty);
      expect(prefs.getInt('ufeed_notify_base'), 40);
    });
  });

  test(
    'what is on screen counts as seen, only while notifications are on',
    () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      await markSeen(prefs, 9);
      expect(prefs.getInt('ufeed_notify_base'), isNull);
      await prefs.setBool('ufeed_notify', true);
      await markSeen(prefs, 9);
      expect(prefs.getInt('ufeed_notify_base'), 9);
    },
  );
}
