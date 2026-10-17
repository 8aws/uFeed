import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import 'models.dart';
import 'token_store.dart';

/// An error answer from the server: `{"error": {"code", "message"}}`.
class ApiException implements Exception {
  const ApiException(this.status, this.code, this.message, {this.retryAfter});

  final int status;
  final String code;
  final String message;

  /// Seconds to wait (Retry-After), e.g. plan refresh cooldowns.
  final int? retryAfter;

  /// No answer at all (no network, server down, timeout).
  bool get isNetwork => status == 0;

  /// Our server isn't really there: no network, a server error, or an answer
  /// that isn't our API (a proxy or firewall page, e.g. a country block).
  /// The app then works from the copy on the device.
  bool get isUnreachable =>
      isNetwork || status >= 500 || code.startsWith('http_');

  @override
  String toString() => 'ApiException($status, $code, $message)';
}

/// The uFeed API, mirroring the web client (Frontend/src/lib/api.ts): bearer
/// token on every call, one refresh-and-retry on 401, and the session is
/// dropped when the refresh token is no longer valid.
class ApiClient {
  ApiClient({
    required String baseUrl,
    required this.tokens,
    required this.locale,
    this.onSignedOut,
    Dio? dio,
  }) : _dio =
           dio ??
           Dio(
             BaseOptions(
               connectTimeout: const Duration(seconds: 10),
               receiveTimeout: const Duration(seconds: 60),
             ),
           ) {
    _dio.options.baseUrl = baseUrl;
    // Errors are read from the response, not thrown by status.
    _dio.options.validateStatus = (_) => true;
  }

  final Dio _dio;
  final TokenStore tokens;
  final String Function() locale;
  final void Function()? onSignedOut;
  Future<bool>? _refreshing;

  Future<Response<Object?>> _raw(
    String method,
    String path, {
    Object? body,
    Map<String, Object?>? query,
    bool auth = true,
  }) async {
    final headers = <String, Object>{'Accept-Language': locale()};
    if (auth) {
      final t = await tokens.read();
      if (t != null) headers['Authorization'] = 'Bearer ${t.access}';
    }
    try {
      return await _dio.request<Object?>(
        path,
        data: body,
        queryParameters: query == null
            ? null
            : {
                for (final e in query.entries)
                  if (e.value != null) e.key: e.value,
              },
        options: Options(method: method, headers: headers),
      );
    } on DioException catch (e) {
      throw ApiException(0, 'network', e.message ?? e.type.name);
    }
  }

  /// One refresh at a time: concurrent 401s wait for the same attempt.
  Future<bool> _refresh() =>
      _refreshing ??= _renew().whenComplete(() => _refreshing = null);

  Future<bool> _renew() async {
    final t = await tokens.read();
    if (t == null) return false;
    final resp = await _raw(
      'POST',
      '/auth/refresh',
      body: {'refresh_token': t.refresh},
      auth: false,
    );
    if (resp.statusCode != 200) return false;
    await tokens.save(Tokens.fromJson(resp.data as Json));
    return true;
  }

  Future<Object?> _request(
    String method,
    String path, {
    Object? body,
    Map<String, Object?>? query,
    bool auth = true,
  }) async {
    final sentWith = (await tokens.read())?.access;
    var resp = await _raw(method, path, body: body, query: query, auth: auth);
    if (resp.statusCode == 401 && auth) {
      // Another call may have refreshed while this one was in flight.
      final renewed = (await tokens.read())?.access != sentWith;
      if (renewed || await _refresh()) {
        resp = await _raw(method, path, body: body, query: query);
      } else {
        await tokens.clear();
        onSignedOut?.call();
      }
    }
    final status = resp.statusCode ?? 0;
    if (status < 200 || status >= 300) {
      var code = 'http_$status';
      var message = resp.statusMessage ?? '';
      final data = resp.data;
      if (data is Map && data['error'] is Map) {
        final err = data['error'] as Map;
        code = err['code'] as String? ?? code;
        message = err['message'] as String? ?? message;
      }
      final ra = int.tryParse(resp.headers.value('retry-after') ?? '');
      throw ApiException(
        status,
        code,
        message,
        retryAfter: ra != null && ra > 0 ? ra : null,
      );
    }
    return resp.data;
  }

  Future<Json> _json(
    String method,
    String path, {
    Object? body,
    Map<String, Object?>? query,
    bool auth = true,
  }) async =>
      await _request(method, path, body: body, query: query, auth: auth)
          as Json;

  Future<List<T>> _list<T>(
    String path,
    T Function(Json) item, {
    Map<String, Object?>? query,
  }) async {
    final data = await _request('GET', path, query: query) as List;
    return [for (final e in data) item(e as Json)];
  }

