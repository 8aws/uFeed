import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/core/auto_retry.dart';

void main() {
  testWidgets('retries with growing waits until it works', (tester) async {
    final net = StreamController<List<ConnectivityResult>>();
    var tries = 0;
    final retry = AutoRetry(() async => ++tries >= 3, network: net.stream)
      ..start();

    await tester.pump(const Duration(seconds: 4));
    expect(tries, 0);
    await tester.pump(const Duration(seconds: 1)); // 5 s
    expect(tries, 1);
    await tester.pump(const Duration(seconds: 9));
    expect(tries, 1);
    await tester.pump(const Duration(seconds: 1)); // +10 s
    expect(tries, 2);

    // The network comes back: one try at once, which works.
    net
      ..add([ConnectivityResult.none])
      ..add([ConnectivityResult.wifi]);
    await tester.pump();
    expect(tries, 3);
    expect(retry.active, isFalse);

    await tester.pump(const Duration(minutes: 5));
    expect(tries, 3);
    net.close().ignore();
  });

  testWidgets('a failing try is not an error', (tester) async {
    var tries = 0;
    final retry = AutoRetry(
      () async {
        tries++;
        throw Exception('down');
      },
      network: const Stream.empty(),
      max: const Duration(seconds: 8),
    )..start();
    await tester.pump(const Duration(seconds: 5));
    await tester.pump(const Duration(seconds: 8));
    await tester.pump(const Duration(seconds: 8)); // capped at 8 s
    expect(tries, 3);
    retry.stop();
  });
}
