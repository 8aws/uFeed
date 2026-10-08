import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

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