  // auth

  Future<SiteConfig> site() async =>
      SiteConfig.fromJson(await _json('GET', '/site', auth: false));

  Future<Tokens> login(String email, String password) async => Tokens.fromJson(
    await _json(
      'POST',
      '/auth/login',
      body: {'email': email, 'password': password},
      auth: false,
    ),
  );

  Future<Tokens> register(String email, String password) async {
    final data = await _json(
      'POST',
      '/auth/register',
      body: {'email': email, 'password': password, 'locale': locale()},
      auth: false,
    );
    return Tokens.fromJson(data['tokens'] as Json);
  }

  /// Use the app without registering: an account with no personal data.
  Future<Tokens> guest() async {
    final data = await _json(
      'POST',
      '/auth/guest',
      body: {'locale': locale()},
      auth: false,
    );
    return Tokens.fromJson(data['tokens'] as Json);
  }

  /// A guest registers: same feeds and saved articles, now with credentials.
  Future<Tokens> upgrade(String email, String password) async {
    final data = await _json(
      'POST',
      '/auth/upgrade',
      body: {'email': email, 'password': password},
    );
    return Tokens.fromJson(data['tokens'] as Json);
  }

  Future<void> forgotPassword(String email) =>
      _request('POST', '/auth/forgot', body: {'email': email}, auth: false);

  Future<User> me() async => User.fromJson(await _json('GET', '/me'));

  // sidebar

  Future<List<Folder>> folders() => _list('/folders', Folder.fromJson);

  Future<List<Subscription>> sources() =>
      _list('/sources', Subscription.fromJson);

  /// Fetches this user's due feeds (cheap; the server skips if done lately).
  /// Returns how many new articles arrived.
  Future<int> sync() async =>
      (await _json('POST', '/sync'))['new_articles'] as int? ?? 0;

  /// "Refresh" (pull down): fetch this user's feeds now, or one feed.
  /// Plans have a cooldown (429 refresh_cooldown with Retry-After).
  Future<int> refresh({String? source}) async =>
      (await _json(
            'POST',
            '/refresh',
            query: {'source': source},
          ))['new_articles']
          as int? ??
      0;

  // feeds and folders

  /// Feeds found at a site or feed address.
  Future<List<DiscoveredFeed>> discover(String url) async {
    final data =
        await _request('POST', '/discover', body: {'url': url}) as List;
    return [for (final e in data) DiscoveredFeed.fromJson(e as Json)];
  }

  Future<Subscription> subscribe(String url, {String? folderId}) async =>
      Subscription.fromJson(
        await _json(
          'POST',
          '/sources',
          body: {'url': url, 'folder_id': folderId},
        ),
      );

  /// Only the keys given are changed (`folder_id: null` = top level).
  Future<Subscription> updateSubscription(
    String id,
    Map<String, Object?> fields,
  ) async =>
      Subscription.fromJson(await _json('PATCH', '/sources/$id', body: fields));

  Future<void> unsubscribe(String id) => _request('DELETE', '/sources/$id');

  Future<Folder> createFolder(String name) async =>
      Folder.fromJson(await _json('POST', '/folders', body: {'name': name}));

  Future<Folder> renameFolder(String id, String name) async => Folder.fromJson(
    await _json('PATCH', '/folders/$id', body: {'name': name}),
  );

  /// Its feeds move to the top level.
  Future<void> deleteFolder(String id) => _request('DELETE', '/folders/$id');

  /// The starter list editors curated on this server; null = the built-in.
  Future<List<CatalogSection>?> catalog() async {
    final sections = (await _json('GET', '/catalog'))['sections'] as List?;
    return sections == null
        ? null
        : [for (final s in sections) CatalogSection.fromJson(s as Json)];
  }

  Future<String> exportOpml() async =>
      await _request('GET', '/opml/export') as String;

