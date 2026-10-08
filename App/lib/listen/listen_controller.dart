import 'dart:async';
import 'dart:io' show Platform;
import 'dart:math' as math;

import 'package:audio_service/audio_service.dart';
import 'package:audio_session/audio_session.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:just_audio/just_audio.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../auth/plan.dart';
import '../auth/session.dart';
import '../core/prefs.dart';
import '../features/home/home_state.dart';
import '../features/reader/article_html.dart';
import '../features/reader/article_page.dart';
import '../features/reader/web_audio.dart';
import '../offline/providers.dart';
import 'audio_handler.dart';
import 'readable.dart';

/// How the article is being read.
enum Engine {
  /// The server's finished MP3, played natively.
  server,

  /// The server's MP3 while it's still being generated, through WebKit
  /// (AVPlayer can't start it); handed over to [server] once it's complete.
  live,

  /// The device's own voice (free, offline, any language it has).
  device,
}

enum ListenStatus { idle, preparing, playing, paused, ended }

/// Post radio: the posts of a list read one after another.
class RadioSession {
  const RadioSession({
    required this.queue,
    required this.pos,
    required this.startedAt,
    this.maxPosts,
    this.maxMinutes,
  });

  final List<Article> queue;
  final int pos;
  final DateTime startedAt;
  final int? maxPosts;
  final int? maxMinutes;

  RadioSession at(int p) => RadioSession(
    queue: queue,
    pos: p,
    startedAt: startedAt,
    maxPosts: maxPosts,
    maxMinutes: maxMinutes,
  );

  int get total =>
      maxPosts == null ? queue.length : math.min(maxPosts!, queue.length);
}

class ListenState {
  const ListenState({
    this.article,
    this.source = '',
    this.engine,
    this.status = ListenStatus.idle,
    this.position = Duration.zero,
    this.duration,
    this.part = 0,
    this.parts = 0,
    this.rate = 1,
    this.error,
    this.radio,
    this.radioDone = false,
  });

  final Article? article;
  final String source;
  final Engine? engine;
  final ListenStatus status;
  final Duration position;
  final Duration? duration; // null while unknown (live audio)
  final int part; // device voice: sentence being read
  final int parts;
  final double rate;

  /// Server error code (plan_limit_tts, rate_limited, …) or 'network'.
  final String? error;
  final RadioSession? radio;
  final bool radioDone; // the radio just ended (for a short message)

  bool get active =>
      article != null &&
      (status == ListenStatus.preparing ||
          status == ListenStatus.playing ||
          status == ListenStatus.paused);

  bool get playing => status == ListenStatus.playing;

  bool isFor(Article a) => article?.id == a.id;

  ListenState copyWith({
    Article? article,
    String? source,
    Engine? engine,
    ListenStatus? status,
    Duration? position,
    Duration? duration,
    int? part,
    int? parts,
    double? rate,
    String? error,
    RadioSession? radio,
    bool clearRadio = false,
    bool radioDone = false,
  }) => ListenState(
    article: article ?? this.article,
    source: source ?? this.source,
    engine: engine ?? this.engine,
    status: status ?? this.status,
    position: position ?? this.position,
    duration: duration ?? this.duration,
    part: part ?? this.part,
    parts: parts ?? this.parts,
    rate: rate ?? this.rate,
    error: error,
    radio: clearRadio ? null : (radio ?? this.radio),
    radioDone: radioDone,
  );
}

/// The one live-audio web view, kept mounted by the app (see app.dart).
final liveAudioProvider = Provider<WebAudio>((ref) {
  final web = WebAudio();
  ref.onDispose(web.dispose);
  return web;
});

final listenProvider = NotifierProvider<ListenController, ListenState>(
  ListenController.new,
);

const _serverLangs = {'es', 'en'};
const _heardEnough = 0.7; // Post radio: a post this far heard counts as read

/// Reads articles aloud, app-wide (the audio keeps going while browsing):
/// the server voice (plan feature) or the device's, and Post radio.
class ListenController extends Notifier<ListenState> implements ListenCommands {
  final _player = AudioPlayer();
  final _jingle = AudioPlayer();
  final _tts = FlutterTts();
  final _subs = <StreamSubscription<Object?>>[];
  bool _ready = false;
  int _run = 0; // invalidates work for an article that was replaced
  Duration _maxHeard = Duration.zero;
  int _maxPart = 0;
  List<String> _chunks = const [];
  Timer? _livePoll;
  Timer? _prefetch;

