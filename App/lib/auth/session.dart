import 'dart:ui';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../api/token_store.dart';
import '../core/config.dart';

/// The app language sent to the server: the device's if we have it, else English.
String deviceLocale() {
  final code = PlatformDispatcher.instance.locale.languageCode;
  return code == 'es' ? 'es' : 'en';
}

final tokenStoreProvider = Provider<TokenStore>((ref) => SecureTokenStore());

final apiProvider = Provider<ApiClient>((ref) {
  return ApiClient(
    baseUrl: apiBase,
    tokens: ref.watch(tokenStoreProvider),
    locale: deviceLocale,
    // The refresh token was rejected (expired, password changed elsewhere…).
    onSignedOut: () => ref.read(sessionProvider.notifier).signedOut(),
  );
});

/// Who is signed in: `null` when nobody is.
final sessionProvider = AsyncNotifierProvider<Session, User?>(Session.new);

class Session extends AsyncNotifier<User?> {
  ApiClient get _api => ref.read(apiProvider);
  TokenStore get _tokens => ref.read(tokenStoreProvider);

  @override
  Future<User?> build() async {
    if (await _tokens.read() == null) return null;
    try {
      return await _api.me();
    } on ApiException catch (e) {
      if (e.status == 401) return null; // the refresh failed too
      rethrow; // no network: the app shows a retry screen
    }
  }

  Future<void> login(String email, String password) async {
    await _tokens.save(await _api.login(email, password));
    state = AsyncData(await _api.me());
  }

  Future<void> register(String email, String password) async {
    await _tokens.save(await _api.register(email, password));
    state = AsyncData(await _api.me());
  }

  Future<void> logout() async {
    await _tokens.clear();
    state = const AsyncData(null);
  }

  void signedOut() => state = const AsyncData(null);

  Future<void> retry() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(build);
  }
}
