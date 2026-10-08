import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_staggered_grid_view/flutter_staggered_grid_view.dart';
import 'package:go_router/go_router.dart';

import '../../api/models.dart';
import '../../auth/session.dart';
import '../../core/prefs.dart';
import '../../core/theme.dart';
import '../../listen/listen_bar.dart';
import '../../listen/listen_controller.dart';
import '../../offline/providers.dart';
import '../../l10n/app_localizations.dart';
import '../reader/reader_screen.dart';
import 'article_tile.dart';
import 'home_state.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      // Load the next page well before the end, like the web's 800 px margin.
      if (_scroll.position.extentAfter < 800) {
        ref.read(articleListProvider.notifier).load();
      }
    });
    // Fetch due feeds once when the app opens.
    Future.microtask(
      () => ref.read(articleListProvider.notifier).refresh(onlyIfNew: true),
    );
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  String _title(AppLocalizations t, Filter f, Sidebar? side) =>
      switch (f.kind) {
        FilterKind.all => t.all,
        FilterKind.unread => t.unread,
        FilterKind.saved => t.saved,
        FilterKind.favorites => t.favorites,
        FilterKind.forYou => t.forYou,
        FilterKind.folder =>
          side?.folders.where((x) => x.id == f.id).firstOrNull?.name ??
              t.folders,
        FilterKind.source => side?.subFor(f.id!)?.title ?? t.feeds,
      };

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final filter = ref.watch(filterProvider);
    final list = ref.watch(articleListProvider);
    final side = ref.watch(sidebarProvider).value;
    final ctrl = ref.read(articleListProvider.notifier);
    final scoped =
        filter.kind == FilterKind.folder || filter.kind == FilterKind.source;
    final onlyUnread = ref.watch(onlyUnreadProvider);
    final canMarkAll = !const {
      FilterKind.saved,
      FilterKind.favorites,
      FilterKind.forYou,
    }.contains(filter.kind);
    final style = ref.watch(listStyleProvider);

    ref.listen(filterProvider, (_, _) {
      if (_scroll.hasClients) _scroll.jumpTo(0);
    });
    ref.listen(listenProvider.select((s) => s.radioDone), (_, done) {
      if (done) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('📻 ${t.radioDone}')));
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: GestureDetector(
          onTap: () => _scroll.hasClients
              ? _scroll.animateTo(
                  0,
                  duration: const Duration(milliseconds: 300),
                  curve: Curves.easeOut,
                )
              : null,
          child: Text(_title(t, filter, side)),
        ),
        actions: [
          if (scoped)
            IconButton(
              tooltip: onlyUnread ? t.all : t.unread,
              icon: Icon(
                onlyUnread ? Icons.filter_alt : Icons.filter_alt_outlined,
              ),
              onPressed: ref.read(onlyUnreadProvider.notifier).toggle,
            ),
          if (canMarkAll)
            IconButton(
              tooltip: t.markAllRead,
              icon: const Icon(Icons.done_all),
              onPressed: list.items.any((a) => !a.isRead)
                  ? ctrl.markAllRead
                  : null,
            ),
          PopupMenuButton<ListStyle>(
            tooltip: t.view,
            icon: Icon(_styleIcon(style)),
            initialValue: style,
            onSelected: ref.read(listStyleProvider.notifier).set,
            itemBuilder: (_) => [
              for (final s in ListStyle.values)
                CheckedPopupMenuItem(
                  value: s,
                  checked: s == style,
                  child: Text(_styleName(t, s)),
                ),
            ],
          ),
        ],
      ),
      drawer: const _SideMenu(),
      bottomNavigationBar: MiniPlayer(
        onOpen: (a) =>
            context.push('/article/${a.id}', extra: ReaderArgs.single(a)),
      ),
      body: Column(
        children: [
          _OfflineBanner(offline: list.offline),
          Expanded(
            child: RefreshIndicator(
              onRefresh: ctrl.refresh,
              child: _body(t, c, list, side, ctrl, style, scoped && onlyUnread),
            ),
          ),
        ],
      ),
    );
  }

  static IconData _styleIcon(ListStyle s) => switch (s) {
    ListStyle.list => Icons.view_headline,
    ListStyle.cardList => Icons.view_list,
    ListStyle.cards => Icons.view_agenda_outlined,
    ListStyle.masonry => Icons.dashboard_outlined,
  };

  static String _styleName(AppLocalizations t, ListStyle s) => switch (s) {
    ListStyle.list => t.viewList,
    ListStyle.cardList => t.viewCardList,
    ListStyle.cards => t.viewCards,
    ListStyle.masonry => t.viewMasonry,
  };

  Widget _body(
    AppLocalizations t,
    UColors c,
    ArticleList list,
    Sidebar? side,
    ArticleListNotifier ctrl,
    ListStyle style,
    bool onlyUnreadHere,
  ) {
    if (list.items.isEmpty) {
      final String message;
      if (list.loading) {
        return const Center(child: CircularProgressIndicator());
      } else if (list.error != null) {
        message = list.error!.isNetwork ? t.offline : list.error!.message;
      } else {
        message = ctrl.unreadView ? t.noUnreadHere : t.noArticles;
      }
      // Scrollable so pull-to-refresh still works on an empty list.
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          const SizedBox(height: 120),
          Center(
            child: Text(message, style: TextStyle(color: c.muted)),
          ),
          if (list.error != null)
            Center(
              child: TextButton(
                onPressed: () => ctrl.load(reset: true),
                child: Text(t.retry),
              ),
            )
          else if (onlyUnreadHere)
            Center(
              child: TextButton(
                onPressed: ref.read(onlyUnreadProvider.notifier).toggle,
                child: Text(t.showAllPosts),
              ),
            ),
        ],
      );
    }
    final count = list.items.length + (list.done ? 0 : 1);
    Widget item(BuildContext context, int i) {
      if (i == list.items.length) {
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: list.error != null
                ? TextButton(onPressed: ctrl.load, child: Text(t.retry))
                : const CircularProgressIndicator(),
          ),
        );
      }
      final a = list.items[i];
      return ArticleTile(
        key: ValueKey(a.id),
        article: a,
        style: style,
        sourceTitle: side?.subFor(a.sourceId)?.title ?? '',
        onOpen: () =>
            context.push('/article/${a.id}', extra: ReaderArgs(list.items, i)),
        onToggleRead: () => ctrl.setRead(a, !a.isRead),
        onToggleSaved: () => ctrl.setSaved(a, !a.isSaved),
      );
    }

    if (style == ListStyle.masonry) {
      return MasonryGridView.count(
        controller: _scroll,
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(10),
        crossAxisCount: 2,
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        itemCount: count,
        itemBuilder: item,
      );
    }
    return ListView.builder(
      controller: _scroll,
      physics: const AlwaysScrollableScrollPhysics(),
      itemCount: count,
      itemBuilder: item,
    );
  }
}