  ApiClient get _api => ref.read(apiProvider);
  WebAudio get _web => ref.read(liveAudioProvider);

  @override
  ListenState build() {
    ref.onDispose(_dispose);
    audioHandler?.commands = this;
    return ListenState(rate: ref.read(speechPrefsProvider).rate);
  }

  void _dispose() {
    for (final s in _subs) {
      s.cancel();
    }
    _livePoll?.cancel();
    _prefetch?.cancel();
    _player.dispose();
    _jingle.dispose();
    _tts.stop();
  }

  Future<void> _setUp() async {
    if (_ready) return;
    _ready = true;
    final session = await AudioSession.instance;
    await session.configure(const AudioSessionConfiguration.speech());
    // Headphones unplugged or a call: the device voice pauses too (the
    // native player already does this by itself).
    _subs.add(
      session.becomingNoisyEventStream.listen((_) {
        if (state.engine == Engine.device) pause();
      }),
    );
    _subs.add(
      session.interruptionEventStream.listen((e) {
        if (e.begin && state.engine != Engine.server) pause();
      }),
    );
    _subs.add(_player.positionStream.listen(_onServerPosition));
    _subs.add(_player.playerStateStream.listen(_onServerState));
    _web.state.addListener(_onLiveState);
    if (Platform.isIOS) {
      await _tts.setSharedInstance(true);
      await _tts.setIosAudioCategory(
        IosTextToSpeechAudioCategory.playback,
        [IosTextToSpeechAudioCategoryOptions.duckOthers],
        IosTextToSpeechAudioMode.spokenAudio,
      );
    }
    await _tts.awaitSpeakCompletion(true);
  }

  // ---------------------------------------------------------------- start

  /// Read [a] aloud from the start (replacing whatever was playing).
  Future<void> start(
    Article a, {
    String source = '',
    bool keepRadio = false,
  }) async {
    await _setUp();
    final run = ++_run;
    await _silence();
    _maxHeard = Duration.zero;
    _maxPart = 0;
    final prefs = ref.read(speechPrefsProvider);
    state = ListenState(
      article: a,
      source: source,
      status: ListenStatus.preparing,
      rate: prefs.rate,
      radio: keepRadio ? state.radio : null,
    );
    _publishItem();
    final plan = await ref.read(planProvider.future);
    if (run != _run) return;
    final translated = prefs.myLanguage && canTranslate(a);
    final lang = translated
        ? deviceLocale()
        : baseLang(a.lang ?? deviceLocale());
    final useServer =
        prefs.server && plan.ttsServer && _serverLangs.contains(lang);
    if (useServer && await _startServer(a, run, lang, translated, prefs)) {
      return;
    }
    if (run != _run) return;
    await _startDevice(a, run, lang, translated, prefs);
  }

  /// True if the server voice took it; false to fall back to the device's.
  Future<bool> _startServer(
    Article a,
    int run,
    String lang,
    bool translated,
    SpeechPrefs prefs,
  ) async {
    try {
      final audio = await _api.articleAudio(
        a.id,
        lang: lang,
        voice: prefs.gender,
        translated: translated,
      );
      if (run != _run) return true;
      if (audio.cached) {
        await _playNative(audio.url, Duration.zero, prefs.rate);
      } else {
        state = state.copyWith(engine: Engine.live);
        await _web.play(
          audio.url,
          title: a.title ?? '',
          artist: state.source,
          rate: prefs.rate,
        );
        _pollForFinished(a, run, lang, translated, prefs);
      }
      _schedulePrefetch();
      return true;
    } on ApiException catch (e) {
      if (run != _run) return true;
      // No server voice for this language or right now: the device's reads it.
      if (e.code == 'tts_lang' || e.code == 'ai_unavailable' || e.isNetwork) {
        return false;
      }
      state = state.copyWith(status: ListenStatus.idle, error: e.code);
      return true;
    }
  }

