import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'core/prefs.dart';
import 'listen/audio_handler.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  // Thumbnails are decoded at their display size (see NetImage); this caps
  // what stays decoded in memory on top of that.
  PaintingBinding.instance.imageCache.maximumSizeBytes = 64 << 20;
  runApp(
    ProviderScope(
      overrides: [prefsProvider.overrideWithValue(prefs)],
      child: const UFeedApp(),
    ),
  );
  // Lock screen and Control Center: set up after the first frame, so a slow
  // audio session never holds the app on the launch screen.
  unawaited(initAudioHandler());
}
