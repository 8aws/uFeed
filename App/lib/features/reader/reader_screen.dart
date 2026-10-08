import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';

import '../../api/models.dart';
import '../../auth/session.dart';
import '../../core/prefs.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';
import '../home/home_state.dart';
import 'article_html.dart';
import 'article_page.dart';
import 'listen_bar.dart';

/// What the reader opens: a list and where in it (swipe for the others).
class ReaderArgs {
  const ReaderArgs(this.articles, this.index);

  ReaderArgs.single(Article a) : articles = [a], index = 0;

  final List<Article> articles;
  final int index;
}

enum _More { read, full, translate, original, text }

/// The reader: one page per article of the list it was opened from (swipe
/// sideways for the next/previous), the toolbar and the listen bar.
class ReaderScreen extends ConsumerStatefulWidget {
  const ReaderScreen({super.key, required this.args});

  final ReaderArgs args;

  @override
  ConsumerState<ReaderScreen> createState() => _ReaderScreenState();
}

class _ReaderScreenState extends ConsumerState<ReaderScreen> {
  late final List<Article> _articles = [...widget.args.articles];
  late final _pages = PageController(initialPage: widget.args.index);
  late int _index = widget.args.index;
  final _views = <String, ArticleViewState>{};

  Article get _current => _articles[_index];
  ArticleViewState _view(String id) => _views[id] ??= ArticleViewState();

  @override
  void initState() {
    super.initState();
    // Not during the first build: it updates the list's providers.
    Future.microtask(() {
      if (mounted) setState(() => _markRead(_index));
    });
  }

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  ArticleListNotifier get _list => ref.read(articleListProvider.notifier);

  /// Opening an article marks it read (as on the web).
  void _markRead(int i) {
    final a = _articles[i];
    if (a.isRead) return;
    _list.setRead(a, true);
    _articles[i] = a.copyWith(isRead: true);
  }

  void _update(Article next) => setState(
    () => _articles[_articles.indexWhere((x) => x.id == next.id)] = next,
  );

  void _toggleRead() {
    final a = _current;
    _list.setRead(a, !a.isRead);
    _update(a.copyWith(isRead: !a.isRead));
  }

  void _toggleSaved() {
    final a = _current;
    _list.setSaved(a, !a.isSaved);
    _update(a.copyWith(isSaved: !a.isSaved));
  }

  void _toggleFavorite() {
    final a = _current;
    _list.setFavorite(a, !a.isFavorite);
    _update(a.copyWith(isFavorite: !a.isFavorite));
  }

  void _share() {
    final a = _current;
    final url = safeUri(a.url);
    if (url == null) return;
    ref.read(apiProvider).engage(a.id, 'share').ignore();
    SharePlus.instance.share(ShareParams(uri: url, subject: a.title)).ignore();
  }

