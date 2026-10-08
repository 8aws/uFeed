import 'dart:convert';
import 'dart:io';

import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:path_provider/path_provider.dart';

import '../api/models.dart';

/// What the app keeps on the device between launches, as JSON files:
///
/// - `home.json`: the side menu and the first page of the last list, painted
///   at once on start (then replaced by fresh data), so the app never opens
///   blank or with a spinner, and works without network.
/// - `saved.json`: the saved articles with their full text, readable
///   offline; their pictures go to the image cache.
///
/// Everything belongs to the signed-in account and is wiped on sign out.
class LocalStore {
  LocalStore([Future<Directory> Function()? dir])
    : _dir = dir ?? getApplicationSupportDirectory;

  final Future<Directory> Function() _dir;

  Future<File> _file(String name) async =>
      File('${(await _dir()).path}/ufeed_$name.json');

  Future<Json?> _read(String name) async {
    try {
      final f = await _file(name);
      if (!await f.exists()) return null;
      return jsonDecode(await f.readAsString()) as Json;
    } on Object {
      return null; // damaged or from an older version: start fresh
    }
  }

  Future<void> _write(String name, Json data) async {
    final f = await _file(name);
    final tmp = File('${f.path}.tmp');
    await tmp.writeAsString(jsonEncode(data));
    await tmp.rename(f.path); // never leave a half-written file
  }

  // Start-up snapshot

  Future<void> saveHome({
    required String userId,
    required List<Folder> folders,
    required List<Subscription> subs,
    required String filterKey,
    required List<Article> articles,
  }) => _write('home', {
    'user': userId,
    'folders': [for (final f in folders) f.toJson()],
    'subs': [for (final s in subs) s.toJson()],
    'filter': filterKey,
    'articles': [for (final a in articles.take(30)) a.toJson()],
  });

  Future<HomeSnapshot?> loadHome(String userId) async {
    final j = await _read('home');
    if (j == null || j['user'] != userId) return null;
    return HomeSnapshot(
      folders: [
        for (final f in j['folders'] as List) Folder.fromJson(f as Json),
      ],
      subs: [
        for (final s in j['subs'] as List) Subscription.fromJson(s as Json),
      ],
      filterKey: j['filter'] as String,
      articles: [
        for (final a in j['articles'] as List) Article.fromJson(a as Json),
      ],
    );
  }

  // Saved articles

  Future<void> saveSaved(String userId, List<OfflineArticle> items) =>
      _write('saved', {
        'user': userId,
        'items': [for (final i in items) i.toJson()],
      });

  Future<List<OfflineArticle>> loadSaved(String userId) async {
    final j = await _read('saved');
    if (j == null || j['user'] != userId) return const [];
    return [
      for (final i in j['items'] as List) OfflineArticle.fromJson(i as Json),
    ];
  }

  /// On sign out: nothing of that account stays on the device.
  Future<void> clear() async {
    for (final name in ['home', 'saved']) {
      final f = await _file(name);
      if (await f.exists()) await f.delete();
    }
    await DefaultCacheManager().emptyCache();
  }
}

class HomeSnapshot {
  const HomeSnapshot({
    required this.folders,
    required this.subs,
    required this.filterKey,
    required this.articles,
  });

  final List<Folder> folders;
  final List<Subscription> subs;
  final String filterKey;
  final List<Article> articles;
}

/// A saved article as kept for offline reading: with the full text from its
/// web page when the feed only gave an excerpt.
class OfflineArticle {
  const OfflineArticle(this.article, this.fullHtml);

  final Article article;
  final String? fullHtml;

  Json toJson() => {'article': article.toJson(), 'full': fullHtml};

  factory OfflineArticle.fromJson(Json j) => OfflineArticle(
    Article.fromJson(j['article'] as Json),
    j['full'] as String?,
  );
}
