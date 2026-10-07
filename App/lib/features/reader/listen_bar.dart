import 'dart:async';

import 'package:audio_session/audio_session.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';

import '../../api/api_client.dart';
import '../../api/models.dart';
import '../../auth/session.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';

/// How often to ask whether the server voice has finished, and for how long.
const _pollEvery = Duration(seconds: 2);
const _giveUpAfter = Duration(minutes: 3);

/// Server voice for one article: play, pause and position. The full listen
/// bar (lock screen controls, speed, Post radio) grows from here in stage 4.
///
/// AVPlayer can't play the MP3 while the server is still writing it (no
/// length yet: it buffers but never starts), unlike the web's <audio>. So
/// the app waits for the finished file, which is instant when it's cached and
/// takes ~1/25 of the reading time when it isn't.
class ListenBar extends ConsumerStatefulWidget {
  const ListenBar({super.key, required this.article});

  final Article article;

  @override
  ConsumerState<ListenBar> createState() => _ListenBarState();
}

class _ListenBarState extends ConsumerState<ListenBar> {
  final _player = AudioPlayer();
  bool _preparing = false;
  bool _started = false;
  int _waited = 0; // seconds waiting for the server voice
  String? _error;

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  /// The finished audio's URL, asking again until the server has it.
  Future<Uri?> _finishedAudio() async {
    final api = ref.read(apiProvider);
    final lang = widget.article.lang ?? deviceLocale();
    final clock = Stopwatch()..start();
    while (mounted && clock.elapsed < _giveUpAfter) {
      final audio = await api.articleAudio(widget.article.id, lang: lang);
      if (audio.cached) return audio.url;
      await Future<void>.delayed(_pollEvery);
      if (mounted) setState(() => _waited = clock.elapsed.inSeconds);
    }
    return null;
  }

  Future<void> _start() async {
    final t = AppLocalizations.of(context);
    setState(() {
      _preparing = true;
      _waited = 0;
      _error = null;
    });
    try {
      final session = await AudioSession.instance;
      await session.configure(const AudioSessionConfiguration.speech());
      final url = await _finishedAudio();
      if (!mounted) return;
      if (url == null) {
        setState(() => _error = t.listenUnavailable);
        return;
      }
      await _player.setUrl(url.toString());
      setState(() => _started = true);
      unawaited(_player.play());
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(
        () => _error = switch (e.code) {
          'plan_limit_tts' => t.listenPlan,
          'rate_limited' => t.listenRateLimited,
          'tts_lang' => t.listenLangUnsupported,
          _ when e.isNetwork => t.offline,
          _ => t.listenUnavailable,
        },
      );
    } on PlayerException {
      if (mounted) setState(() => _error = t.listenUnavailable);
    } finally {
      if (mounted) setState(() => _preparing = false);
    }
  }

  String _clock(Duration d) {
    final m = d.inMinutes;
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    if (!_started) {
      return Row(
        children: [
          OutlinedButton.icon(
            onPressed: _preparing ? null : _start,
            icon: _preparing
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.headphones),
            label: Text(
              !_preparing
                  ? t.listen
                  : _waited < 2
                  ? t.listenPreparing
                  : t.listenPreparingFor(_waited),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(width: 12),
            Expanded(
              child: Text(_error!, style: TextStyle(color: c.danger)),
            ),
          ],
        ],
      );
    }
    return StreamBuilder<PlayerState>(
      stream: _player.playerStateStream,
      builder: (context, snap) {
        final state = snap.data;
        final playing = state?.playing ?? false;
        final buffering =
            state?.processingState == ProcessingState.loading ||
            state?.processingState == ProcessingState.buffering;
        return Row(
          children: [
            IconButton.filled(
              onPressed: playing ? _player.pause : _player.play,
              icon: buffering
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : Icon(playing ? Icons.pause : Icons.play_arrow),
            ),
            const SizedBox(width: 12),
            StreamBuilder<Duration>(
              stream: _player.positionStream,
              builder: (context, pos) => Text(
                '${_clock(pos.data ?? Duration.zero)} / '
                '${_clock(_player.duration ?? Duration.zero)}',
                style: TextStyle(
                  color: c.muted,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
