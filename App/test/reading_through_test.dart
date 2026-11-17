import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/api/api_client.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/auth/session.dart';
import 'package:ufeed/features/home/home_state.dart';
import 'package:ufeed/offline/outbox.dart';
import 'package:ufeed/offline/providers.dart';

Article _article(int n) => Article(
  id: 'a$n',
  sourceId: 's',
  url: null,
  title: 'Story $n',
  author: null,
  summary: null,
  aiSummary: null,
  contentHtml: null,
  imageUrl: null,
  lang: 'es',
  wordCount: null,
  publishedAt: DateTime(2026, 1, 1).subtract(Duration(minutes: n)),
  fullStatus: null,
  isRead: false,
  isSaved: false,
  isFavorite: false,
  dupCount: 1,
  otherCopies: 0,
);

/// A server with `total` unread articles, served `size` at a time.
class _FakeApi implements ApiClient {
  _FakeApi(this.total, this.size);

  final int total;
  final int size;
  int requests = 0;
  String? lastQuery;
  bool? lastSemantic;
  bool? lastUnread;

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
    requests++;
    lastQuery = q;
    lastSemantic = semantic;
    lastUnread = unread;
    final from = int.tryParse(cursor ?? '0') ?? 0;
    final to = (from + size).clamp(0, total);
    return Page(
      items: [for (var i = from; i < to; i++) _article(i)],
      nextCursor: to >= total ? null : '$to',
    );
  }

  @override
  Future<List<Article>> forYou({int limit = 40}) async => const [];

  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

class _FakeOutbox implements Outbox {
  @override
  List<Article> applyPending(
    List<Article> items, {
    String? Function(String sourceId)? folderOf,
  }) => items;

  @override
  Future<Sent> setState(String id, Field field, bool value) async => Sent.sent;

  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

class _FakeSidebar extends SidebarNotifier {
  @override
  Future<Sidebar> build() async => const Sidebar(folders: [], subs: []);

  @override
  void adjustUnread(String sourceId, int delta) {}
}

Future<void> _settle(ProviderContainer c) async {
  for (var i = 0; i < 100; i++) {
    await Future<void>.delayed(const Duration(milliseconds: 5));
    if (!c.read(articleListProvider).loading) {
      await Future<void>.delayed(const Duration(milliseconds: 5));
      if (!c.read(articleListProvider).loading) return;
    }
  }
}

ProviderContainer _container(_FakeApi api) {
  final c = ProviderContainer(
    overrides: [
      apiProvider.overrideWithValue(api),
      outboxProvider.overrideWithValue(_FakeOutbox()),
      sessionProvider.overrideWith(() => _NoSession()),
      sidebarProvider.overrideWith(_FakeSidebar.new),
    ],
  );
  addTearDown(c.dispose);
  return c;
}

class _NoSession extends Session {
  @override
  Future<User?> build() async => null;
}

void main() {
  test(
    'reading through an unread list tops it up instead of leaving it short',
    () async {
      final api = _FakeApi(40, 8);
      final c = _container(api);
      c.read(articleListProvider);
      await _settle(c);
      expect(c.read(articleListProvider).items.length, 8);

      // The person reads the first post, then the next… as the reader does.
      final list = c.read(articleListProvider.notifier);
      for (var n = 0; n < 40; n++) {
        final current = c.read(articleListProvider).items.first;
        await list.setRead(current, true);
        await _settle(c);
        final s = c.read(articleListProvider);
        // Never stuck: either everything is loaded or the list still has plenty.
        expect(
          s.done || s.items.length >= 8,
          isTrue,
          reason: 'after reading ${n + 1}',
        );
      }
      final end = c.read(articleListProvider);
      expect(end.items, isEmpty);
      expect(end.done, isTrue);
    },
  );

  test('the reader asks for the next page when it reaches the end', () async {
    final api = _FakeApi(20, 8);
    final c = _container(api);
    c.read(articleListProvider);
    await _settle(c);
    final list = c.read(articleListProvider.notifier);
    final have = {for (final a in c.read(articleListProvider).items) a.id};

    final second = await list.more(have);
    expect(second.map((a) => a.id), [for (var i = 8; i < 16; i++) 'a$i']);
    have.addAll(second.map((a) => a.id));
    final third = await list.more(have);
    expect(third.length, 4);
    have.addAll(third.map((a) => a.id));
    expect(await list.more(have), isEmpty); // the end: nothing more to bring
  });

  test(
    'a search looks through everything, keeps what it finds, and ends',
    () async {
      final api = _FakeApi(10, 5);
      final c = _container(api);
      c.read(articleListProvider);
      await _settle(c);
      expect(api.lastUnread, isTrue);
      expect(api.lastQuery, isNull);

      final search = c.read(searchProvider.notifier);
      search.setQuery('  pirámide ');
      c.read(articleListProvider);
      await _settle(c);
      expect(api.lastQuery, 'pirámide');
      expect(api.lastSemantic, isFalse);
      expect(api.lastUnread, isFalse); // read posts are found too

      // Reading a result does not make it vanish from the results.
      final list = c.read(articleListProvider.notifier);
      final first = c.read(articleListProvider).items.first;
      await list.setRead(first, true);
      expect(c.read(articleListProvider).items.length, 5);

      search.setAi(true);
      c.read(articleListProvider);
      await _settle(c);
      expect(api.lastSemantic, isTrue);

      search.clear();
      c.read(articleListProvider);
      await _settle(c);
      expect(api.lastQuery, isNull);
      expect(api.lastUnread, isTrue);
    },
  );

  test('"For you" is not searched', () async {
    final api = _FakeApi(10, 5);
    final c = _container(api);
    c.read(filterProvider.notifier).set(const Filter(FilterKind.forYou));
    c.read(searchProvider.notifier).setQuery('algo');
    c.read(articleListProvider);
    await _settle(c);
    expect(c.read(articleListProvider.notifier).searching, isFalse);
    expect(api.requests, 0); // the For-you list is fetched apart
  });
}
