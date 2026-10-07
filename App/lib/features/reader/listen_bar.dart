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
import 'web_audio.dart';

/// Server voice for one article: play, pause and position. The full listen
/// bar (lock screen controls, speed, Post radio) grows from here in stage 4.
///
/// Finished audio plays natively (just_audio / AVPlayer). Audio the server is
/// still generating goes through WebKit instead ([WebAudio]): AVPlayer can't
/// play an MP3 with no length yet (it buffers but never starts), while
/// WebKit plays it live, as Safari does for the web app.
class ListenBar extends ConsumerStatefulWidget {
  const ListenBar({super.key, required this.article, this.sourceTitle = ''});

  final Article article;
  final String sourceTitle;

  @override
  ConsumerState<ListenBar> createState() => _ListenBarState();
}

class _ListenBarState extends ConsumerState<ListenBar> {
  final _player = AudioPlayer();
  WebAudio? _web; // live audio through WebKit
  bool _preparing = false;
  bool _started = false;
  String? _error;

  @override
  void dispose() {
    _web?.dispose();
    _player.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    final t = AppLocalizations.of(context);
    setState(() {
      _preparing = true;
      _error = null;
    });
    try {
      final session = await AudioSession.instance;
      await session.configure(const AudioSessionConfiguration.speech());
      final audio = await ref
          .read(apiProvider)
          .articleAudio(
            widget.article.id,
            lang: widget.article.lang ?? deviceLocale(),
          );
      if (!mounted) return;
      if (!audio.cached) {
        final web = WebAudio();
        setState(() {
          _web = web;
          _started = true;
        });
        await web.play(
          audio.url,
          title: widget.article.title ?? '',
          artist: widget.sourceTitle,
        );
        return;
      }
      await _player.setUrl(audio.url.toString());
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
            label: Text(_preparing ? t.listenPreparing : t.listen),
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
    final web = _web;
    if (web != null) {
      return ValueListenableBuilder<WebAudioState>(
        valueListenable: web.state,
        builder: (context, s, _) => Row(
          children: [
            IconButton.filled(
              onPressed: s.playing ? web.pause : web.resume,
              icon: Icon(s.playing ? Icons.pause : Icons.play_arrow),
            ),
            const SizedBox(width: 12),
            Text(
              '${_clock(s.position)} / '
              '${s.duration == null ? '…' : _clock(s.duration!)}',
              style: TextStyle(
                color: c.muted,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
            if (s.error != null) ...[
              const SizedBox(width: 12),
              Flexible(
                child: Text(
                  t.listenUnavailable,
                  style: TextStyle(color: c.danger),
                ),
              ),
            ],
            const Spacer(),
            web.view(),
          ],
        ),
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
