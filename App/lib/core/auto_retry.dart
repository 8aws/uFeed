import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';

/// Tries [attempt] again until it reports success: after 5 s, 10 s, 20 s…
/// up to 2 min between tries, and at once when the network comes back or
/// the app is opened again. Nothing runs while the app is in the background.
class AutoRetry {
  AutoRetry(
    this._attempt, {
    this.first = const Duration(seconds: 5),
    this.max = const Duration(minutes: 2),
    Stream<List<ConnectivityResult>>? network,
  }) : _network = network;

  /// True when it worked (stop retrying).
  final Future<bool> Function() _attempt;
  final Duration first;
  final Duration max;
  final Stream<List<ConnectivityResult>>? _network;

  Timer? _timer;
  Duration _wait = Duration.zero;
  bool _active = false;
  bool _running = false;
  bool _wasOffline = false;
  StreamSubscription<List<ConnectivityResult>>? _net;
  AppLifecycleListener? _life;

  bool get active => _active;

  /// Starts retrying (no-op if it already is).
  void start() {
    if (_active) return;
    _active = true;
    _wait = first;
    _net = (_network ?? Connectivity().onConnectivityChanged).listen((r) {
      final offline = r.every((c) => c == ConnectivityResult.none);
      if (_wasOffline && !offline) now();
      _wasOffline = offline;
    });
    _life = AppLifecycleListener(onResume: now, onHide: () => _timer?.cancel());
    _schedule();
  }

  void _schedule() {
    _timer?.cancel();
    _timer = Timer(_wait, now);
  }

  /// One try right away (e.g. the person tapped Retry).
  Future<void> now() async {
    if (!_active || _running) return;
    _timer?.cancel();
    _running = true;
    bool ok;
    try {
      ok = await _attempt();
    } on Object {
      ok = false;
    }
    _running = false;
    if (!_active) return;
    if (ok) return stop();
    final next = _wait * 2;
    _wait = next > max ? max : next;
    _schedule();
  }

  void stop() {
    _active = false;
    _timer?.cancel();
    _net?.cancel();
    _net = null;
    _life?.dispose();
    _life = null;
  }
}
