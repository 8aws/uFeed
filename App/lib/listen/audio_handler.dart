import 'package:audio_service/audio_service.dart';
import 'package:flutter/foundation.dart';

/// What the lock screen, Control Center, headphones and CarPlay can ask for.
abstract class ListenCommands {
  Future<void> resume();
  Future<void> pause();
  Future<void> stop();
  Future<void> seekBy(Duration delta);
  Future<void> seekTo(Duration position);
  Future<void> next();
}

/// The bridge to the system's media controls (audio_service). The listen
/// controller publishes what's playing here and receives the buttons.
class UFeedAudioHandler extends BaseAudioHandler with SeekHandler {
  ListenCommands? commands;

  @override
  Future<void> play() async => commands?.resume();

  @override
  Future<void> pause() async => commands?.pause();

  @override
  Future<void> stop() async => commands?.stop();

  @override
  Future<void> seek(Duration position) async => commands?.seekTo(position);

  @override
  Future<void> fastForward() async =>
      commands?.seekBy(const Duration(seconds: 10));

  @override
  Future<void> rewind() async => commands?.seekBy(const Duration(seconds: -10));

  @override
  Future<void> skipToNext() async => commands?.next();
}

/// Set up once in main(); null in tests, where the platform can't, and for
/// the first moments after launch.
UFeedAudioHandler? audioHandler;

/// Who answers the lock-screen buttons; handed to the handler once it exists.
ListenCommands? _pendingCommands;

void setAudioCommands(ListenCommands commands) {
  _pendingCommands = commands;
  audioHandler?.commands = commands;
}

Future<void> initAudioHandler() async {
  try {
    audioHandler = await AudioService.init(
      builder: UFeedAudioHandler.new,
      config: const AudioServiceConfig(
        androidNotificationChannelId: 'es.uverse.ufeed.audio',
        androidNotificationChannelName: 'uFeed',
        androidNotificationOngoing: true,
        fastForwardInterval: Duration(seconds: 10),
        rewindInterval: Duration(seconds: 10),
      ),
    );
    audioHandler?.commands = _pendingCommands;
  } on Object catch (e) {
    audioHandler = null; // the app still plays, without lock-screen controls
    debugPrint('audio_service unavailable: $e');
  }
}
