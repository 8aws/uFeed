import 'dart:convert';
import 'dart:ui';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../api/token_store.dart';
import '../core/config.dart';
import '../core/prefs.dart';
import '../offline/providers.dart';

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

  /// The account, kept so the app opens without network.
  static const _userKey = 'ufeed_user';

  User? _cachedUser() {
    final raw = ref.read(prefsProvider).getString(_userKey);
    return raw == null ? null : User.fromJson(jsonDecode(raw) as Json);
  }

  Future<User> _fetchMe() async {
    final me = await _api.me();
    await ref.read(prefsProvider).setString(_userKey, jsonEncode(me.toJson()));
    return me;
  }

  @override
  Future<User?> build() async {
    if (await _tokens.read() == null) return null;
    try {
      return await _fetchMe();
    } on ApiException catch (e) {
      if (e.status == 401) return null; // the refresh failed too
      // No network: carry on with the saved account and the offline copy.
      final cached = _cachedUser();
      if (cached != null && e.isNetwork) return cached;
      rethrow; // nothing saved yet: the app shows a retry screen
    }
  }

  Future<void> login(String email, String password) async {
    await _tokens.save(await _api.login(email, password));
    state = AsyncData(await _fetchMe());
  }

  Future<void> register(String email, String password) async {
    await _tokens.save(await _api.register(email, password));
    state = AsyncData(await _fetchMe());
  }

  /// Nothing of the account stays on the device.
  Future<void> logout() async {
    await _wipe();
    state = const AsyncData(null);
  }

  Future<void> _wipe() async {
    await _tokens.clear();
    await ref.read(prefsProvider).remove(_userKey);
    await ref.read(outboxProvider).clear();
    await ref.read(localStoreProvider).clear();
  }

  void signedOut() {
    _wipe().ignore();
    state = const AsyncData(null);
  }

  Future<void> retry() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(build);
  }
}
