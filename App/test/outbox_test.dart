import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ufeed/api/api_client.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/api/token_store.dart';
import 'package:ufeed/offline/outbox.dart';

import 'fake_adapter.dart';

Article _article(String id, {bool read = false, DateTime? fetched}) => Article(
  id: id,
  sourceId: 's1',
  url: null,
  title: id,
  author: null,
  summary: null,
  aiSummary: null,
  contentHtml: null,
  imageUrl: null,
  lang: 'es',
  wordCount: null,
  publishedAt: fetched,
  fetchedAt: fetched,
  fullStatus: null,
  isRead: read,
  isSaved: false,
  isFavorite: false,
  dupCount: 1,
);

void main() {
  late bool online;
  late FakeAdapter adapter;
  late Outbox box;
  var clock = DateTime(2026, 10, 8, 10);

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    online = false;
    clock = DateTime(2026, 10, 8, 10);
    adapter = FakeAdapter((req) {
      if (!online) {
        throw DioException.connectionError(requestOptions: req, reason: 'off');
      }
      if (req.path.contains('gone')) {
        return (status: 404, body: null, headers: null);
      }
      return (status: 200, body: {'ok': true}, headers: null);
    });
    final api = ApiClient(
      baseUrl: 'https://test/api',
      tokens: MemoryTokenStore()
        ..tokens = const Tokens(access: 'a', refresh: 'r'),
      locale: () => 'es',
      dio: Dio()..httpClientAdapter = adapter,
    );
    box = Outbox(await SharedPreferences.getInstance(), api, now: () => clock);
  });

  test('offline changes are queued, keeping only the latest value', () async {
    expect(await box.setState('a1', Field.read, true), Sent.queued);
    clock = clock.add(const Duration(minutes: 1));
    expect(await box.setState('a1', Field.read, false), Sent.queued);
    expect(await box.setState('a1', Field.saved, true), Sent.queued);
    expect(box.count, 2);

    online = true;
    adapter.calls.clear();
    expect(await box.flush(), 2);
    expect(box.count, 0);
    expect(
      [for (final c in adapter.calls) '${c.method} ${c.path}'],
      ['DELETE /articles/a1/read', 'POST /articles/a1/save'],
    );
  });

  test('flush sends in the order things happened, with their time', () async {
    await box.run(MarkAll(clock, sourceId: 's1'));
    clock = clock.add(const Duration(minutes: 1));
    await box.setState('a1', Field.read, false);
    clock = clock.add(const Duration(minutes: 1));
    await box.run(ReadEvent(clock, 'a2', const Duration(seconds: 30), 0.8));

    online = true;
    adapter.calls.clear();
    expect(await box.flush(), 3);
    expect(
      [for (final c in adapter.calls) c.path],
      [
        '/articles/mark-all-read',
        '/articles/a1/read',
        '/articles/a2/read-event',
      ],
    );
    expect(
      (adapter.calls.last.data as Map)['at'],
      DateTime(2026, 10, 8, 10, 2).toUtc().toIso8601String(),
    );
  });

  test('permanent failures are dropped, not retried forever', () async {
    await box.setState('gone', Field.read, true);
    online = true;
    expect(await box.flush(), 0);
    expect(box.count, 0);
  });

  test('queued changes win over what the server says', () async {
    await box.run(MarkAll(clock, sourceId: 's1'));
    clock = clock.add(const Duration(minutes: 1));
    await box.setState('a2', Field.read, false);
    final items = box.applyPending([
      _article('a1', fetched: DateTime(2026, 10, 8, 9)),
      _article('a2', fetched: DateTime(2026, 10, 8, 9)),
      _article('a3', fetched: DateTime(2026, 10, 8, 11)), // arrived later
    ]);
    expect([for (final a in items) a.isRead], [true, false, false]);
  });
}