  Future<void> _playNative(Uri url, Duration at, double rate) async {
    state = state.copyWith(engine: Engine.server);
    await _player.setUrl(url.toString());
    if (at > Duration.zero) await _player.seek(at);
    await _player.setSpeed(rate);
    unawaited(_player.play());
  }

  /// Live audio: once the server has the whole file, continue natively from
  /// the same point (full lock-screen controls, seeking, duration).
  void _pollForFinished(
    Article a,
    int run,
    String lang,
    bool translated,
    SpeechPrefs prefs,
  ) {
    _livePoll?.cancel();
    _livePoll = Timer.periodic(const Duration(seconds: 3), (t) async {
      if (run != _run || state.engine != Engine.live) return t.cancel();
      try {
        final audio = await _api.articleAudio(
          a.id,
          lang: lang,
          voice: prefs.gender,
          translated: translated,
        );
        if (!audio.cached || run != _run || state.engine != Engine.live) {
          return;
        }
        t.cancel();
        final live = _web.state.value;
        final wasPlaying = live.playing;
        await _web.stop();
        await _playNative(audio.url, live.position, state.rate);
        if (!wasPlaying) await _player.pause();
      } on ApiException {
        // try again on the next tick
      }
    });
  }

  Future<void> _startDevice(
    Article a,
    int run,
    String lang,
    bool translated,
    SpeechPrefs prefs,
  ) async {
    String text;
    if (translated) {
      try {
        final tr = await _api.translation(a.id, lang, generate: true);
        text = translationText(tr.title, tr.paragraphs ?? const []);
      } on ApiException {
        text = await _articleText(a);
        lang = baseLang(a.lang ?? lang);
      }
    } else {
      text = await _articleText(a);
    }
    if (run != _run) return;
    _chunks = chunks(text);
    await _tts.setLanguage(
      lang == 'es'
          ? 'es-ES'
          : lang == 'en'
          ? 'en-US'
          : lang,
    );
    await _tts.setSpeechRate(_ttsRate(prefs.rate));
    state = state.copyWith(
      engine: Engine.device,
      parts: _chunks.length,
      part: 0,
    );
    unawaited(_speakFrom(0, run));
  }

  /// The article's text, full when the feed only gave an excerpt.
  Future<String> _articleText(Article a) async {
    var html = ref.read(offlineSavedProvider)[a.id]?.fullHtml;
    if (html == null && isExcerpt(a) && safeUri(a.url) != null) {
      try {
        html = await _api.fullText(a.id);
      } on ApiException {
        // the excerpt will do
      }
    }
    return readableText(a.title ?? '', html ?? a.contentHtml ?? a.summary);
  }

  /// AVSpeechUtterance's normal rate is 0.5 on iOS; 1.0 elsewhere.
  double _ttsRate(double r) =>
      Platform.isIOS ? (0.5 * r).clamp(0.1, 1.0) : r.clamp(0.25, 2.0);

  Future<void> _speakFrom(int from, int run) async {
    state = state.copyWith(status: ListenStatus.playing);
    _publishState();
    for (var i = from; i < _chunks.length; i++) {
      if (run != _run) return;
      _maxPart = math.max(_maxPart, i);
      state = state.copyWith(part: i, status: ListenStatus.playing);
      _publishState();
      await _tts.speak(_chunks[i]);
    }
    if (run == _run) await _finished();
  }

  // ------------------------------------------------------------- progress

  void _onServerPosition(Duration p) {
    if (state.engine != Engine.server) return;
    if (p > _maxHeard) _maxHeard = p;
    state = state.copyWith(position: p, duration: _player.duration);
    _publishState();
  }

  void _onServerState(PlayerState s) {
    if (state.engine != Engine.server) return;
    if (s.processingState == ProcessingState.completed) {
      _finished();
      return;
    }
    final status = s.playing
        ? ListenStatus.playing
        : (s.processingState == ProcessingState.loading
              ? ListenStatus.preparing
              : ListenStatus.paused);
    state = state.copyWith(status: status, duration: _player.duration);
    _publishState();
  }

  void _onLiveState() {
    if (state.engine != Engine.live) return;
    final s = _web.state.value;
    if (s.position > _maxHeard) _maxHeard = s.position;
    if (s.ended) {
      _finished();
      return;
    }
    state = state.copyWith(
      status: s.playing ? ListenStatus.playing : ListenStatus.paused,
      position: s.position,
      duration: s.duration,
      error: s.error == null ? null : 'player',
    );
    _publishState();
  }