class _SideMenu extends ConsumerWidget {
  const _SideMenu();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final current = ref.watch(filterProvider);
    final side = ref.watch(sidebarProvider);
    final user = ref.watch(sessionProvider).value;

    void pick(Filter f) {
      ref.read(filterProvider.notifier).set(f);
      Navigator.of(context).pop();
    }

    Widget count(int n) => n == 0
        ? const SizedBox.shrink()
        : Text('$n', style: TextStyle(color: c.muted, fontSize: 13));

    Widget item(
      Filter f,
      Widget icon,
      String label, {
      int unread = 0,
      double indent = 0,
    }) => ListTile(
      dense: true,
      contentPadding: EdgeInsets.only(left: 16 + indent, right: 16),
      leading: icon,
      minLeadingWidth: 20,
      title: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
      trailing: count(unread),
      selected: current == f,
      selectedTileColor: c.accentSoft,
      onTap: () => pick(f),
    );

    Widget favicon(Subscription s) => ClipRRect(
      borderRadius: BorderRadius.circular(3),
      child: s.source.faviconUrl == null
          ? Icon(Icons.rss_feed, size: 18, color: c.muted)
          : CachedNetworkImage(
              imageUrl: s.source.faviconUrl!,
              width: 18,
              height: 18,
              errorWidget: (_, _, _) =>
                  Icon(Icons.rss_feed, size: 18, color: c.muted),
            ),
    );

