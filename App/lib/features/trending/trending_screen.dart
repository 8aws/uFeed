import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../api/api_client.dart';
import '../../api/models.dart';
import '../../auth/session.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';
import '../home/article_tile.dart';
import '../home/home_state.dart';
import '../reader/reader_screen.dart';

/// Trending rankings over the last 30 days, as in the web's 🔥 panel.
final insightsProvider = FutureProvider.autoDispose<Insights>(
  (ref) => ref.watch(apiProvider).insights(),
);

class TrendingScreen extends ConsumerWidget {
  const TrendingScreen({super.key});

  static String rankingName(AppLocalizations t, Ranking r) => switch (r) {
    Ranking.trendingNow => t.trendingNow,
    Ranking.top => t.top,
    Ranking.mostSaved => t.mostSaved,
    Ranking.deepReads => t.deepReads,
    Ranking.hiddenGems => t.hiddenGems,
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final insights = ref.watch(insightsProvider);
    final side = ref.watch(sidebarProvider).value;

    return DefaultTabController(
      length: Ranking.values.length,
      child: Scaffold(
        appBar: AppBar(
          title: Text(t.trending),
          bottom: TabBar(
            isScrollable: true,
            tabAlignment: TabAlignment.start,
            tabs: [
              for (final r in Ranking.values) Tab(text: rankingName(t, r)),
            ],
          ),
        ),
        body: insights.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  e is ApiException && e.isNetwork ? t.offline : '$e',
                  style: TextStyle(color: c.muted),
                ),
                TextButton(
                  onPressed: () => ref.invalidate(insightsProvider),
                  child: Text(t.retry),
                ),
              ],
            ),
          ),
          data: (data) => TabBarView(
            children: [
              for (final r in Ranking.values)
                RefreshIndicator(
                  onRefresh: () => ref.refresh(insightsProvider.future),
                  child: data.rankings[r]!.isEmpty
                      ? ListView(
                          children: [
                            const SizedBox(height: 120),
                            Center(
                              child: Text(
                                t.noArticles,
                                style: TextStyle(color: c.muted),
                              ),
                            ),
                          ],
                        )
                      : _RankingList(
                          items: data.rankings[r]!,
                          side: side,
                          onOpen: (articles, i) => context.push(
                            '/article/${articles[i].id}',
                            extra: ReaderArgs(articles, i),
                          ),
                        ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// One ranking. Read/saved changes are kept locally so the rows update.
class _RankingList extends ConsumerStatefulWidget {
  const _RankingList({
    required this.items,
    required this.side,
    required this.onOpen,
  });

  final List<RankedArticle> items;
  final Sidebar? side;
  final void Function(List<Article> articles, int index) onOpen;

  @override
  ConsumerState<_RankingList> createState() => _RankingListState();
}

class _RankingListState extends ConsumerState<_RankingList> {
  late final _articles = [for (final it in widget.items) it.article];

  Future<void> _update(
    int i,
    Article next,
    Future<void> Function() call,
  ) async {
    final before = _articles[i];
    setState(() => _articles[i] = next);
    try {
      await call();
    } on ApiException {
      if (mounted) setState(() => _articles[i] = before);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final api = ref.read(apiProvider);
    return ListView.builder(
      physics: const AlwaysScrollableScrollPhysics(),
      itemCount: _articles.length,
      itemBuilder: (context, i) {
        final a = _articles[i];
        return ArticleTile(
          key: ValueKey(a.id),
          article: a,
          sourceTitle: widget.side?.subFor(a.sourceId)?.title ?? '',
          note: t.readers(widget.items[i].readers),
          onOpen: () {
            widget.onOpen(List.of(_articles), i);
            setState(() => _articles[i] = a.copyWith(isRead: true));
          },
          onToggleRead: () => _update(
            i,
            a.copyWith(isRead: !a.isRead),
            () => api.setRead(a.id, !a.isRead),
          ),
          onToggleSaved: () => _update(
            i,
            a.copyWith(isSaved: !a.isSaved),
            () => api.setSaved(a.id, !a.isSaved),
          ),
        );
      },
    );
  }
}
