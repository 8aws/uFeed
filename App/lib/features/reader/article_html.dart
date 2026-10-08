import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_widget_from_html_core/flutter_widget_from_html_core.dart';
import 'package:html/dom.dart' as dom;
import 'package:just_audio/just_audio.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';

/// Only absolute http(s) URLs (resolved against the article's address);
/// anything else (javascript:, data:, …) is dropped, as in the web reader.
Uri? safeUri(String? url, [Uri? base]) {
  if (url == null || url.trim().isEmpty) return null;
  final u = Uri.tryParse(url.trim());
  if (u == null) return null;
  final abs = base != null ? base.resolveUri(u) : u;
  return abs.isScheme('http') || abs.isScheme('https') ? abs : null;
}

/// YouTube / Vimeo video behind a link: the backend marks the players it
/// found with data-embed="youtube:ID"; plain watch links count too.
({String provider, String id})? embedOf(String? href, String? tag) {
  if (tag != null) {
    final [provider, id, ...] = [...tag.split(':'), ''];
    if (provider == 'youtube' && RegExp(r'^[\w-]{11}$').hasMatch(id)) {
      return (provider: provider, id: id);
    }
    if (provider == 'vimeo' && RegExp(r'^\d{4,12}$').hasMatch(id)) {
      return (provider: provider, id: id);
    }
  }
  final u = safeUri(href);
  if (u == null) return null;
  final host = u.host.replaceFirst(RegExp(r'^(www|m)\.'), '');
  String? id;
  if (host == 'youtube.com' && u.path == '/watch') {
    id = u.queryParameters['v'];
  } else if (host == 'youtube.com' &&
      RegExp(r'^/(shorts|live)/').hasMatch(u.path)) {
    id = u.pathSegments.length > 1 ? u.pathSegments[1] : null;
  } else if (host == 'youtu.be' && u.pathSegments.isNotEmpty) {
    id = u.pathSegments.first;
  }
  if (id != null && RegExp(r'^[\w-]{11}$').hasMatch(id)) {
    return (provider: 'youtube', id: id);
  }
  final vimeo = RegExp(r'^/(\d{4,12})$').firstMatch(u.path);
  if (host == 'vimeo.com' && vimeo != null) {
    return (provider: 'vimeo', id: vimeo.group(1)!);
  }
  return null;
}

Future<void> openLink(Uri url, {bool external = false}) => launchUrl(
  url,
  mode: external ? LaunchMode.externalApplication : LaunchMode.inAppBrowserView,
);

/// The article's HTML as native widgets. Feed HTML never runs code here:
/// scripts, forms and iframes aren't rendered, links open in the browser,
/// videos become cards and podcasts get a small player.
class ArticleHtml extends StatelessWidget {
  const ArticleHtml({
    super.key,
    required this.html,
    required this.baseUrl,
    required this.textStyle,
  });

  final String html;
  final Uri? baseUrl;
  final TextStyle textStyle;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return HtmlWidget(
      html,
      baseUrl: baseUrl,
      textStyle: textStyle,
      onTapUrl: (url) {
        final u = safeUri(url, baseUrl);
        if (u != null) unawaited(openLink(u));
        return true; // handled (or refused): never navigate elsewhere
      },
      customStylesBuilder: (e) => switch (e.localName) {
        'a' => {'color': _hex(c.accent), 'text-decoration': 'none'},
        'blockquote' => {
          'border-left': '3px solid ${_hex(c.border)}',
          'padding-left': '12px',
          'margin-left': '0',
          'color': _hex(c.muted),
        },
        // Below the article's own headline.
        'h1' => {'font-size': '1.3em', 'line-height': '1.25'},
        'h2' => {'font-size': '1.2em', 'line-height': '1.25'},
        'h3' ||
        'h4' ||
        'h5' ||
        'h6' => {'font-size': '1.08em', 'line-height': '1.3'},
        'figcaption' => {'color': _hex(c.muted), 'font-size': '0.85em'},
        'pre' || 'code' => {'background-color': _hex(c.accentSoft)},
        _ => null,
      },
      customWidgetBuilder: (e) => _custom(context, e),
    );
  }

  Widget? _custom(BuildContext context, dom.Element e) {
    switch (e.localName) {
      case 'img':
        final src = safeUri(e.attributes['src'], baseUrl);
        if (src == null) return const SizedBox.shrink();
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: CachedNetworkImage(
              imageUrl: src.toString(),
              fit: BoxFit.contain,
              errorWidget: (_, _, _) => const SizedBox.shrink(),
            ),
          ),
        );
      case 'a':
        final embed = embedOf(e.attributes['href'], e.attributes['data-embed']);
        if (embed == null) return null; // a normal link
        return _EmbedCard(provider: embed.provider, id: embed.id);
      case 'audio':
        final src = safeUri(
          e.attributes['src'] ?? e.querySelector('source')?.attributes['src'],
          baseUrl,
        );
        return src == null ? const SizedBox.shrink() : _PodcastPlayer(src);
      case 'video':
        final src = safeUri(
          e.attributes['src'] ?? e.querySelector('source')?.attributes['src'],
          baseUrl,
        );
        return src == null
            ? const SizedBox.shrink()
            : _MediaCard(
                icon: Icons.movie_outlined,
                onTap: () => openLink(src),
              );
      case 'iframe' || 'script' || 'style' || 'form' || 'object' || 'embed':
        return const SizedBox.shrink();
    }
    return null;
  }

  static String _hex(Color c) =>
      '#${(c.toARGB32() & 0xFFFFFF).toRadixString(16).padLeft(6, '0')}';
}

