import 'dart:io';

import '../api/api_client.dart';
import '../api/models.dart';
import '../auth/session.dart';
import '../core/prefs.dart';
import '../features/reader/article_page.dart';
import 'local_store.dart';

/// Recordings kept for the most recent saved articles (~1.5 MB each).
const maxAudioArticles = 20;
const _serverLangs = {'es', 'en'};

/// The language an article is read in, and whether it's translated first.
({String lang, bool translated}) speechLang(Article a, SpeechPrefs prefs) {
  final translated = prefs.myLanguage && canTranslate(a);
  return (
    lang: translated ? deviceLocale() : baseLang(a.lang ?? deviceLocale()),
    translated: translated,
  );
}

/// Downloads [url] to [to]; the server streams a recording it's still
/// generating, so this ends when the whole MP3 is there.
Future<void> downloadTo(Uri url, File to) async {
  final client = HttpClient();
  try {
    final res = await (await client.getUrl(url)).close();
    if (res.statusCode != 200) {
      throw HttpException('HTTP ${res.statusCode}', uri: url);
    }
    final sink = to.openWrite();
    try {
      await res.pipe(sink);
    } finally {
      await sink.close();
    }
  } finally {
    client.close();
  }
}

bool _warming = false;

/// Keeps the server voice of the saved articles on the device, newest first,
/// so they can be listened to offline (the device voice already works
/// offline). [all] is the whole saved list: recordings of articles no longer
/// in it are dropped.
Future<void> warmAudio({
  required ApiClient api,
  required LocalStore store,
  required List<Article> saved,
  required SpeechPrefs prefs,
  bool all = true,
  Future<void> Function(Uri url, File to) download = downloadTo,
}) async {
  if (_warming) return;
  _warming = true;
  try {
    final wanted = saved.take(maxAudioArticles).toList();
    if (all) await store.pruneAudio({for (final a in wanted) a.id});
    for (final a in wanted) {
      final (:lang, :translated) = speechLang(a, prefs);
      if (!_serverLangs.contains(lang)) continue;
      if (await store.audioFile(a.id, lang, prefs.gender) != null) continue;
      try {
        final audio = await api.articleAudio(
          a.id,
          lang: lang,
          voice: prefs.gender,
          translated: translated,
        );
        await store.putAudio(
          a.id,
          lang,
          prefs.gender,
          (to) => download(audio.url, to),
        );
      } on ApiException catch (e) {
        // Plan, quota or connection: try again on the next sync.
        if (e.isNetwork || e.status == 403 || e.status == 429) return;
      } on IOException {
        return; // connection dropped mid-download
      }
    }
  } finally {
    _warming = false;
  }
}