  /// A similar article: opened on its own, on top of this one.
  void _openOther(Article a) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ReaderScreen(args: ReaderArgs.single(a)),
      ),
    );
  }

  void _more(_More choice) {
    final a = _current;
    final view = _view(a.id);
    switch (choice) {
      case _More.read:
        _toggleRead();
      case _More.full:
        view.full.value = !view.full.value;
      case _More.translate:
        view.translated.value = !view.translated.value;
      case _More.original:
        final url = safeUri(a.url);
        if (url != null) openLink(url).ignore();
      case _More.text:
        _textSheet();
    }
    setState(() {});
  }

  void _textSheet() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => Consumer(
        builder: (context, ref, _) {
          final t = AppLocalizations.of(context);
          final prefs = ref.watch(displayPrefsProvider);
          final set = ref.read(displayPrefsProvider.notifier).update;
          return SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(t.textSize),
                  const SizedBox(height: 8),
                  SegmentedButton<double>(
                    showSelectedIcon: false,
                    segments: [
                      for (final s in textScales)
                        ButtonSegment(
                          value: s,
                          label: Text(
                            'A',
                            style: TextStyle(fontSize: 13 * s),
                            textScaler: TextScaler.noScaling,
                          ),
                        ),
                    ],
                    selected: {prefs.textScale},
                    onSelectionChanged: (v) =>
                        set(prefs.copyWith(textScale: v.first)),
                  ),
                  const SizedBox(height: 16),
                  Text(t.font),
                  const SizedBox(height: 8),
                  SegmentedButton<bool>(
                    showSelectedIcon: false,
                    segments: [
                      ButtonSegment(value: false, label: Text(t.fontSystem)),
                      const ButtonSegment(
                        value: true,
                        label: Text(
                          'Atkinson',
                          style: TextStyle(fontFamily: 'Atkinson Hyperlegible'),
                        ),
                      ),
                    ],
                    selected: {prefs.atkinson},
                    onSelectionChanged: (v) =>
                        set(prefs.copyWith(atkinson: v.first)),
                  ),
                  const SizedBox(height: 8),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(t.autoFull),
                    value: prefs.autoFull,
                    onChanged: (v) => set(prefs.copyWith(autoFull: v)),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final a = _current;
    final view = _view(a.id);
    final side = ref.watch(sidebarProvider).value;
    final hasUrl = safeUri(a.url) != null;

    return Scaffold(
      appBar: AppBar(
        actions: [
          IconButton(
            tooltip: a.isSaved ? t.unsave : t.save,
            icon: Icon(
              a.isSaved ? Icons.star : Icons.star_border,
              color: a.isSaved ? const Color(0xFFF59E0B) : null,
            ),
            onPressed: _toggleSaved,
          ),
          IconButton(
            tooltip: a.isFavorite ? t.unfavorite : t.favorite,
            icon: Icon(
              a.isFavorite ? Icons.favorite : Icons.favorite_border,
              color: a.isFavorite ? c.danger : null,
            ),
            onPressed: _toggleFavorite,
          ),
          if (hasUrl)
            IconButton(
              tooltip: t.share,
              icon: const Icon(Icons.ios_share),
              onPressed: _share,
            ),
          PopupMenuButton<_More>(
            tooltip: t.more,
            onSelected: _more,
            itemBuilder: (_) => [
              _item(
                _More.read,
                a.isRead ? Icons.mark_email_unread_outlined : Icons.done,
                a.isRead ? t.markUnread : t.markRead,
              ),
              if (hasUrl)
                _item(
                  _More.full,
                  Icons.article_outlined,
                  view.full.value ? t.showExcerpt : t.fullArticle,
                ),
              if (canTranslate(a))
                _item(
                  _More.translate,
                  Icons.translate,
                  view.translated.value ? t.showOriginal : t.translate,
                ),
              if (hasUrl)
                _item(_More.original, Icons.open_in_new, t.openOriginal),
              _item(_More.text, Icons.text_fields, t.textSize),
            ],
          ),
        ],
      ),
      body: PageView.builder(
        controller: _pages,
        itemCount: _articles.length,
        onPageChanged: (i) {
          _markRead(i);
          setState(() => _index = i);
        },
        itemBuilder: (context, i) => ArticlePage(
          key: ValueKey(_articles[i].id),
          article: _articles[i],
          view: _view(_articles[i].id),
          onOpenArticle: _openOther,
        ),
      ),
      // Outside the page, so scrolling the text doesn't stop the audio.
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: c.surface,
          border: Border(top: BorderSide(color: c.border)),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 6, 16, 6),
            child: ListenBar(
              key: ValueKey('listen-${a.id}'),
              article: a,
              sourceTitle: side?.subFor(a.sourceId)?.title ?? '',
            ),
          ),
        ),
      ),
    );
  }

  PopupMenuItem<_More> _item(_More value, IconData icon, String label) =>
      PopupMenuItem(
        value: value,
        child: Row(
          children: [
            Icon(icon, size: 20),
            const SizedBox(width: 12),
            Text(label),
          ],
        ),
      );
}
