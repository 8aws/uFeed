import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/api_client.dart';
import '../../api/models.dart';
import '../../auth/session.dart';
import '../../core/dialogs.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';
import '../reader/article_html.dart';
import '../reader/reader_screen.dart';
import 'article_tile.dart';
import 'home_state.dart';

/// Other copies of the same story: the ones in your own feeds open as usual;
/// the ones in feeds you don't follow can be read on their site, or that feed
/// can be followed. They never count as unread until you follow the feed.
Future<void> showTwins(BuildContext context, WidgetRef ref, Article a) =>
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (_) => _TwinsSheet(article: a),
    );

class _TwinsSheet extends ConsumerStatefulWidget {
  const _TwinsSheet({required this.article});

  final Article article;

  @override
  ConsumerState<_TwinsSheet> createState() => _TwinsSheetState();
}

class _TwinsSheetState extends ConsumerState<_TwinsSheet> {
  late final Future<List<Twin>> _twins = ref
      .read(apiProvider)
      .twins(widget.article.id);
  final _busy = <String>{};
  final _added = <String>{};

  Future<void> _open(Twin t) async {
    final id = t.articleId;
    if (id == null) return;
    final nav = Navigator.of(context, rootNavigator: true);
    try {
      final article = await ref.read(apiProvider).article(id);
      nav.pop(); // the sheet
      await nav.push(
        MaterialPageRoute<void>(
          builder: (_) => ReaderScreen(args: ReaderArgs.single(article)),
        ),
      );
    } on ApiException {
      if (mounted) toast(context, AppLocalizations.of(context).somethingFailed);
    }
  }

  /// Follow the feed this copy comes from: found from the story's own page.
  Future<void> _follow(Twin t) async {
    final t0 = AppLocalizations.of(context);
    final key = t.url ?? t.sourceTitle ?? '';
    final page = t.siteUrl ?? t.url;
    if (page == null) return;
    setState(() => _busy.add(key));
    try {
      final api = ref.read(apiProvider);
      final feeds = await api.discover(page);
      if (feeds.isEmpty) {
        if (mounted) toast(context, t0.somethingFailed);
        return;
      }
      await api.subscribe(feeds.first.feedUrl);
      await ref.read(sidebarProvider.notifier).reload();
      ref.invalidate(articleListProvider);
      if (mounted) {
        setState(() => _added.add(key));
        toast(context, t0.feedAdded);
      }
    } on ApiException catch (e) {
      if (mounted) {
        toast(
          context,
          e.code.startsWith('plan_limit')
              ? (ref.read(sessionProvider).value?.isGuest ?? false
                    ? t0.planLimitFeedsGuest
                    : t0.planLimitFeeds)
              : t0.somethingFailed,
        );
      }
    } finally {
      if (mounted) setState(() => _busy.remove(key));
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * 0.8,
        ),
        child: FutureBuilder<List<Twin>>(
          future: _twins,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              );
            }
            if (snap.hasError) {
              return Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  t.somethingFailed,
                  style: TextStyle(color: c.muted),
                ),
              );
            }
            final twins = snap.data ?? const [];
            final mine = [
              for (final x in twins)
                if (x.followed) x,
            ];
            final other = [
              for (final x in twins)
                if (!x.followed) x,
            ];
            Widget heading(String text) => Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 4),
              child: Text(
                text.toUpperCase(),
                style: TextStyle(
                  color: c.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.5,
                ),
              ),
            );
            String when(Twin x) =>
                x.publishedAt == null ? '' : ' · ${timeAgo(t, x.publishedAt)}';
            return ListView(
              shrinkWrap: true,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 4),
                  child: Text(
                    t.twinsTitle,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                if (twins.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(20),
                    child: Text(t.twinsNone, style: TextStyle(color: c.muted)),
                  ),
                if (mine.isNotEmpty) heading(t.twinsInYours),
                for (final x in mine)
                  ListTile(
                    title: Text(
                      x.title ?? '',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontWeight: x.isRead
                            ? FontWeight.w500
                            : FontWeight.w700,
                      ),
                    ),
                    subtitle: Text('${x.sourceTitle ?? ''}${when(x)}'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _open(x),
                  ),
                if (other.isNotEmpty) ...[
                  heading(t.twinsElsewhere),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 4),
                    child: Text(
                      t.twinsNote,
                      style: TextStyle(color: c.muted, fontSize: 12.5),
                    ),
                  ),
                  for (final x in other)
                    ListTile(
                      isThreeLine: true,
                      title: Text(
                        x.title ?? '',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${x.sourceTitle ?? ''}${when(x)}'),
                          const SizedBox(height: 4),
                          Wrap(
                            spacing: 8,
                            children: [
                              if (safeUri(x.url) != null)
                                OutlinedButton(
                                  onPressed: () => openLink(safeUri(x.url)!),
                                  child: Text(t.openOnSite),
                                ),
                              FilledButton.tonal(
                                onPressed:
                                    _busy.contains(
                                          x.url ?? x.sourceTitle ?? '',
                                        ) ||
                                        _added.contains(
                                          x.url ?? x.sourceTitle ?? '',
                                        )
                                    ? null
                                    : () => _follow(x),
                                child: Text(
                                  _added.contains(x.url ?? x.sourceTitle ?? '')
                                      ? t.feedAdded
                                      : t.followThisFeed,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                ],
                const SizedBox(height: 12),
              ],
            );
          },
        ),
      ),
    );
  }
}
