import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/api_client.dart';
import '../../api/models.dart';
import '../../auth/session.dart';
import '../../offline/local_store.dart';
import '../../offline/outbox.dart';
import '../../offline/providers.dart';

enum FilterKind { all, unread, saved, favorites, forYou, folder, source }

/// What the article list shows.
class Filter {
  const Filter(this.kind, [this.id]);

  final FilterKind kind;
  final String? id; // folder or source id

  @override
  bool operator ==(Object other) =>
      other is Filter && other.kind == kind && other.id == id;

  @override
  int get hashCode => Object.hash(kind, id);

  /// For the start-up snapshot (which list it is).
  String get key => id == null ? kind.name : '${kind.name}:$id';
}

/// Where an article goes in a list ordered like the server's: newest first
/// (published, else fetched), ties by id, descending. Returns the list with it
/// added (unchanged if it is already there); `atEnd` says whether it may go
/// last: false while more pages are still to load, since it would then belong
/// somewhere beyond what is on screen.
List<Article> insertedInOrder(
  List<Article> items,
  Article a, {
  required bool atEnd,
}) {
  if (items.any((x) => x.id == a.id)) return items;
  int when(Article x) =>
      (x.publishedAt ?? x.fetchedAt)?.millisecondsSinceEpoch ?? 0;
  bool ahead(Article x) =>
      when(x) > when(a) || (when(x) == when(a) && x.id.compareTo(a.id) > 0);
  final at = items.indexWhere((x) => !ahead(x));
  if (at < 0) return atEnd ? [...items, a] : items;
  return [...items.sublist(0, at), a, ...items.sublist(at)];
}

class Sidebar {
  const Sidebar({required this.folders, required this.subs, this.counts});

  final List<Folder> folders;
  final List<Subscription> subs;

  /// The totals as the server counts them (one per duplicate story, own feeds
  /// only); without them (no connection) the feeds' own badges are added up.
  final UnreadCounts? counts;

  int get unreadTotal =>
      counts?.total ??
      subs.where((s) => !s.muted).fold(0, (n, s) => n + s.unreadCount);

  int unreadIn(String folderId) =>
      counts?.folders[folderId] ??
      (counts != null
          ? 0
          : subs
                .where((s) => s.folderId == folderId && !s.muted)
                .fold(0, (n, s) => n + s.unreadCount));

  Subscription? subFor(String sourceId) {
    for (final s in subs) {
      if (s.source.id == sourceId) return s;
    }
    return null;
  }

  Sidebar adjustUnread(String sourceId, int delta) => Sidebar(
    folders: folders,
    subs: [
      for (final s in subs)
        s.source.id == sourceId ? s.withUnread(s.unreadCount + delta) : s,
    ],
    // Until the server's numbers arrive again: a good guess.
    counts: counts?.adjusted(delta, subFor(sourceId)?.folderId),
  );
}

final sidebarProvider = AsyncNotifierProvider<SidebarNotifier, Sidebar>(
  SidebarNotifier.new,
);

class SidebarNotifier extends AsyncNotifier<Sidebar> {
  @override
  Future<Sidebar> build() async {
    final api = ref.watch(apiProvider);
    try {
      final (folders, subs, counts) = await (
        api.folders(),
        api.sources(),
        api
            .unreadCounts()
            .then<UnreadCounts?>((c) => c)
            .onError((_, _) => null),
      ).wait;
      folders.sort((a, b) => a.position.compareTo(b.position));
      return Sidebar(folders: folders, subs: subs, counts: counts);
    } on ParallelWaitError<
      (List<Folder>?, List<Subscription>?, UnreadCounts?),
      Object
    > {
      // No network: the menu from the last session.
      final snap = await _snapshot();
      if (snap != null) return Sidebar(folders: snap.folders, subs: snap.subs);
      rethrow;
    }
  }

  Future<HomeSnapshot?> _snapshot() async {
    final user = ref.read(sessionProvider).value;
    if (user == null) return null;
    return ref.read(localStoreProvider).loadHome(user.id);
  }

