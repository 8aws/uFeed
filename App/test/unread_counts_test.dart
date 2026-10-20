import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/features/home/home_state.dart';

Subscription _sub(String source, {String? folder, int unread = 0}) =>
    Subscription(
      id: 'sub-$source',
      folderId: folder,
      customTitle: null,
      muted: false,
      source: Source(
        id: source,
        feedUrl: 'https://$source/feed',
        siteUrl: null,
        title: source,
        faviconUrl: null,
      ),
      unreadCount: unread,
    );

void main() {
  test('the totals come from the server when it sent them', () {
    final subs = [_sub('a', folder: 'f', unread: 150), _sub('b', unread: 10)];
    // Added up, the feeds say 160; the server counts one per story: 40.
    final side = Sidebar(
      folders: const [],
      subs: subs,
      counts: const UnreadCounts(40, {'f': 30}),
    );
    expect(side.unreadTotal, 40);
    expect(side.unreadIn('f'), 30);
    expect(side.unreadIn('empty'), 0);
  });

  test('without the server numbers (offline) the feeds are added up', () {
    final subs = [_sub('a', folder: 'f', unread: 5), _sub('b', unread: 2)];
    final side = Sidebar(folders: const [], subs: subs);
    expect(side.unreadTotal, 7);
    expect(side.unreadIn('f'), 5);
  });

  test(
    'reading adjusts the feed, its folder and the total until refreshed',
    () {
      final side = Sidebar(
        folders: const [],
        subs: [_sub('a', folder: 'f', unread: 3)],
        counts: const UnreadCounts(10, {'f': 3}),
      ).adjustUnread('a', -1);
      expect(side.subFor('a')!.unreadCount, 2);
      expect(side.unreadTotal, 9);
      expect(side.unreadIn('f'), 2);
    },
  );

  test('counts never go below zero', () {
    const c = UnreadCounts(0, {'f': 0});
    final d = c.adjusted(-1, 'f');
    expect(d.total, 0);
    expect(d.folders['f'], 0);
  });

  test('an article tells how many other copies of its story exist', () {
    final a = Article.fromJson({
      'id': 'x',
      'source_id': 's',
      'dup_count': 2,
      'other_copies': 3,
    });
    expect(a.twins, 4); // 1 more in your feeds, 3 in feeds you don't follow
    expect(Article.fromJson(a.toJson()).otherCopies, 3);
    expect(Article.fromJson({'id': 'y', 'source_id': 's'}).twins, 0);
  });

  test('a twin in a feed you do not follow carries no article id', () {
    final t = Twin.fromJson({
      'title': 'Same story',
      'url': 'https://elsewhere.example/a',
      'source_title': 'Elsewhere',
      'followed': false,
    });
    expect(t.articleId, isNull);
    expect(t.followed, isFalse);
  });
}