  /// How much of the current article was heard (0..1).
  double get heard {
    switch (state.engine) {
      case Engine.device:
        return _chunks.isEmpty ? 0 : (_maxPart + 1) / _chunks.length;
      case Engine.server || Engine.live:
        final d = state.duration;
        if (d == null || d == Duration.zero) return 0;
        return (_maxHeard.inMilliseconds / d.inMilliseconds).clamp(0.0, 1.0);
      case null:
        return 0;
    }
  }

  Future<void> _finished() async {
    if (state.status == ListenStatus.ended) return;
    if (state.radio != null) {
      await _radioAdvance(1);
      return;
    }
    state = state.copyWith(status: ListenStatus.ended, part: 0);
    _publishState();
  }

  // ------------------------------------------------------------- commands

  @override
  Future<void> resume() async {
    switch (state.engine) {
      case Engine.server:
        await _player.play();
      case Engine.live:
        await _web.resume();
      case Engine.device:
        final from = state.status == ListenStatus.ended ? 0 : state.part;
        unawaited(_speakFrom(from, ++_run));
      case null:
        break;
    }
  }

  @override
  Future<void> pause() async {
    switch (state.engine) {
      case Engine.server:
        await _player.pause();
      case Engine.live:
        await _web.pause();
      case Engine.device:
        _run++;
        await _tts.stop();
        state = state.copyWith(status: ListenStatus.paused);
        _publishState();
      case null:
        break;
    }
  }

  Future<void> toggle() => state.playing ? pause() : resume();

  /// ±15 s on recordings; on the device voice, one sentence per 15 s.
  @override
  Future<void> seekBy(Duration delta) async {
    switch (state.engine) {
      case Engine.server:
        final d = _player.duration ?? Duration.zero;
        final to = _player.position + delta;
        await _player.seek(
          to < Duration.zero ? Duration.zero : (to > d ? d : to),
        );
      case Engine.live:
        await _web.seekBy(delta);
      case Engine.device:
        final step = delta.isNegative ? -1 : 1;
        final to = (state.part + step)
            .clamp(0, math.max(0, _chunks.length - 1))
            .toInt();
        state = state.copyWith(part: to);
        if (state.playing) {
          _run++;
          await _tts.stop();
          unawaited(_speakFrom(to, _run));
        }
      case null:
        break;
    }
  }

  @override
  Future<void> seekTo(Duration position) async {
    if (state.engine == Engine.server) await _player.seek(position);
  }

  Future<void> setRate(double rate) async {
    final prefs = ref.read(speechPrefsProvider);
    ref.read(speechPrefsProvider.notifier).update(prefs.copyWith(rate: rate));
    state = state.copyWith(rate: rate);
    switch (state.engine) {
      case Engine.server:
        await _player.setSpeed(rate);
      case Engine.live:
        await _web.setRate(rate);
      case Engine.device:
        await _tts.setSpeechRate(_ttsRate(rate));
        if (state.playing) {
          _run++;
          await _tts.stop();
          unawaited(_speakFrom(state.part, _run));
        }
      case null:
        break;
    }
    _publishState();
  }

  @override
  Future<void> stop() async {
    final r = state.radio;
    if (r != null) _markIfHeard(r.queue[r.pos]);
    _run++;
    await _silence();
    state = ListenState(rate: state.rate);
    await audioHandler?.stop.call();
    audioHandler?.playbackState.add(PlaybackState());
  }

  /// Post radio: skip to the next post. Otherwise nothing.
  @override
  Future<void> next() async {
    if (state.radio != null) await _radioAdvance(heard);
  }

  Future<void> _silence() async {
    _livePoll?.cancel();
    _prefetch?.cancel();
    await _player.stop();
    await _tts.stop();
    if (state.engine == Engine.live) await _web.stop();
  }

  // ------------------------------------------------------------ Post radio