    final data = side.value;
    return Drawer(
      child: SafeArea(
        child: ListView(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.asset(
                      'assets/icon/ufeed_icon.png',
                      width: 32,
                      height: 32,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      t.appName,
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            item(
              const Filter(FilterKind.unread),
              const Icon(Icons.mark_email_unread_outlined),
              t.unread,
              unread: data?.unreadTotal ?? 0,
            ),
            item(
              const Filter(FilterKind.all),
              const Icon(Icons.inbox_outlined),
              t.all,
            ),
            item(
              const Filter(FilterKind.saved),
              const Icon(Icons.star_border),
              t.saved,
            ),
            item(
              const Filter(FilterKind.favorites),
              const Icon(Icons.favorite_border),
              t.favorites,
            ),
            item(
              const Filter(FilterKind.forYou),
              const Icon(Icons.auto_awesome_outlined),
              t.forYou,
            ),
            ListTile(
              dense: true,
              leading: const Icon(Icons.local_fire_department_outlined),
              minLeadingWidth: 20,
              title: Text(t.trending),
              onTap: () {
                Navigator.of(context).pop();
                context.push('/trending');
              },
            ),
            const Divider(),
            if (side.isLoading && data == null)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (data != null) ...[
              for (final folder in data.folders) ...[
                item(
                  Filter(FilterKind.folder, folder.id),
                  const Icon(Icons.folder_outlined),
                  folder.name,
                  unread: data.unreadIn(folder.id),
                ),
                for (final s in data.subs.where((s) => s.folderId == folder.id))
                  item(
                    Filter(FilterKind.source, s.source.id),
                    favicon(s),
                    s.title,
                    unread: s.muted ? 0 : s.unreadCount,
                    indent: 16,
                  ),
              ],
              for (final s in data.subs.where((s) => s.folderId == null))
                item(
                  Filter(FilterKind.source, s.source.id),
                  favicon(s),
                  s.title,
                  unread: s.muted ? 0 : s.unreadCount,
                ),
            ],
            const Divider(),
            if (user != null)
              ListTile(
                dense: true,
                leading: const Icon(Icons.person_outline),
                title: Text(user.email, overflow: TextOverflow.ellipsis),
              ),
            ListTile(
              dense: true,
              leading: const Icon(Icons.logout),
              title: Text(t.logout),
              onTap: () {
                Navigator.of(context).pop();
                ref.read(sessionProvider.notifier).logout();
              },
            ),
          ],
        ),
      ),
    );
  }
}

/// "Offline" and/or "N changes waiting to sync", above the list.
class _OfflineBanner extends ConsumerWidget {
  const _OfflineBanner({required this.offline});

  final bool offline;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final outbox = ref.watch(outboxProvider);
    return StreamBuilder<int>(
      stream: outbox.pending.stream,
      initialData: outbox.count,
      builder: (context, snap) {
        final n = snap.data ?? 0;
        if (!offline && n == 0) return const SizedBox.shrink();
        return Container(
          width: double.infinity,
          color: c.accentSoft,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              Icon(
                offline ? Icons.cloud_off : Icons.sync,
                size: 16,
                color: c.muted,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  [
                    if (offline) t.offlineBanner,
                    if (n > 0) t.pendingSync(n),
                  ].join(' · '),
                  style: TextStyle(color: c.muted, fontSize: 12.5),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
