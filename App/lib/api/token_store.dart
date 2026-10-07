import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models.dart';

/// Where the session's tokens live between launches.
abstract class TokenStore {
  Future<Tokens?> read();
  Future<void> save(Tokens tokens);
  Future<void> clear();
}

/// Keychain on iOS/macOS, Keystore-backed storage on Android.
class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;
  static const _access = 'ufeed_access';
  static const _refresh = 'ufeed_refresh';

  @override
  Future<Tokens?> read() async {
    final access = await _storage.read(key: _access);
    final refresh = await _storage.read(key: _refresh);
    if (access == null || refresh == null) return null;
    return Tokens(access: access, refresh: refresh);
  }

  @override
  Future<void> save(Tokens tokens) async {
    await _storage.write(key: _access, value: tokens.access);
    await _storage.write(key: _refresh, value: tokens.refresh);
  }

  @override
  Future<void> clear() async {
    await _storage.delete(key: _access);
    await _storage.delete(key: _refresh);
  }
}

/// For tests.
class MemoryTokenStore implements TokenStore {
  Tokens? tokens;

  @override
  Future<Tokens?> read() async => tokens;

  @override
  Future<void> save(Tokens t) async => tokens = t;

  @override
  Future<void> clear() async => tokens = null;
}