  Future<({int imported, int skipped})> importOpml(
    Uint8List bytes,
    String filename,
  ) async {
    final data = await _json(
      'POST',
      '/opml/import',
      body: FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: filename),
      }),
    );
    return (
      imported: data['imported'] as int? ?? 0,
      skipped: data['skipped'] as int? ?? 0,
    );
  }

  // filters

  Future<List<MutedKeyword>> keywords() =>
      _list('/filters/keywords', MutedKeyword.fromJson);

  Future<MutedKeyword> addKeyword(String keyword) async =>
      MutedKeyword.fromJson(
        await _json('POST', '/filters/keywords', body: {'keyword': keyword}),
      );

  Future<void> removeKeyword(String id) =>
      _request('DELETE', '/filters/keywords/$id');

  // account

  Future<User> updateMe(Map<String, Object?> fields) async =>
      User.fromJson(await _json('PATCH', '/me', body: fields));

  /// Returns fresh tokens: other sessions are signed out.
  Future<Tokens> changePassword(String current, String next) async =>
      Tokens.fromJson(
        await _json(
          'POST',
          '/me/password',
          body: {'current_password': current, 'new_password': next},
        ),
      );

  /// Deletes the account and all its data (a guest has no password).
  Future<void> deleteAccount([String password = '']) =>
      _request('POST', '/me/delete', body: {'password': password});

  // articles

  Future<Page<Article>> articles({
    String? folder,
    String? source,
    bool unread = false,
    bool saved = false,
    bool favorite = false,
    String? q,
    String? cursor,
    int limit = 30,
  }) async => Page.fromJson(
    await _json(
      'GET',
      '/articles',
      query: {
        'folder': folder,
        'source': source,
        if (unread) 'unread': true,
        if (saved) 'saved': true,
        if (favorite) 'favorite': true,
        'q': q,
        'cursor': cursor,
        'limit': limit,
      },
    ),
    Article.fromJson,
  );

  /// Articles picked for this user from what they read (no paging).
  Future<List<Article>> forYou({int limit = 40}) =>
      _list('/foryou', Article.fromJson, query: {'limit': limit});

  /// Trending rankings over the last `windowHours`.
  Future<Insights> insights({int windowHours = 720, int limit = 12}) async =>
      Insights.fromJson(
        await _json(
          'GET',
          '/insights',
          query: {'window_hours': windowHours, 'limit': limit},
        ),
      );

  Future<void> setRead(String id, bool read) =>
      _request(read ? 'POST' : 'DELETE', '/articles/$id/read');

  Future<void> setSaved(String id, bool saved) =>
      _request(saved ? 'POST' : 'DELETE', '/articles/$id/save');

  Future<void> setFavorite(String id, bool favorite) =>
      _request(favorite ? 'POST' : 'DELETE', '/articles/$id/favorite');

  /// The full article from its web page (feeds that publish an excerpt).
  /// Null when the page couldn't be read.
  Future<String?> fullText(String id) async =>
      (await _json('POST', '/articles/$id/full'))['html'] as String?;

  /// Machine translation into `lang`; `generate` creates it (~3-4 s).
  Future<Translation> translation(
    String id,
    String lang, {
    bool generate = false,
  }) async => Translation.fromJson(
    await _json(
      'GET',
      '/articles/$id/translation',
      query: {'lang': lang, 'generate': generate},
    ),
  );

  /// The AI summary in `lang`; `generate` queues it (plan priority).
  Future<AiSummary> aiSummary(
    String id,
    String lang, {
    bool generate = false,
  }) async => AiSummary.fromJson(
    await _json(
      'GET',
      '/articles/$id/ai-summary',
      query: {'lang': lang, 'generate': generate},
    ),
  );

  Future<List<Article>> similar(String id, {int limit = 6}) =>
      _list('/articles/$id/similar', Article.fromJson, query: {'limit': limit});

  /// How long the article was open and how far it was read (Trending).
  /// `at`: when it happened, for changes sent later from the offline queue.
  Future<void> readEvent(
    String id,
    Duration dwell,
    double completion, {
    DateTime? at,
  }) => _request(
    'POST',
    '/articles/$id/read-event',
    body: {
      'dwell_ms': dwell.inMilliseconds,
      'completion': completion,
      'at': at?.toUtc().toIso8601String(),
    },
  );

  /// open | share | skip, for the ranking signals.
  Future<void> engage(String id, String kind, {DateTime? at}) => _request(
    'POST',
    '/articles/$id/engage',
    body: {'kind': kind, 'at': at?.toUtc().toIso8601String()},
  );

  /// The article read aloud by the server voice (plan `tts_server`): a signed
  /// URL that plays the finished MP3, or follows it live while it's generated.
  Future<({Uri url, String lang, bool cached})> articleAudio(
    String id, {
    required String lang,
    String voice = 'f',
    bool translated = false,
  }) async {
    final data = await _json(
      'POST',
      '/articles/$id/audio',
      query: {'lang': lang, 'voice': voice, 'translated': translated},
    );
    return (
      url: Uri.parse(_dio.options.baseUrl).resolve(data['url'] as String),
      lang: data['lang'] as String,
      cached: data['cached'] as bool? ?? false,
    );
  }

  /// `before`: only what was already listed then (newer arrivals stay unread).
  Future<void> markAllRead({
    String? folderId,
    String? sourceId,
    DateTime? before,
  }) => _request(
    'POST',
    '/articles/mark-all-read',
    body: {
      'folder_id': folderId,
      'source_id': sourceId,
      'before': before?.toUtc().toIso8601String(),
    },
  );
}
