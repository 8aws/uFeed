import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../api/models.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';
import '../home/article_tile.dart';
import '../home/home_state.dart';
import 'listen_bar.dart';

/// Placeholder reader (stage 1): headline and excerpt. The full reader with
/// the article's HTML, AI summary and listening comes in stage 2.
class ReaderScreen extends ConsumerWidget {
  const ReaderScreen({super.key, required this.article});

  final Article article;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final a = article;
    final url = a.url == null ? null : Uri.tryParse(a.url!);
    return Scaffold(
      appBar: AppBar(
        actions: [
          if (url != null)
            IconButton(
              tooltip: t.share,
              icon: const Icon(Icons.ios_share),
              onPressed: () => SharePlus.instance.share(
                ShareParams(uri: url, subject: a.title),
              ),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
        children: [
          Text(
            a.title ?? '',
            style: Theme.of(
              context,
            ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Text(
            [
              if (a.author != null) a.author!,
              timeAgo(t, a.publishedAt),
            ].join(' · '),
            style: TextStyle(color: c.muted),
          ),
          const SizedBox(height: 12),
          ListenBar(
            article: a,
            sourceTitle:
                ref.watch(sidebarProvider).value?.subFor(a.sourceId)?.title ??
                '',
          ),
          const SizedBox(height: 16),
          Text(
            plainText(a.contentHtml ?? a.summary),
            style: const TextStyle(fontSize: 17, height: 1.5),
          ),
          if (url != null) ...[
            const SizedBox(height: 24),
            OutlinedButton.icon(
              icon: const Icon(Icons.open_in_new),
              label: Text(t.openOriginal),
              onPressed: () =>
                  launchUrl(url, mode: LaunchMode.inAppBrowserView),
            ),
          ],
        ],
      ),
    );
  }
}
