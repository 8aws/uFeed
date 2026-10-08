import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/api_client.dart';
import '../../api/models.dart';
import '../../auth/session.dart';
import '../../core/prefs.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';
import '../home/article_tile.dart';
import '../home/home_state.dart';
import 'article_html.dart';

String baseLang(String? lang) =>
    (lang ?? '').split(RegExp('[-_]')).first.toLowerCase();

/// EN<->ES machine translation into the reader's language (as on the web).
bool canTranslate(Article a) {
  final src = baseLang(a.lang);
  final mine = deviceLocale();
  return const {'es', 'en'}.contains(src) && src != mine;
}

/// The feed only gave an excerpt (or the full text was fetched before).
bool isExcerpt(Article a) => (a.wordCount ?? 0) < 200 || a.fullStatus == 'ok';

/// What the reader's toolbar can switch for the article on screen.
class ArticleViewState {
  ArticleViewState();

  final full = ValueNotifier<bool>(false);
  final translated = ValueNotifier<bool>(false);
}

/// One article in the reader: headline, AI summary bar, content (feed,
/// full article or translation) and similar articles.
class ArticlePage extends ConsumerStatefulWidget {
  const ArticlePage({
    super.key,
    required this.article,
    required this.view,
    required this.onOpenArticle,
  });

  final Article article;
  final ArticleViewState view;
  final void Function(Article) onOpenArticle;

  @override
  ConsumerState<ArticlePage> createState() => _ArticlePageState();
}

class _ArticlePageState extends ConsumerState<ArticlePage> {
  final _scroll = ScrollController();
  final _opened = DateTime.now();
  late final ApiClient _api = ref.read(apiProvider);

  String? _fullHtml;
  bool _fullBusy = false;
  String? _fullMsg;

  Translation? _translation;
  bool _trBusy = false;
  String? _trMsg;

  AiSummary? _summary;
  bool _summaryOpen = false;
  bool _summaryBusy = false;
  int _summarySecs = 0;
  String? _summaryMsg;

  List<Article> _similar = const [];

  Article get a => widget.article;
  String get _lang => deviceLocale();