  void adjustUnread(String sourceId, int delta) {
    final s = state.value;
    if (s != null) state = AsyncData(s.adjustUnread(sourceId, delta));
    _scheduleCounts();
  }

  Timer? _countsTimer;

  /// After reading or un-reading, ask the server for the real numbers (the
  /// local adjustment is only a guess: it can't know which copy of a story the
  /// totals count).
  void _scheduleCounts() {
    _countsTimer?.cancel();
    ref.onDispose(() => _countsTimer?.cancel());
    _countsTimer = Timer(const Duration(seconds: 3), () async {
      final s = state.value;
      if (s == null) return;
      try {
        final c = await ref.read(apiProvider).unreadCounts();
        final now = state.value;
        if (now != null) {
          state = AsyncData(
            Sidebar(folders: now.folders, subs: now.subs, counts: c),
          );
        }
      } on ApiException {
        // keep the guess
      }
    });
  }

  Future<void> reload() async {
    final next = await AsyncValue.guard(build);
    // Keep what's on screen if the reload fails.
    if (next.hasValue || !state.hasValue) state = next;
  }
}

class FilterNotifier extends Notifier<Filter> {
  @override
  Filter build() => const Filter(FilterKind.unread);

  void set(Filter f) => state = f;
}

final filterProvider = NotifierProvider<FilterNotifier, Filter>(
  FilterNotifier.new,
);

/// In a folder or source, show only unread (like the web's "only unread").
class OnlyUnreadNotifier extends Notifier<bool> {
  @override
  bool build() => true;

  void toggle() => state = !state;
}

final onlyUnreadProvider = NotifierProvider<OnlyUnreadNotifier, bool>(
  OnlyUnreadNotifier.new,
);

class ArticleList {
  const ArticleList({
    this.items = const [],
    this.cursor,
    this.loading = false,
    this.done = false,
    this.error,
    this.listedAt,
    this.offline = false,
  });

  final List<Article> items;

  /// Showing the copy kept on the device (no connection).
  final bool offline;
  final String? cursor;
  final bool loading;
  final bool done;
  final ApiException? error;

  /// When the first page was fetched: "mark all read" stops there.
  final DateTime? listedAt;

  ArticleList copyWith({
    List<Article>? items,
    String? cursor,
    bool? loading,
    bool? done,
    ApiException? error,
    DateTime? listedAt,
    bool? offline,
  }) => ArticleList(
    items: items ?? this.items,
    cursor: cursor ?? this.cursor,
    loading: loading ?? this.loading,
    done: done ?? this.done,
    error: error,
    listedAt: listedAt ?? this.listedAt,
    offline: offline ?? this.offline,
  );
}

final articleListProvider = NotifierProvider<ArticleListNotifier, ArticleList>(
  ArticleListNotifier.new,
);

class ArticleListNotifier extends Notifier<ArticleList> {
  int _seq = 0;

  ApiClient get _api => ref.read(apiProvider);
  Outbox get _outbox => ref.read(outboxProvider);

  @override
  ArticleList build() {
    ref.watch(filterProvider);
    ref.watch(onlyUnreadProvider);
    Future.microtask(() => load(reset: true));
    return const ArticleList(loading: true);
  }

  bool get unreadView {
    final f = ref.read(filterProvider);
    return f.kind == FilterKind.unread ||
        ((f.kind == FilterKind.folder || f.kind == FilterKind.source) &&
            ref.read(onlyUnreadProvider));
  }

  /// Changes still queued offline win over what the server says.
  List<Article> _pending(List<Article> items) {
    final side = ref.read(sidebarProvider).value;
    return _outbox.applyPending(
      items,
      folderOf: (id) => side?.subFor(id)?.folderId,
    );
  }

  String? get _userId => ref.read(sessionProvider).value?.id;

