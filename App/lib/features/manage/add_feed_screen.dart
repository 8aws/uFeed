import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/api_client.dart';
import '../../api/models.dart';
import '../../auth/session.dart';
import '../../core/dialogs.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';
import '../home/home_state.dart';

/// The starter list editors curated on this server, or the built-in one.
final catalogProvider = FutureProvider<List<CatalogSection>>((ref) async {
  try {
    final server = await ref.read(apiProvider).catalog();
    if (server != null) return server;
  } on ApiException {
    // the built-in list will do
  }
  final raw = await rootBundle.loadString('assets/catalog.json');
  return [
    for (final s in jsonDecode(raw) as List) CatalogSection.fromJson(s as Json),
  ];
});

/// Loose URL key so `https://www.x.com/feed/` and `http://x.com/feed` match.
String feedKey(String url) => url
    .trim()
    .toLowerCase()
    .replaceFirst(RegExp(r'^https?://'), '')
    .replaceFirst(RegExp(r'^www\.'), '')
    .replaceFirst(RegExp(r'/+$'), '');

/// Add a feed by address, or pick from the starter catalogue.
class AddFeedScreen extends ConsumerStatefulWidget {
  const AddFeedScreen({super.key});

  @override
  ConsumerState<AddFeedScreen> createState() => _AddFeedScreenState();
}

class _AddFeedScreenState extends ConsumerState<AddFeedScreen> {
  final _url = TextEditingController();
  List<DiscoveredFeed>? _found;
  bool _searching = false;
  String? _msg;
  String? _folderId;
  String _lang = 'all';
  final _busy = <String>{};

  ApiClient get _api => ref.read(apiProvider);

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  String _error(AppLocalizations t, ApiException e) =>
      e.code.startsWith('plan_limit') ? t.planLimitFeeds : t.somethingFailed;

  Future<void> _discover() async {
    final t = AppLocalizations.of(context);
    var url = _url.text.trim();
    if (url.isEmpty) return;
    if (!url.contains('://')) url = 'https://$url';
    setState(() {
      _searching = true;
      _msg = null;
      _found = null;
    });
    try {
      final found = await _api.discover(url);
      if (!mounted) return;
      setState(() {
        _found = found;
        if (found.isEmpty) _msg = t.noFeedsFound;
      });
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _msg = e.isNetwork ? t.offline : t.noFeedsFound);
      }
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  Future<Subscription?> _subscribe(
    String url, {
    String? folderId,
    String? title,
  }) async {
    final t = AppLocalizations.of(context);
    setState(() => _busy.add(feedKey(url)));
    try {
      var sub = await _api.subscribe(url, folderId: folderId);
      // The catalogue's curated name when the feed's own title is generic.
      if (title != null &&
          sub.customTitle == null &&
          sub.source.title != title) {
        try {
          sub = await _api.updateSubscription(sub.id, {'custom_title': title});
        } on ApiException {
          // keep the feed's own title
        }
      }
      await ref.read(sidebarProvider.notifier).reload();
      return sub;
    } on ApiException catch (e) {
      if (mounted) toast(context, _error(t, e));
      if (e.code.startsWith('plan_limit')) rethrow;
      return null;
    } finally {
      if (mounted) setState(() => _busy.remove(feedKey(url)));
    }
  }

  /// Reuse a folder with this name (case-insensitive) or create it.
  Future<String?> _folderNamed(String name) async {
    final side = ref.read(sidebarProvider).value;
    for (final f in side?.folders ?? const <Folder>[]) {
      if (f.name.toLowerCase() == name.toLowerCase()) return f.id;
    }
    try {
      return (await _api.createFolder(name)).id;
    } on ApiException {
      return null;
    }
  }

  Future<void> _addFromCatalog(CatalogSection s, CatalogFeed f) async {
    final folder = await _folderNamed(s.name(deviceLocale()));
    await _subscribe(f.url, folderId: folder, title: f.title);
  }

  Future<void> _addAll(CatalogSection s, Set<String> have) async {
    final folder = await _folderNamed(s.name(deviceLocale()));
    for (final f in _visible(s)) {
      if (have.contains(feedKey(f.url))) continue;
      try {
        await _subscribe(f.url, folderId: folder, title: f.title);
      } on ApiException {
        return; // plan limit reached: stop here
      }
    }
  }

  Future<void> _remove(Subscription sub) async {
    try {
      await _api.unsubscribe(sub.id);
      await ref.read(sidebarProvider.notifier).reload();
    } on ApiException {
      if (mounted) toast(context, AppLocalizations.of(context).somethingFailed);
    }
  }