  @override
  void initState() {
    super.initState();
    widget.view.full.addListener(_onFullToggle);
    widget.view.translated.addListener(_onTranslateToggle);
    if (ref.read(displayPrefsProvider).autoFull && isExcerpt(a)) {
      // After the first frame: it shows a note in the page.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_loadFull());
      });
    }
    // An existing summary (made by anyone before) shows up folded.
    _api
        .aiSummary(a.id, _lang)
        .then((s) {
          if (mounted && s.summary != null) setState(() => _summary = s);
        })
        .catchError((_) {});
    _api
        .similar(a.id)
        .then((s) {
          if (mounted) setState(() => _similar = s);
        })
        .catchError((_) {});
    _api.engage(a.id, 'open').ignore();
  }

  @override
  void dispose() {
    widget.view.full.removeListener(_onFullToggle);
    widget.view.translated.removeListener(_onTranslateToggle);
    _sendReadEvent();
    _scroll.dispose();
    super.dispose();
  }

  /// How long it was open and how far it was read (feeds Trending).
  void _sendReadEvent() {
    final dwell = DateTime.now().difference(_opened);
    if (dwell.inMilliseconds < 1000) return;
    var completion = 1.0;
    if (_scroll.hasClients && _scroll.position.maxScrollExtent > 0) {
      final p = _scroll.position;
      completion =
          ((p.pixels + p.viewportDimension) /
                  (p.maxScrollExtent + p.viewportDimension))
              .clamp(0.0, 1.0);
    }
    _api.readEvent(a.id, dwell, completion).ignore();
  }

  void _onFullToggle() {
    if (widget.view.full.value) {
      if (_fullHtml == null) unawaited(_loadFull(manual: true));
    }
    setState(() {});
  }

  Future<void> _loadFull({bool manual = false}) async {
    if (_fullHtml != null || a.url == null) return;
    setState(() {
      _fullBusy = true;
      _fullMsg = null;
    });
    final t = AppLocalizations.of(context);
    try {
      final html = await _api.fullText(a.id);
      if (!mounted) return;
      if (html != null) {
        _fullHtml = html;
        _translation = null; // it was translated from the excerpt
        widget.view.full.value = true;
      } else if (manual) {
        _fullMsg = t.fullUnavailable;
        widget.view.full.value = false;
      }
    } on ApiException {
      if (mounted && manual) {
        _fullMsg = t.fullUnavailable;
        widget.view.full.value = false;
      }
    } finally {
      if (mounted) setState(() => _fullBusy = false);
    }
  }

  Future<void> _onTranslateToggle() async {
    if (!widget.view.translated.value || _translation != null) {
      setState(() {});
      return;
    }
    final t = AppLocalizations.of(context);
    setState(() {
      _trBusy = true;
      _trMsg = null;
    });
    try {
      final tr = await _api.translation(a.id, _lang, generate: true);
      if (!mounted) return;
      if (tr.paragraphs == null) throw const ApiException(0, 'empty', '');
      setState(() => _translation = tr);
    } on ApiException {
      if (!mounted) return;
      _trMsg = t.translateUnavailable;
      widget.view.translated.value = false;
    } finally {
      if (mounted) setState(() => _trBusy = false);
    }
  }

  /// The bar folds/unfolds a summary we have; otherwise asks for one and
  /// follows it through the AI queue.
  Future<void> _summaryBar() async {
    if (_summary?.summary != null || _summaryBusy) {
      setState(() => _summaryOpen = !_summaryOpen || _summaryBusy);
      return;
    }
    final t = AppLocalizations.of(context);
    setState(() {
      _summaryOpen = true;
      _summaryBusy = true;
      _summarySecs = 0;
      _summaryMsg = null;
    });
    final clock = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _summarySecs++);
    });
    try {
      var s = await _api.aiSummary(a.id, _lang, generate: true);
      final until = DateTime.now().add(const Duration(minutes: 10));
      while (s.pending && DateTime.now().isBefore(until)) {
        if (!mounted) return;
        setState(() => _summary = s);
        await Future<void>.delayed(const Duration(seconds: 2));
        s = await _api.aiSummary(a.id, _lang);
      }
      if (!mounted) return;
      setState(() {
        _summary = s;
        if (s.summary == null) _summaryMsg = t.aiFailed;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(
        () => _summaryMsg = switch (e.code) {
          'rate_limited' => t.aiRate,
          'plan_limit_ai' => t.planLimitAi,
          'plan_limit_ai_daily' => t.aiDailyLimit,
          _ => t.aiUnavailable,
        },
      );
    } finally {
      clock.cancel();
      if (mounted) setState(() => _summaryBusy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final theme = Theme.of(context);
    final side = ref.watch(sidebarProvider).value;
    final showTr = widget.view.translated.value && _translation != null;
    final showFull = widget.view.full.value && _fullHtml != null;
    final body = theme.textTheme.bodyLarge!.copyWith(
      fontSize: 17.5,
      height: 1.55,
      color: c.text,
    );
    final title = showTr && _translation!.title != null
        ? _translation!.title!
        : (a.title ?? '');
    final meta = [
      side?.subFor(a.sourceId)?.title ?? '',
      if (a.author != null) '${t.by} ${a.author}',
      timeAgo(t, a.publishedAt),
      if (a.wordCount != null && a.wordCount! > 0)
        t.readingMinutes((a.wordCount! / 220).ceil()),
    ].where((s) => s.isNotEmpty).join(' · ');

    return ListView(
      controller: _scroll,
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 40),
      children: [
        Text(
          title,
          style: theme.textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w700,
            height: 1.2,
          ),
        ),
        if (_summary?.title != null) ...[
          const SizedBox(height: 4),
          Text('🌐 ${_summary!.title!}', style: TextStyle(color: c.muted)),
        ],
        const SizedBox(height: 8),
        Text(meta, style: TextStyle(color: c.muted, fontSize: 13)),
        const SizedBox(height: 14),
        _summaryCard(t, c),
        if (_trMsg != null) _note(_trMsg!, c),
        if (_trBusy) _note('⏳ ${t.translating}', c),
        if (showTr) ...[
          _note('🌐 ${t.machineTranslation}', c),
          for (final p in _translation!.paragraphs!)
            Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: Text(p, style: body),
            ),
        ] else ...[
          if (_fullBusy) _note('⏳ ${t.fullLoading}', c),
          if (_fullMsg != null) _note(_fullMsg!, c),
          if (showFull) _note('📰 ${t.fullNote}', c),
          ArticleHtml(
            key: ValueKey(showFull),
            html: (showFull ? _fullHtml : a.contentHtml ?? a.summary) ?? '',
            baseUrl: safeUri(a.url),
            textStyle: body,
          ),
        ],
        if (_similar.isNotEmpty) ...[
          const SizedBox(height: 28),
          Text(
            '✨ ${t.similar}',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          for (final s in _similar)
            InkWell(
              onTap: () => widget.onOpenArticle(s),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  children: [
                    if (s.imageUrl != null) ...[
                      ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: CachedNetworkImage(
                          imageUrl: s.imageUrl!,
                          width: 56,
                          height: 56,
                          fit: BoxFit.cover,
                          errorWidget: (_, _, _) => const SizedBox.shrink(),
                        ),
                      ),
                      const SizedBox(width: 12),
                    ],
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            s.title ?? '',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          Text(
                            side?.subFor(s.sourceId)?.title ?? '',
                            style: TextStyle(color: c.muted, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ],
    );
  }

  Widget _note(String text, UColors c) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Text(text, style: TextStyle(color: c.muted, fontSize: 13)),
  );

  /// Folded until asked, as on the web: "✨ AI summary ▸".
  Widget _summaryCard(AppLocalizations t, UColors c) {
    final s = _summary;
    String state = '';
    if (_summaryBusy) {
      final where = s?.status == 'queued' && s?.position != null
          ? t.aiQueued(s!.position!)
          : t.aiGenerating;
      final eta = s?.etaS != null ? ' / ~${s!.etaS} s' : '';
      state = '$where · $_summarySecs s$eta';
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: c.accentSoft,
        borderRadius: BorderRadius.circular(8),
        border: Border(left: BorderSide(color: c.accent, width: 3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          InkWell(
            onTap: _summaryBusy && _summaryOpen ? null : _summaryBar,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Row(
                children: [
                  Text(
                    '✨ ${t.aiSummary}',
                    style: TextStyle(
                      color: c.accent,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (_summaryOpen && s?.model != null && s?.summary != null)
                    Flexible(
                      child: Text(
                        ' · ${s!.model}',
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: c.muted, fontSize: 12),
                      ),
                    ),
                  const Spacer(),
                  if (state.isNotEmpty)
                    Text(state, style: TextStyle(color: c.muted, fontSize: 12)),
                  Icon(
                    _summaryOpen ? Icons.expand_more : Icons.chevron_right,
                    color: c.muted,
                  ),
                ],
              ),
            ),
          ),
          if (_summaryOpen && s?.summary != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Text(
                s!.summary!,
                style: TextStyle(color: c.text, height: 1.45),
              ),
            ),
          if (_summaryMsg != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Text(_summaryMsg!, style: TextStyle(color: c.danger)),
            ),
        ],
      ),
    );
  }
}