  Future<void> load({bool reset = false}) async {
    if (!reset && (state.loading || state.done)) return;
    final seq = ++_seq;
    final f = ref.read(filterProvider);
    if (reset) {
      // Paint the copy from the last session at once, then refresh it.
      final cached = await _cached(f);
      if (seq != _seq) return;
      state = ArticleList(items: cached ?? const [], loading: true);
    } else {
      state = state.copyWith(loading: true);
    }
    try {
      if (f.kind == FilterKind.forYou) {
        final items = await _api.forYou();
        if (seq != _seq) return;
        state = ArticleList(
          items: _pending(items),
          done: true,
          listedAt: DateTime.now(),
        );
        return;
      }
      final page = await _api.articles(
        unread: unreadView,
        saved: f.kind == FilterKind.saved,
        favorite: f.kind == FilterKind.favorites,
        folder: f.kind == FilterKind.folder ? f.id : null,
        source: f.kind == FilterKind.source ? f.id : null,
        cursor: reset ? null : state.cursor,
      );
      if (seq != _seq) return;
      var items = _pending(page.items);
      // Read here but not yet synced: the server still lists it as unread.
      if (unreadView) items = items.where((a) => !a.isRead).toList();
      state = ArticleList(
        // An article that already is in the list is never added twice (their
        // keys must be unique, and a repeated one leaves a blank tile).
        items: reset
            ? items
            : [
                ...state.items,
                ...items.where((n) => !state.items.any((o) => o.id == n.id)),
              ],
        cursor: page.nextCursor,
        done: page.nextCursor == null,
        listedAt: reset ? DateTime.now() : state.listedAt,
      );
      if (reset) unawaited(_saveSnapshot(f, items));
    } on ApiException catch (e) {
      if (seq != _seq) return;
      final keep = state.items.isNotEmpty;
      state = state.copyWith(
        loading: false,
        error: e,
        done: keep && e.isUnreachable ? true : null,
        offline: e.isUnreachable && keep,
      );
    }
  }

  /// The copy on the device for this list: the start-up snapshot, or the
  /// saved articles kept for offline reading.
  Future<List<Article>?> _cached(Filter f) async {
    final user = _userId;
    if (user == null) return null;
    if (f.kind == FilterKind.saved) {
      final saved = ref.read(offlineSavedProvider);
      if (saved.isNotEmpty) {
        return _pending([for (final o in saved.values) o.article]);
      }
    }
    final snap = await ref.read(localStoreProvider).loadHome(user);
    if (snap == null || snap.filterKey != _snapshotKey(f)) return null;
    return _pending(snap.articles);
  }

  String _snapshotKey(Filter f) => '${f.key}:${unreadView ? 'unread' : 'all'}';

  Future<void> _saveSnapshot(Filter f, List<Article> items) async {
    final user = _userId;
    final side = ref.read(sidebarProvider).value;
    if (user == null || side == null) return;
    await ref
        .read(localStoreProvider)
        .saveHome(
          userId: user,
          folders: side.folders,
          subs: side.subs,
          filterKey: _snapshotKey(f),
          articles: items,
        );
  }

  /// App start: send what's queued and fetch due feeds (cheap; the server
  /// skips feeds checked lately), reloading only if something arrived (or
  /// always with `force`, e.g. back online after showing the offline copy).
  Future<void> startUp({bool force = false}) async {
    await _outbox.flush();
    final before = _unreadInView();
    var arrived = 0;
    try {
      arrived = await _api.sync();
    } on ApiException {
      if (!force) return;
    }
    await ref.read(sidebarProvider.notifier).reload();
    if (force || arrived > 0 || _unreadInView() != before) {
      await load(reset: true);
    }
  }