/// A video as a card: tapping opens it in the YouTube/Vimeo app or browser,
/// so nothing from those sites loads until the reader asks.
class _EmbedCard extends StatelessWidget {
  const _EmbedCard({required this.provider, required this.id});

  final String provider;
  final String id;

  @override
  Widget build(BuildContext context) {
    final url = provider == 'youtube'
        ? Uri.https('www.youtube.com', '/watch', {'v': id})
        : Uri.https('vimeo.com', '/$id');
    return _MediaCard(
      icon: Icons.play_circle_fill,
      label: provider == 'youtube' ? 'YouTube' : 'Vimeo',
      thumbnail: provider == 'youtube'
          ? 'https://i.ytimg.com/vi/$id/hqdefault.jpg'
          : null,
      onTap: () => openLink(url, external: true),
    );
  }
}

class _MediaCard extends StatelessWidget {
  const _MediaCard({
    required this.icon,
    required this.onTap,
    this.label,
    this.thumbnail,
  });

  final IconData icon;
  final VoidCallback onTap;
  final String? label;
  final String? thumbnail;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Material(
        color: c.accentSoft,
        borderRadius: BorderRadius.circular(8),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: AspectRatio(
            aspectRatio: 16 / 9,
            child: Stack(
              fit: StackFit.expand,
              children: [
                if (thumbnail != null)
                  CachedNetworkImage(
                    imageUrl: thumbnail!,
                    fit: BoxFit.cover,
                    errorWidget: (_, _, _) => const SizedBox.shrink(),
                  ),
                Center(
                  child: Icon(
                    icon,
                    size: 56,
                    color: thumbnail != null ? Colors.white : c.accent,
                    shadows: const [Shadow(blurRadius: 8)],
                  ),
                ),
                if (label != null)
                  Positioned(
                    left: 10,
                    bottom: 8,
                    child: Text(
                      label!,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                        shadows: [Shadow(blurRadius: 6)],
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// A podcast episode in the article: play/pause and position. Loads
/// nothing until played (saves mobile data, like preload="none").
class _PodcastPlayer extends StatefulWidget {
  const _PodcastPlayer(this.url);

  final Uri url;

  @override
  State<_PodcastPlayer> createState() => _PodcastPlayerState();
}

class _PodcastPlayerState extends State<_PodcastPlayer> {
  final _player = AudioPlayer();
  bool _loaded = false;

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    if (_player.playing) return _player.pause();
    if (!_loaded) {
      await _player.setUrl(widget.url.toString());
      _loaded = true;
    }
    unawaited(_player.play());
  }

  String _clock(Duration d) {
    final h = d.inHours;
    final m = (d.inMinutes % 60).toString().padLeft(h > 0 ? 2 : 1, '0');
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return h > 0 ? '$h:$m:$s' : '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final t = AppLocalizations.of(context);
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: c.accentSoft,
        borderRadius: BorderRadius.circular(8),
      ),
      child: StreamBuilder<PlayerState>(
        stream: _player.playerStateStream,
        builder: (context, snap) {
          final playing = snap.data?.playing ?? false;
          return Row(
            children: [
              IconButton(
                tooltip: t.listen,
                icon: Icon(
                  playing ? Icons.pause_circle : Icons.play_circle,
                  size: 36,
                  color: c.accent,
                ),
                onPressed: _toggle,
              ),
              const Icon(Icons.podcasts, size: 18),
              const SizedBox(width: 8),
              StreamBuilder<Duration>(
                stream: _player.positionStream,
                builder: (context, pos) => Text(
                  _loaded
                      ? '${_clock(pos.data ?? Duration.zero)} / '
                            '${_clock(_player.duration ?? Duration.zero)}'
                      : 'Podcast',
                  style: TextStyle(
                    color: c.muted,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
