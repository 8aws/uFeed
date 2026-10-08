import 'package:audio_service/audio_service.dart';

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
      commands?.seekBy(const Duration(seconds: 15));

  @override
  Future<void> rewind() async => commands?.seekBy(const Duration(seconds: -15));

  @override
  Future<void> skipToNext() async => commands?.next();
}

/// Set up once in main(); null in tests and where the platform can't.
UFeedAudioHandler? audioHandler;

Future<void> initAudioHandler() async {
  try {
    audioHandler = await AudioService.init(
      builder: UFeedAudioHandler.new,
      config: const AudioServiceConfig(
        androidNotificationChannelId: 'es.uverse.ufeed.audio',
        androidNotificationChannelName: 'uFeed',
        androidNotificationOngoing: true,
        fastForwardInterval: Duration(seconds: 15),
        rewindInterval: Duration(seconds: 15),
      ),
    );
  } on Object {
    audioHandler = null; // the app still plays, without lock-screen controls
  }
}