  /// Pull to refresh: fetch this view's feeds now and reload. Returns how
  /// many articles reached the view; counting what's new to the reader, not
  /// only what this request fetched (another fetch may have stored them).
  Future<int> refresh() async {
    await _outbox.flush();
    final f = ref.read(filterProvider);
    final before = _unreadInView();
    var fetched = 0;
    ApiException? failure;
    try {
      fetched = await _api.refresh(
        source: f.kind == FilterKind.source ? f.id : null,
      );
    } on ApiException catch (e) {
      failure = e; // still reload what we have
    }
    await Future.wait([
      load(reset: true),
      ref.read(sidebarProvider.notifier).reload(),
    ]);
    if (failure != null && failure.code == 'refresh_cooldown') throw failure;
    final delta = _unreadInView() - before;
    return delta > fetched ? delta : fetched;
  }

  /// Unread count of the feeds this view shows (muted ones aside).
  int _unreadInView() {
    final side = ref.read(sidebarProvider).value;
    if (side == null) return 0;
    final f = ref.read(filterProvider);
    // Each view counts as the lists do: the unread and folder views by the
    // server's totals (one per story), a feed by its own badge.
    return switch (f.kind) {
      FilterKind.source => side.subFor(f.id!)?.unreadCount ?? 0,
      FilterKind.folder => side.unreadIn(f.id!),
      _ => side.unreadTotal,
    };
  }

  void _replace(Article a) {
    state = state.copyWith(
      items: [for (final x in state.items) x.id == a.id ? a : x],
    );
  }

  /// Applied on screen at once; sent now or queued until there's network.
  Future<void> _set(Article before, Article after, Field field, bool v) async {
    _replace(after);
    // Keep the start-up copy in step with what's on screen.
    unawaited(_saveSnapshot(ref.read(filterProvider), state.items));
    try {
      await _outbox.setState(before.id, field, v);
    } on ApiException {
      _replace(before); // permanent failure (e.g. the article is gone)
      if (field == Field.read) {
        ref
            .read(sidebarProvider.notifier)
            .adjustUnread(before.sourceId, v ? 1 : -1);
      }
    }
  }

  /// In the unread views a post leaves the list as soon as it is read (swipe,
  /// long press, opening it) and comes back to its place if marked unread
  /// again, as on the web.
  Future<void> setRead(Article a, bool read) async {
    if (a.isRead == read) return;
    ref.read(sidebarProvider.notifier).adjustUnread(a.sourceId, read ? -1 : 1);
    final after = a.copyWith(isRead: read);
    if (unreadView) {
      if (read) {
        state = state.copyWith(
          items: [
            for (final x in state.items)
              if (x.id != a.id) x,
          ],
        );
      } else if (_belongsHere(a)) {
        state = state.copyWith(
          items: insertedInOrder(state.items, after, atEnd: state.done),
        );
      }
    }
    await _set(a, after, Field.read, read);
  }

  /// Whether an article is one this view lists (for putting it back).
  bool _belongsHere(Article a) {
    final f = ref.read(filterProvider);
    final sub = ref.read(sidebarProvider).value?.subFor(a.sourceId);
    return switch (f.kind) {
      FilterKind.unread => !(sub?.muted ?? false),
      FilterKind.source => a.sourceId == f.id,
      FilterKind.folder => sub?.folderId == f.id,
      _ => false,
    };
  }

  Future<void> setSaved(Article a, bool saved) async {
    await _set(a, a.copyWith(isSaved: saved), Field.saved, saved);
    ref.read(savedChangesProvider.notifier).bump();
  }

  Future<void> setFavorite(Article a, bool fav) =>
      _set(a, a.copyWith(isFavorite: fav), Field.favorite, fav);

  Future<void> markAllRead() async {
    final f = ref.read(filterProvider);
    final sent = await _outbox.run(
      MarkAll(
        state.listedAt ?? DateTime.now(),
        folderId: f.kind == FilterKind.folder ? f.id : null,
        sourceId: f.kind == FilterKind.source ? f.id : null,
      ),
    );
    if (sent == Sent.queued) {
      // Offline: shown read now, sent when the connection is back.
      state = state.copyWith(
        items: [for (final a in state.items) a.copyWith(isRead: true)],
      );
      return;
    }
    await Future.wait([
      load(reset: true),
      ref.read(sidebarProvider.notifier).reload(),
    ]);
  }
}
