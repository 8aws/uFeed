import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_wkwebview/webview_flutter_wkwebview.dart';

/// What the page's <audio> reports.
class WebAudioState {
  const WebAudioState({
    this.position = Duration.zero,
    this.duration,
    this.playing = false,
    this.waiting = false,
    this.ended = false,
    this.error,
  });

  final Duration position;
  final Duration? duration; // null while the file is still growing
  final bool playing;
  final bool waiting;
  final bool ended;
  final String? error;
}

const _page = '''<!doctype html><html><body>
<audio id="a" preload="auto" playsinline></audio>
<script>
const a = document.getElementById('a');
function send() {
  ufeed.postMessage(JSON.stringify({
    t: a.currentTime, d: isFinite(a.duration) ? a.duration : null,
    p: !a.paused, w: a.readyState < 3 && !a.paused, e: a.ended }));
}
['timeupdate', 'play', 'pause', 'ended', 'waiting', 'playing',
 'durationchange'].forEach(ev => a.addEventListener(ev, send));
a.addEventListener('error', () =>
  ufeed.postMessage(JSON.stringify({ err: 'media ' + (a.error && a.error.code) })));
function seekBy(s) { a.currentTime = Math.max(0, a.currentTime + s); }
function load(u, title, artist, rate) {
  // Lock screen / Control Center: the article instead of the page's host.
  if ('mediaSession' in navigator) {
    const ms = navigator.mediaSession;
    ms.metadata = new MediaMetadata({ title, artist });
    ms.setActionHandler('play', () => a.play());
    ms.setActionHandler('pause', () => a.pause());
    ms.setActionHandler('seekbackward', () => { a.currentTime = Math.max(0, a.currentTime - 15); });
    ms.setActionHandler('seekforward', () => { a.currentTime += 15; });
  }
  a.src = u;
  a.playbackRate = rate;
  a.defaultPlaybackRate = rate;
  a.play().catch(e => ufeed.postMessage(JSON.stringify({ err: String(e) })));
}
</script></body></html>''';

/// Plays a URL through WebKit's media stack (an <audio> in a hidden web
/// view). Unlike AVPlayer, WebKit plays the server voice's MP3 while it is
/// still being generated, as Safari does for the web app.
class WebAudio {
  WebAudio() {
    final params = WebViewPlatform.instance is WebKitWebViewPlatform
        ? WebKitWebViewControllerCreationParams(
            allowsInlineMediaPlayback: true,
            mediaTypesRequiringUserAction: const <PlaybackMediaTypes>{},
          )
        : const PlatformWebViewControllerCreationParams();
    controller = WebViewController.fromPlatformCreationParams(params)
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..addJavaScriptChannel('ufeed', onMessageReceived: _onMessage);
  }

  late final WebViewController controller;
  final state = ValueNotifier(const WebAudioState());

  void _onMessage(JavaScriptMessage m) {
    final j = jsonDecode(m.message) as Map<String, dynamic>;
    if (j['err'] != null) {
      state.value = WebAudioState(error: j['err'] as String);
      return;
    }
    Duration secs(num s) => Duration(milliseconds: (s * 1000).round());
    state.value = WebAudioState(
      position: secs(j['t'] as num),
      duration: j['d'] == null ? null : secs(j['d'] as num),
      playing: j['p'] as bool,
      waiting: j['w'] as bool,
      ended: j['e'] as bool,
    );
  }

  /// Load the page, then start playing `url` (the page must be in the widget
  /// tree: see [view]).
  Future<void> play(
    Uri url, {
    String title = '',
    String artist = '',
    double rate = 1,
  }) async {
    final args = [
      url.toString(),
      title,
      artist,
      rate,
    ].map(jsonEncode).join(', ');
    await controller.setNavigationDelegate(
      NavigationDelegate(
        onPageFinished: (_) => controller.runJavaScript('load($args)'),
      ),
    );
    await controller.loadHtmlString(_page);
  }

  Future<void> resume() => _js('a.play()');
  Future<void> pause() => _js('a.pause()');
  Future<void> seekBy(Duration d) => _js('seekBy(${d.inMilliseconds / 1000})');
  Future<void> setRate(double r) =>
      _js('a.playbackRate = $r; a.defaultPlaybackRate = $r;');

  /// Commands to a page that was already cleared (audio handed over to the
  /// native player) are simply ignored.
  Future<void> _js(String code) async {
    try {
      await controller.runJavaScript(code);
    } on Object {
      // no <audio> on the page any more
    }
  }

  /// Silence it and free the page (e.g. when native playback takes over).
  Future<void> stop() async {
    await controller.loadHtmlString('<html></html>');
    state.value = const WebAudioState();
  }

  /// The (invisible) web view; must stay mounted while playing.
  Widget view() => SizedBox(
    width: 1,
    height: 1,
    child: Opacity(opacity: 0.01, child: WebViewWidget(controller: controller)),
  );

  void dispose() {
    unawaited(controller.loadHtmlString('<html></html>'));
    state.dispose();
  }
}