  List<CatalogFeed> _visible(CatalogSection s) => [
    for (final f in s.feeds)
      if (_lang == 'all' || f.lang == _lang) f,
  ];

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final side = ref.watch(sidebarProvider).value;
    final subsByUrl = {
      for (final s in side?.subs ?? const <Subscription>[])
        feedKey(s.source.feedUrl): s,
    };
    final catalog = ref.watch(catalogProvider);
    final lang = deviceLocale();

    return Scaffold(
      appBar: AppBar(title: Text(t.addFeed)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
        children: [
          TextField(
            controller: _url,
            keyboardType: TextInputType.url,
            autocorrect: false,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _discover(),
            decoration: InputDecoration(
              hintText: t.addFeedPlaceholder,
              border: const OutlineInputBorder(),
              suffixIcon: _searching
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    )
                  : IconButton(
                      tooltip: t.discover,
                      icon: const Icon(Icons.search),
                      onPressed: _discover,
                    ),
            ),
          ),
          if (side != null && side.folders.isNotEmpty) ...[
            const SizedBox(height: 8),
            DropdownButtonFormField<String?>(
              initialValue: _folderId,
              decoration: InputDecoration(
                labelText: t.folders,
                border: const OutlineInputBorder(),
                isDense: true,
              ),
              items: [
                DropdownMenuItem(value: null, child: Text(t.noFolder)),
                for (final f in side.folders)
                  DropdownMenuItem(value: f.id, child: Text(f.name)),
              ],
              onChanged: (v) => setState(() => _folderId = v),
            ),
          ],
          if (_msg != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(_msg!, style: TextStyle(color: c.muted)),
            ),
          for (final f in _found ?? const <DiscoveredFeed>[])
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.rss_feed),
              title: Text(f.title ?? f.feedUrl),
              subtitle: Text(
                f.feedUrl,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              trailing: subsByUrl.containsKey(feedKey(f.feedUrl))
                  ? Text(t.subscribed, style: TextStyle(color: c.muted))
                  : FilledButton(
                      onPressed: _busy.contains(feedKey(f.feedUrl))
                          ? null
                          : () => _subscribe(
                              f.feedUrl,
                              folderId: _folderId,
                            ).catchError((_) => null),
                      child: Text(t.subscribe),
                    ),
            ),
          const SizedBox(height: 24),
          Text(
            t.starterSources,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            showSelectedIcon: false,
            segments: [
              ButtonSegment(value: 'all', label: Text(t.allLangs)),
              ButtonSegment(value: 'es', label: Text('🇪🇸 ${t.langEs}')),
              ButtonSegment(value: 'en', label: Text('🇬🇧 ${t.langEn}')),
            ],
            selected: {_lang},
            onSelectionChanged: (v) => setState(() => _lang = v.first),
          ),
          ...catalog.when(
            loading: () => [
              const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator()),
              ),
            ],
            error: (_, _) => const [],
            data: (sections) => [
              for (final s in sections) ...[
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        s.name(lang),
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ),
                    TextButton(
                      onPressed: () =>
                          _addAll(s, subsByUrl.keys.toSet()).catchError((_) {}),
                      child: Text('+ ${t.catalogAddAll}'),
                    ),
                  ],
                ),
                for (final f in _visible(s))
                  _CatalogRow(
                    feed: f,
                    sub: subsByUrl[feedKey(f.url)],
                    busy: _busy.contains(feedKey(f.url)),
                    onAdd: () => _addFromCatalog(s, f).catchError((_) {}),
                    onRemove: _remove,
                  ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

class _CatalogRow extends StatelessWidget {
  const _CatalogRow({
    required this.feed,
    required this.sub,
    required this.busy,
    required this.onAdd,
    required this.onRemove,
  });

  final CatalogFeed feed;
  final Subscription? sub;
  final bool busy;
  final VoidCallback onAdd;
  final void Function(Subscription) onRemove;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Text(feed.lang == 'es' ? '🇪🇸' : '🇬🇧'),
      minLeadingWidth: 20,
      title: Text(feed.title),
      trailing: busy
          ? const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : sub != null
          ? OutlinedButton(
              onPressed: () => onRemove(sub!),
              child: Text('✓ ${t.catalogRemove}'),
            )
          : FilledButton.tonal(
              onPressed: onAdd,
              child: Text('+ ${t.catalogAdd}'),
            ),
    );
  }
}
