import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/api/api_client.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/auth/session.dart';
import 'package:ufeed/features/home/home_state.dart';
import 'package:ufeed/offline/local_search.dart';
import 'package:ufeed/offline/local_store.dart';
import 'package:ufeed/offline/outbox.dart';
import 'package:ufeed/offline/providers.dart';

Article _a(
  String id, {
  String? title,
  String? summary,
  String? html,
  String source = 's',
  int minutesAgo = 0,
  bool saved = false,
}) => Article(
  id: id,
  sourceId: source,
  url: null,
  title: title ?? 'Story $id',
  author: null,
  summary: summary,
  aiSummary: null,
  contentHtml: html,
  imageUrl: null,
  lang: 'es',
  wordCount: null,
  publishedAt: DateTime(2026, 11, 1).subtract(Duration(minutes: minutesAgo)),
  fullStatus: null,
  isRead: false,
  isSaved: saved,
  isFavorite: false,
  dupCount: 1,
  otherCopies: 0,
);

void main() {
  test('words match without caring for case or accents, all of them', () {
    final a = _a(
      '1',
      title: 'Qué monitor comprar para Mac',
      summary: 'Pirámide',
    );
    expect(matchesQuery(a, 'Applesfera', queryWords('MONITOR mac')), isTrue);
    expect(matchesQuery(a, 'Applesfera', queryWords('piramide')), isTrue);
    expect(matchesQuery(a, 'Applesfera', queryWords('que  comprar')), isTrue);
    expect(matchesQuery(a, 'Applesfera', queryWords('applesfera')), isTrue);
    expect(matchesQuery(a, 'Applesfera', queryWords('monitor pc')), isFalse);
    expect(matchesQuery(a, 'Applesfera', queryWords('   ')), isFalse);
  });

  test('the text of the article is searched too, tags aside', () {
    final a = _a('1', html: '<p>La <b>alta velocidad</b> en España</p>');
    expect(matchesQuery(a, '', queryWords('velocidad espana')), isTrue);
    expect(matchesQuery(a, '', queryWords('bold')), isFalse);
  });

  test(
    'a local search lists each article once, newest first, within the view',
    () {
      final pool = [
        _a('old', title: 'Gato viejo', minutesAgo: 600),
        _a('new', title: 'Gato nuevo', minutesAgo: 5),
        _a('new', title: 'Gato nuevo', minutesAgo: 5), // kept twice
        _a('dog', title: 'Perro'),
        _a('other', title: 'Gato de otra fuente', source: 'x', minutesAgo: 1),
      ];
      final found = searchLocal(
        query: 'gato',
        pool: pool,
        sourceOf: (_) => '',
        where: (a) => a.sourceId == 's',
      );
      expect(found.map((a) => a.id), ['new', 'old']);
    },
  );

  test('the kept articles are merged, once each, newest first and capped', () {
    final kept = [
      for (var i = 0; i < 150; i++) _a('k$i', minutesAgo: 1000 + i),
    ];
    final incoming = [
      for (var i = 0; i < 100; i++) _a('n$i', minutesAgo: i),
      _a('k0', title: 'Updated', minutesAgo: 1000),
    ];
    final merged = mergeRecent(kept, incoming);
    expect(merged.length, recentMax);
    expect(merged.map((a) => a.id).toSet().length, recentMax);
    expect(merged.first.id, 'n0');
    final ids = merged.map((a) => a.id).toList();
    expect(ids.indexOf('n0'), lessThan(ids.indexOf('k1')));
    // Long HTML is dropped, the excerpt stays.
    final big = mergeRecent(const [], [
      _a('b', summary: 'short', html: 'x' * 40000),
    ]);
    expect(big.single.contentHtml, isNull);
    expect(big.single.summary, 'short');
  });

  group(
    'the list falls back to the device when the server is out of reach',
    () {
      late Directory dir;
      setUp(() async => dir = await Directory.systemTemp.createTemp('ufeed'));
      tearDown(() async => dir.delete(recursive: true));

      test('and says so', () async {
        final api = _Api();
        final store = LocalStore(() async => dir);
        final c = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(api),
            outboxProvider.overrideWithValue(_Outbox()),
            localStoreProvider.overrideWithValue(store),
            sessionProvider.overrideWith(_Session.new),
            sidebarProvider.overrideWith(_Sidebar.new),
          ],
        );
        addTearDown(c.dispose);
        await c.read(sessionProvider.future);

        // Online: the list loads and the device keeps what came.
        c.read(articleListProvider);
        await _settle(c);
        expect(c.read(articleListProvider).items.length, 3);
        await Future<void>.delayed(const Duration(milliseconds: 100));
        expect((await store.loadRecent('u1')).length, 3);

        // Offline: the search is answered from what is kept.
        api.down = true;
        c.read(searchProvider.notifier).setQuery('monitor');
        c.read(articleListProvider);
        await _settle(c);
        final s = c.read(articleListProvider);
        expect(s.localSearch, isTrue);
        expect(s.offline, isTrue);
        expect(s.done, isTrue);
        expect(s.items.map((a) => a.id), ['m1']);

        // Back online the same search comes from the server again.
        api.down = false;
        c.read(searchProvider.notifier).setQuery('monitor ');
        c.read(searchProvider.notifier).setAi(true);
        c.read(articleListProvider);
        await _settle(c);
        expect(c.read(articleListProvider).localSearch, isFalse);
      });
    },
  );
}

class _Api implements ApiClient {
  bool down = false;

  @override
  Future<Page<Article>> articles({
    String? folder,
    String? source,
    bool unread = false,
    bool saved = false,
    bool favorite = false,
    String? q,
    bool semantic = false,
    String? cursor,
    int limit = 30,
  }) async {
    if (down) throw const ApiException(0, 'network', 'offline');
    return Page(
      items: [
        _a('m1', title: 'Qué monitor comprar', minutesAgo: 3),
        _a('m2', title: 'Un coche eléctrico', minutesAgo: 2),
        _a('m3', title: 'Receta de tortilla', minutesAgo: 1),
      ],
      nextCursor: null,
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

class _Outbox implements Outbox {
  @override
  List<Article> applyPending(
    List<Article> items, {
    String? Function(String sourceId)? folderOf,
  }) => items;

  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

class _Session extends Session {
  @override
  Future<User?> build() async =>
      User.fromJson({'id': 'u1', 'email': 'a@b.c', 'role': 'general'});
}

class _Sidebar extends SidebarNotifier {
  @override
  Future<Sidebar> build() async => const Sidebar(folders: [], subs: []);
}

Future<void> _settle(ProviderContainer c) async {
  for (var i = 0; i < 100; i++) {
    await Future<void>.delayed(const Duration(milliseconds: 10));
    if (!c.read(articleListProvider).loading) {
      await Future<void>.delayed(const Duration(milliseconds: 10));
      if (!c.read(articleListProvider).loading) return;
    }
  }
}
