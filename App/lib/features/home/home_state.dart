import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/api_client.dart';
import '../../api/models.dart';
import '../../auth/session.dart';

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
}

class Sidebar {
  const Sidebar({required this.folders, required this.subs});

  final List<Folder> folders;
  final List<Subscription> subs;

  int get unreadTotal =>
      subs.where((s) => !s.muted).fold(0, (n, s) => n + s.unreadCount);

  int unreadIn(String folderId) => subs
      .where((s) => s.folderId == folderId && !s.muted)
      .fold(0, (n, s) => n + s.unreadCount);

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
  );
}

final sidebarProvider = AsyncNotifierProvider<SidebarNotifier, Sidebar>(
  SidebarNotifier.new,
);

class SidebarNotifier extends AsyncNotifier<Sidebar> {
  @override
  Future<Sidebar> build() async {
    final api = ref.watch(apiProvider);
    final (folders, subs) = await (api.folders(), api.sources()).wait;
    folders.sort((a, b) => a.position.compareTo(b.position));
    return Sidebar(folders: folders, subs: subs);
  }

  void adjustUnread(String sourceId, int delta) {
    final s = state.value;
    if (s != null) state = AsyncData(s.adjustUnread(sourceId, delta));
  }

  Future<void> reload() async {
    state = await AsyncValue.guard(build);
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
  });

  final List<Article> items;
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
  }) => ArticleList(
    items: items ?? this.items,
    cursor: cursor ?? this.cursor,
    loading: loading ?? this.loading,
    done: done ?? this.done,
    error: error,
    listedAt: listedAt ?? this.listedAt,
  );
}

final articleListProvider = NotifierProvider<ArticleListNotifier, ArticleList>(
  ArticleListNotifier.new,
);

class ArticleListNotifier extends Notifier<ArticleList> {
  int _seq = 0;

  ApiClient get _api => ref.read(apiProvider);

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

  Future<void> load({bool reset = false}) async {
    if (!reset && (state.loading || state.done)) return;
    final seq = ++_seq;
    final f = ref.read(filterProvider);
    state = reset
        ? const ArticleList(loading: true)
        : state.copyWith(loading: true);
    try {
      if (f.kind == FilterKind.forYou) {
        final items = await _api.forYou();
        if (seq != _seq) return;
        state = ArticleList(items: items, done: true, listedAt: DateTime.now());
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
      state = ArticleList(
        items: reset ? page.items : [...state.items, ...page.items],
        cursor: page.nextCursor,
        done: page.nextCursor == null,
        listedAt: reset ? DateTime.now() : state.listedAt,
      );
    } on ApiException catch (e) {
      if (seq != _seq) return;
      state = state.copyWith(loading: false, error: e);
    }
  }

  /// Pull to refresh: fetch due feeds, then reload list and counters.
  /// `onlyIfNew` (app start, list already loading): skip if nothing arrived.
  Future<void> refresh({bool onlyIfNew = false}) async {
    var arrived = 0;
    try {
      arrived = await _api.sync();
    } on ApiException {
      // still reload what we have
    }
    if (onlyIfNew && arrived == 0) return;
    await Future.wait([
      load(reset: true),
      ref.read(sidebarProvider.notifier).reload(),
    ]);
  }

  void _replace(Article a) {
    state = state.copyWith(
      items: [for (final x in state.items) x.id == a.id ? a : x],
    );
  }

  Future<void> setRead(Article a, bool read) async {
    if (a.isRead == read) return;
    _replace(a.copyWith(isRead: read));
    ref.read(sidebarProvider.notifier).adjustUnread(a.sourceId, read ? -1 : 1);
    try {
      await _api.setRead(a.id, read);
    } on ApiException {
      _replace(a);
      ref
          .read(sidebarProvider.notifier)
          .adjustUnread(a.sourceId, read ? 1 : -1);
    }
  }

  Future<void> setSaved(Article a, bool saved) async {
    _replace(a.copyWith(isSaved: saved));
    try {
      await _api.setSaved(a.id, saved);
    } on ApiException {
      _replace(a);
    }
  }

  Future<void> setFavorite(Article a, bool fav) async {
    _replace(a.copyWith(isFavorite: fav));
    try {
      await _api.setFavorite(a.id, fav);
    } on ApiException {
      _replace(a);
    }
  }

  Future<void> markAllRead() async {
    final f = ref.read(filterProvider);
    await _api.markAllRead(
      folderId: f.kind == FilterKind.folder ? f.id : null,
      sourceId: f.kind == FilterKind.source ? f.id : null,
      before: state.listedAt,
    );
    await Future.wait([
      load(reset: true),
      ref.read(sidebarProvider.notifier).reload(),
    ]);
  }
}
