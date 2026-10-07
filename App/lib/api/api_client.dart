import 'dart:async';

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
  Future<bool> _refresh() => _refreshing ??= () async {
    try {
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
    } finally {
      _refreshing = null;
    }
  }();

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

  Future<void> setRead(String id, bool read) =>
      _request(read ? 'POST' : 'DELETE', '/articles/$id/read');

  Future<void> setSaved(String id, bool saved) =>
      _request(saved ? 'POST' : 'DELETE', '/articles/$id/save');

  Future<void> setFavorite(String id, bool favorite) =>
      _request(favorite ? 'POST' : 'DELETE', '/articles/$id/favorite');

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
