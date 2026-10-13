import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/api/api_client.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/api/token_store.dart';
import 'package:ufeed/core/prefs.dart';
import 'package:ufeed/offline/local_store.dart';
import 'package:ufeed/offline/offline_audio.dart';

import 'fake_adapter.dart';

String _id(int n) => '00000000-0000-0000-0000-${n.toString().padLeft(12, '0')}';

Article _a(int n, {String lang = 'es'}) =>
    Article.fromJson({'id': _id(n), 'source_id': 's', 'lang': lang});

void main() {
  late Directory dir;
  late LocalStore store;
  late FakeAdapter adapter;
  late List<Uri> downloads;
  late int status;

  ApiClient client() => ApiClient(
    baseUrl: 'https://test/api',
    tokens: MemoryTokenStore()
      ..tokens = const Tokens(access: 'a', refresh: 'r'),
    locale: () => 'es',
    dio: Dio()..httpClientAdapter = adapter,
  );

  Future<void> fakeDownload(Uri url, File to) async {
    downloads.add(url);
    await to.writeAsString('mp3:${url.path}');
  }

  Future<void> warm(List<Article> saved, {bool all = true}) => warmAudio(
    api: client(),
    store: store,
    saved: saved,
    prefs: const SpeechPrefs(server: true, offlineAudio: true),
    all: all,
    download: fakeDownload,
  );

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('ufeed_audio_test');
    store = LocalStore(() async => dir);
    downloads = [];
    status = 200;
    adapter = FakeAdapter((req) {
      final id = req.path.split('/')[2];
      return (
        status: status,
        body: status == 200
            ? {'url': '/api/audio/$id.mp3', 'lang': 'es', 'cached': true}
            : {
                'error': {'code': 'plan_limit_tts', 'message': 'x'},
              },
        headers: null,
      );
    });
  });

  tearDown(() => dir.delete(recursive: true));

  test('keeps the recordings of saved articles and plays them back', () async {
    await warm([_a(1), _a(2)]);
    expect(downloads, hasLength(2));
    final f = await store.audioFile(_id(1), 'es', 'f');
    expect(await f!.readAsString(), 'mp3:/api/audio/${_id(1)}.mp3');
    // Already there: nothing is downloaded again.
    await warm([_a(1), _a(2)]);
    expect(downloads, hasLength(2));
  });

  test('skips languages the server voice does not speak', () async {
    await warm([_a(1, lang: 'fr')]);
    expect(downloads, isEmpty);
    expect(adapter.calls, isEmpty);
  });

  test('drops recordings of articles no longer saved', () async {
    await warm([_a(1), _a(2)]);
    await warm([_a(2)]);
    expect(await store.audioFile(_id(1), 'es', 'f'), isNull);
    expect(await store.audioFile(_id(2), 'es', 'f'), isNotNull);
  });

  test('a single newly saved article does not prune the rest', () async {
    await warm([_a(1)]);
    await warm([_a(2)], all: false);
    expect(await store.audioFile(_id(1), 'es', 'f'), isNotNull);
  });

  test('stops at the plan limit and keeps nothing half-written', () async {
    status = 403;
    await warm([_a(1), _a(2)]);
    expect(adapter.calls, hasLength(1));
    expect(await store.audioFile(_id(1), 'es', 'f'), isNull);
  });

  test('sign out removes the recordings', () async {
    await warm([_a(1)]);
    await store.clearAudio();
    expect(await store.audioFile(_id(1), 'es', 'f'), isNull);
  });
}
