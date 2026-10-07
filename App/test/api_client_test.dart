import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/api/api_client.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/api/token_store.dart';

/// Answers requests from a handler instead of the network.
class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.handler);

  final ({int status, Object? body, Map<String, List<String>>? headers})
  Function(RequestOptions req)
  handler;
  final calls = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls.add(options);
    final r = handler(options);
    return ResponseBody.fromString(
      r.body == null ? '' : jsonEncode(r.body),
      r.status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
        ...?r.headers,
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

const _tokens = {
  'access_token': 'new-access',
  'refresh_token': 'new-refresh',
  'token_type': 'bearer',
};

void main() {
  late MemoryTokenStore store;
  late FakeAdapter adapter;
  late bool signedOut;

  ApiClient client(FakeAdapter a) {
    final dio = Dio()..httpClientAdapter = a;
    return ApiClient(
      baseUrl: 'https://test/api',
      tokens: store,
      locale: () => 'es',
      onSignedOut: () => signedOut = true,
      dio: dio,
    );
  }

  setUp(() {
    store = MemoryTokenStore()
      ..tokens = const Tokens(access: 'old-access', refresh: 'old-refresh');
    signedOut = false;
  });

  test('sends the bearer token and the language', () async {
    adapter = FakeAdapter(
      (_) => (status: 200, body: <Object>[], headers: null),
    );
    await client(adapter).folders();
    final req = adapter.calls.single;
    expect(req.headers['Authorization'], 'Bearer old-access');
    expect(req.headers['Accept-Language'], 'es');
  });

  test('refreshes once on 401 and retries with the new token', () async {
    adapter = FakeAdapter((req) {
      if (req.path.endsWith('/auth/refresh')) {
        return (status: 200, body: _tokens, headers: null);
      }
      final ok = req.headers['Authorization'] == 'Bearer new-access';
      return ok
          ? (status: 200, body: <Object>[], headers: null)
          : (status: 401, body: null, headers: null);
    });
    final api = client(adapter);
    // Two calls at once share a single refresh.
    await Future.wait([api.folders(), api.sources()]);
    expect(
      adapter.calls.where((c) => c.path.endsWith('/auth/refresh')).length,
      1,
    );
    expect(store.tokens!.access, 'new-access');
    expect(signedOut, isFalse);
  });

  test('a rejected refresh signs the user out', () async {
    adapter = FakeAdapter((_) => (status: 401, body: null, headers: null));
    await expectLater(
      client(adapter).folders(),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)),
    );
    expect(store.tokens, isNull);
    expect(signedOut, isTrue);
  });

  test('reads the server error code and Retry-After', () async {
    adapter = FakeAdapter(
      (_) => (
        status: 429,
        body: {
          'error': {'code': 'refresh_cooldown', 'message': 'Wait'},
        },
        headers: {
          'retry-after': ['42'],
        },
      ),
    );
    await expectLater(
      client(adapter).sync(),
      throwsA(
        isA<ApiException>()
            .having((e) => e.code, 'code', 'refresh_cooldown')
            .having((e) => e.retryAfter, 'retryAfter', 42),
      ),
    );
  });

  test('parses an article page', () async {
    adapter = FakeAdapter(
      (req) => (
        status: 200,
        body: {
          'items': [
            {
              'id': 'a1',
              'source_id': 's1',
              'url': 'https://example.com/post',
              'title': 'Hola',
              'author': null,
              'summary': '<p>Uno &amp; dos</p>',
              'ai_summary': null,
              'content_html': null,
              'image_url': null,
              'lang': 'es',
              'word_count': 300,
              'tags': <String>[],
              'published_at': '2026-10-07T10:00:00Z',
              'is_read': false,
              'is_saved': true,
              'is_favorite': false,
              'dup_count': 2,
            },
          ],
          'next_cursor': 'c2',
        },
        headers: null,
      ),
    );
    final page = await client(adapter).articles(unread: true, source: 's1');
    expect(adapter.calls.single.queryParameters, {
      'source': 's1',
      'unread': true,
      'limit': 30,
    });
    expect(page.nextCursor, 'c2');
    final a = page.items.single;
    expect(a.title, 'Hola');
    expect(a.isSaved, isTrue);
    expect(a.publishedAt, DateTime.utc(2026, 10, 7, 10));
  });
}
