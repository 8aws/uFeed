import '../api/models.dart';
import '../features/home/article_tile.dart' show plainText;

/// Articles the device keeps for searching without a connection: the ones the
/// lists loaded lately (newest first, at most [recentMax]).
const recentMax = 200;

/// A kept article's HTML is dropped past this size: the excerpt still reads and
/// searches, and the cache stays small.
const _keepHtmlUpTo = 30000;

DateTime _when(Article a) =>
    a.publishedAt ?? a.fetchedAt ?? DateTime.fromMillisecondsSinceEpoch(0);

/// Lower case without accents, so "pirámide" finds "Piramide" and back.
String normalize(String s) {
  const from = 'áàäâãéèëêíìïîóòöôõúùüûñç';
  const to = 'aaaaaeeeeiiiiooooouuuunc';
  final b = StringBuffer();
  for (final ch in s.toLowerCase().split('')) {
    final i = from.indexOf(ch);
    b.write(i < 0 ? ch : to[i]);
  }
  return b.toString();
}

/// The words of a query, normalised (all of them must appear).
List<String> queryWords(String query) => [
  for (final w in normalize(query).split(RegExp(r'\s+')))
    if (w.isNotEmpty) w,
];

/// Whether every word is in the title, the feed's name, the excerpt or the text.
bool matchesQuery(Article a, String sourceTitle, List<String> words) {
  if (words.isEmpty) return false;
  final hay = normalize(
    [
      a.title ?? '',
      sourceTitle,
      plainText(a.summary),
      plainText(a.contentHtml),
    ].join(' '),
  );
  return words.every(hay.contains);
}

/// What the device holds that matches: newest first, each article once.
List<Article> searchLocal({
  required String query,
  required Iterable<Article> pool,
  required String Function(String sourceId) sourceOf,
  bool Function(Article a)? where,
  int limit = 60,
}) {
  final words = queryWords(query);
  final seen = <String>{};
  final found = [
    for (final a in pool)
      if ((where?.call(a) ?? true) &&
          seen.add(a.id) &&
          matchesQuery(a, sourceOf(a.sourceId), words))
        a,
  ]..sort((x, y) => _when(y).compareTo(_when(x)));
  return found.take(limit).toList();
}

/// The kept articles plus what just arrived: each once (the newer copy wins),
/// newest first, at most [recentMax].
List<Article> mergeRecent(List<Article> kept, List<Article> incoming) {
  final byId = <String, Article>{for (final a in kept) a.id: a};
  for (final a in incoming) {
    byId[a.id] = (a.contentHtml?.length ?? 0) > _keepHtmlUpTo
        ? a.withoutHtml()
        : a;
  }
  final all = byId.values.toList()
    ..sort((x, y) => _when(y).compareTo(_when(x)));
  return all.take(recentMax).toList();
}