  /// Read the list from [from] on, one post after another (plan feature).
  Future<void> startRadio(
    List<Article> list,
    int from, {
    required String Function(Article) sourceOf,
  }) async {
    final plan = await ref.read(planProvider.future);
    if (!plan.postRadio || from >= list.length) return;
    final prefs = ref.read(speechPrefsProvider);
    int? cap(int pref, int? max) =>
        pref == 0 ? max : (max == null ? pref : math.min(pref, max));
    _sourceOf = sourceOf;
    final radio = RadioSession(
      queue: list.sublist(from),
      pos: 0,
      startedAt: DateTime.now(),
      maxPosts: cap(prefs.radioPosts, plan.radioMaxPosts),
      maxMinutes: cap(prefs.radioMinutes, plan.radioMaxMinutes),
    );
    await _setUp();
    state = state.copyWith(radio: radio);
    await _playJingle();
    final first = radio.queue.first;
    await start(first, source: sourceOf(first), keepRadio: true);
  }

  String Function(Article) _sourceOf = _noSource;
  static String _noSource(Article _) => '';

  Future<void> _radioAdvance(double heardNow) async {
    final r = state.radio;
    if (r == null) return;
    if (heardNow >= _heardEnough) _markIfHeard(r.queue[r.pos], force: true);
    final nextPos = r.pos + 1;
    final overTime =
        r.maxMinutes != null &&
        DateTime.now().difference(r.startedAt).inMinutes >= r.maxMinutes!;
    final done = nextPos >= r.queue.length || nextPos >= r.total || overTime;
    _run++;
    await _silence();
    await _playJingle();
    if (done) {
      state = ListenState(rate: state.rate, radioDone: true);
      audioHandler?.playbackState.add(PlaybackState());
      return;
    }
    state = state.copyWith(radio: r.at(nextPos));
    final next = r.queue[nextPos];
    await start(next, source: _sourceOf(next), keepRadio: true);
  }

  void _markIfHeard(Article a, {bool force = false}) {
    if (a.isRead || (!force && heard < _heardEnough)) return;
    ref.read(articleListProvider.notifier).setRead(a, true);
  }

  /// While a radio post plays, ask for the next one's server audio, so it
  /// starts generating and the chain doesn't pause between posts.
  void _schedulePrefetch() {
    _prefetch?.cancel();
    final r = state.radio;
    if (r == null || r.pos + 1 >= r.queue.length) return;
    final next = r.queue[r.pos + 1];
    final prefs = ref.read(speechPrefsProvider);
    _prefetch = Timer(const Duration(seconds: 12), () {
      _api
          .articleAudio(
            next.id,
            lang: baseLang(next.lang ?? deviceLocale()),
            voice: prefs.gender,
          )
          .ignore();
    });
  }

  Future<void> _playJingle() async {
    try {
      await _jingle.setAsset('assets/audio/jingle.wav');
      await _jingle.play().timeout(const Duration(seconds: 3));
    } on Object {
      // never let the chime stop the radio
    }
  }

  // ---------------------------------------------------------- lock screen

  void _publishItem() {
    final a = state.article;
    final h = audioHandler;
    if (a == null || h == null) return;
    h.mediaItem.add(
      MediaItem(
        id: a.id,
        title: a.title ?? '',
        artist: state.source,
        album: 'uFeed',
        artUri: safeUri(a.imageUrl),
        duration: state.duration,
      ),
    );
  }

  Duration? _publishedDuration;

  void _publishState() {
    final h = audioHandler;
    if (h == null) return;
    if (state.duration != _publishedDuration) {
      _publishedDuration = state.duration;
      _publishItem();
    }
    final playing = state.playing;
    h.playbackState.add(
      PlaybackState(
        controls: [
          MediaControl.rewind,
          playing ? MediaControl.pause : MediaControl.play,
          MediaControl.fastForward,
          if (state.radio != null) MediaControl.skipToNext,
        ],
        systemActions: {
          if (state.engine == Engine.server) MediaAction.seek,
          MediaAction.rewind,
          MediaAction.fastForward,
        },
        processingState: switch (state.status) {
          ListenStatus.preparing => AudioProcessingState.loading,
          ListenStatus.ended => AudioProcessingState.completed,
          ListenStatus.idle => AudioProcessingState.idle,
          _ => AudioProcessingState.ready,
        },
        playing: playing,
        updatePosition: state.position,
        speed: state.rate,
      ),
    );
  }
}
