import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../auth/session.dart';
import '../features/home/home_state.dart';
import '../features/reader/article_html.dart';
import '../features/reader/article_page.dart';
import 'local_store.dart';
import 'providers.dart';

/// How much of the saved list is kept on the device.
const _maxSaved = 200;
const _fullPerRun = 20; // full texts fetched per sync (one request each)
const _imagesPerArticle = 8;

final _imgSrc = RegExp(
  r'''<img\b[^>]*\bsrc\s*=\s*["']([^"']+)["']''',
  caseSensitive: false,
);

/// Keeps the saved articles readable offline: their text (the full article
/// when the feed only gave an excerpt) and pictures.
Future<void> syncSaved(WidgetRef ref) async {
  final user = ref.read(sessionProvider).value;
  if (user == null) return;
  final api = ref.read(apiProvider);
  final store = ref.read(localStoreProvider);
  final before = {
    for (final o in await store.loadSaved(user.id)) o.article.id: o,
  };

  final saved = <Article>[];
  String? cursor;
  try {
    do {
      final page = await api.articles(saved: true, cursor: cursor, limit: 100);
      saved.addAll(page.items);
      cursor = page.nextCursor;
    } while (cursor != null && saved.length < _maxSaved);
  } on ApiException {
    return; // offline: keep what we have
  }

  var fetched = 0;
  final out = <OfflineArticle>[];
  for (final a in saved.take(_maxSaved)) {
    var full = before[a.id]?.fullHtml;
    if (full == null &&
        isExcerpt(a) &&
        a.url != null &&
        fetched < _fullPerRun) {
      fetched++;
      try {
        full = await api.fullText(a.id);
      } on ApiException {
        // keep the excerpt
      }
    }
    out.add(OfflineArticle(a, full));
  }
  await store.saveSaved(user.id, out);
  ref.read(offlineSavedProvider.notifier).set(out);
  unawaited(_cacheImages(out.where((o) => !before.containsKey(o.article.id))));
}

/// Pictures of newly saved articles into the image cache the reader uses.
Future<void> _cacheImages(Iterable<OfflineArticle> items) async {
  final cache = DefaultCacheManager();
  for (final o in items) {
    final a = o.article;
    final base = safeUri(a.url);
    final html = o.fullHtml ?? a.contentHtml ?? a.summary ?? '';
    final urls = <Uri>{
      if (safeUri(a.imageUrl) != null) safeUri(a.imageUrl)!,
      for (final m in _imgSrc.allMatches(html).take(_imagesPerArticle))
        if (safeUri(m.group(1), base) != null) safeUri(m.group(1), base)!,
    };
    for (final u in urls) {
      try {
        await cache.downloadFile(u.toString());
      } on Object {
        // a broken picture shouldn't stop the rest
      }
    }
  }
}

/// Sends what was queued offline and refreshes the offline copy: on start,
/// when the connection comes back and when the app returns to the front.
class OfflineSync extends ConsumerStatefulWidget {
  const OfflineSync({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<OfflineSync> createState() => _OfflineSyncState();
}

class _OfflineSyncState extends ConsumerState<OfflineSync> {
  StreamSubscription<List<ConnectivityResult>>? _net;
  AppLifecycleListener? _life;
  bool _wasOffline = false;
  Timer? _savedTimer;

  @override
  void initState() {
    super.initState();
    Future.microtask(() async {
      final user = ref.read(sessionProvider).value;
      if (user == null) return;
      final kept = await ref.read(localStoreProvider).loadSaved(user.id);
      if (mounted) ref.read(offlineSavedProvider.notifier).set(kept);
      await _online();
    });
    _net = Connectivity().onConnectivityChanged.listen((r) {
      final offline = r.every((c) => c == ConnectivityResult.none);
      if (_wasOffline && !offline) _online().ignore();
      _wasOffline = offline;
    });
    _life = AppLifecycleListener(onResume: () => _online().ignore());
  }

  Future<void> _online() async {
    if (!mounted) return;
    final sent = await ref.read(outboxProvider).flush();
    if (!mounted) return;
    final list = ref.read(articleListProvider);
    if (sent > 0 || list.offline || list.error != null) {
      await ref.read(articleListProvider.notifier).refresh();
    }
    if (mounted) await syncSaved(ref);
  }

  @override
  void dispose() {
    _net?.cancel();
    _life?.dispose();
    _savedTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Saving/unsaving: refresh the offline copy a moment later (batched).
    ref.listen(savedChangesProvider, (_, _) {
      _savedTimer?.cancel();
      _savedTimer = Timer(const Duration(seconds: 3), () {
        if (mounted) syncSaved(ref).ignore();
      });
    });
    return widget.child;
  }
}
