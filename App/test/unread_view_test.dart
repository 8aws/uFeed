import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/core/prefs.dart';
import 'package:ufeed/features/home/home_state.dart';

Article _a(String id, DateTime when) => Article(
  id: id,
  sourceId: 's1',
  url: null,
  title: id,
  author: null,
  summary: null,
  aiSummary: null,
  contentHtml: null,
  imageUrl: null,
  lang: 'es',
  wordCount: null,
  publishedAt: when,
  fetchedAt: when,
  fullStatus: null,
  isRead: false,
  isSaved: false,
  isFavorite: false,
  dupCount: 1,
);

void main() {
  final t0 = DateTime(2026, 10, 20, 12);

  test('an article marked unread again goes back to its place', () {
    final newest = _a('c', t0.add(const Duration(hours: 2)));
    final middle = _a('b', t0.add(const Duration(hours: 1)));
    final oldest = _a('a', t0);
    final list = [newest, oldest];

    final back = insertedInOrder(list, middle, atEnd: true);
    expect([for (final x in back) x.id], ['c', 'b', 'a']);
    // Already there: nothing changes.
    expect(insertedInOrder(back, middle, atEnd: true), same(back));
  });

  test(
    'older than everything loaded only goes last when the list is complete',
    () {
      final list = [_a('c', t0.add(const Duration(hours: 2)))];
      final old = _a('a', t0);
      expect(insertedInOrder(list, old, atEnd: false), same(list));
      expect(
        [for (final x in insertedInOrder(list, old, atEnd: true)) x.id],
        ['c', 'a'],
      );
    },
  );

  test('same time: ties go by id, descending, like the server', () {
    final x = _a('x', t0);
    final z = _a('z', t0);
    final out = insertedInOrder([z], x, atEnd: true);
    expect([for (final a in out) a.id], ['z', 'x']);
  });

  test('folded folders are remembered between sessions', () async {
    SharedPreferences.setMockInitialValues({});
    Future<ProviderContainer> container() async => ProviderContainer(
      overrides: [
        prefsProvider.overrideWithValue(await SharedPreferences.getInstance()),
      ],
    );
    final c = await container();
    addTearDown(c.dispose);
    expect(c.read(collapsedFoldersProvider), isEmpty);
    c.read(collapsedFoldersProvider.notifier).toggle('f1');
    c.read(collapsedFoldersProvider.notifier).toggle('f2');
    c.read(collapsedFoldersProvider.notifier).toggle('f1'); // open again
    expect(c.read(collapsedFoldersProvider), {'f2'});

    final again = await container();
    addTearDown(again.dispose);
    expect(again.read(collapsedFoldersProvider), {'f2'});
  });
}
