import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../api/models.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';

String timeAgo(AppLocalizations t, DateTime? when) {
  if (when == null) return '';
  final d = DateTime.now().difference(when);
  if (d.inMinutes < 60) return t.minutesAgo(d.inMinutes < 1 ? 1 : d.inMinutes);
  if (d.inHours < 24) return t.hoursAgo(d.inHours);
  return t.daysAgo(d.inDays);
}

/// Plain text of a feed excerpt (they often carry HTML).
String plainText(String? html) {
  if (html == null) return '';
  return html
      .replaceAll(RegExp(r'<[^>]*>'), ' ')
      .replaceAll('&nbsp;', ' ')
      .replaceAll('&amp;', '&')
      .replaceAll('&quot;', '"')
      .replaceAll('&#39;', "'")
      .replaceAll('&lt;', '<')
      .replaceAll('&gt;', '>')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
}

/// The list layouts, as in the web app.
enum ListStyle {
  /// Headline, source and time only.
  list,

  /// Headline and excerpt beside a thumbnail.
  cardList,

  /// Picture on top, then headline and excerpt.
  cards,

  /// Two columns of cards of varying height.
  masonry,
}

const _gold = Color(0xFFF59E0B);

/// One article in the list. Swipe right toggles read, swipe left toggles
/// saved (same as the web); long press marks read without opening.
class ArticleTile extends StatelessWidget {
  const ArticleTile({
    super.key,
    required this.article,
    required this.sourceTitle,
    required this.onOpen,
    required this.onToggleRead,
    required this.onToggleSaved,
    this.style = ListStyle.cardList,
    this.note,
  });

  final Article article;
  final String sourceTitle;
  final VoidCallback onOpen;
  final VoidCallback onToggleRead;
  final VoidCallback onToggleSaved;
  final ListStyle style;

  /// Extra text for the meta line (e.g. "12 lectores" in Trending).
  final String? note;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final a = article;

    Widget hint(IconData icon, String label, Alignment align, Color bg) =>
        Container(
          color: bg,
          alignment: align,
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: Colors.white),
              const SizedBox(height: 2),
              Text(
                label,
                style: const TextStyle(color: Colors.white, fontSize: 12),
              ),
            ],
          ),
        );

    final body = switch (style) {
      ListStyle.list => _compact(context, t, c),
      ListStyle.cardList => _cardList(context, t, c),
      ListStyle.cards || ListStyle.masonry => _card(context, t, c),
    };
    final grid = style == ListStyle.masonry;

    return Dismissible(
      key: ValueKey('swipe-${a.id}'),
      dismissThresholds: const {
        DismissDirection.startToEnd: 0.25,
        DismissDirection.endToStart: 0.25,
      },
      confirmDismiss: (dir) async {
        if (dir == DismissDirection.startToEnd) {
          onToggleRead();
        } else {
          onToggleSaved();
        }
        return false; // the row stays; only its state changes
      },
      background: hint(
        a.isRead ? Icons.mark_email_unread_outlined : Icons.done,
        a.isRead ? t.markUnread : t.markRead,
        Alignment.centerLeft,
        c.accent,
      ),
      secondaryBackground: hint(
        a.isSaved ? Icons.star_border : Icons.star,
        a.isSaved ? t.unsave : t.save,
        Alignment.centerRight,
        _gold,
      ),
      child: Material(
        color: c.surface,
        borderRadius: grid ? BorderRadius.circular(10) : null,
        clipBehavior: grid ? Clip.antiAlias : Clip.none,
        child: InkWell(
          onTap: onOpen,
          onLongPress: a.isRead ? null : onToggleRead,
          child: Container(
            decoration: grid
                ? BoxDecoration(
                    border: Border.all(color: c.border),
                    borderRadius: BorderRadius.circular(10),
                  )
                : BoxDecoration(
                    border: Border(bottom: BorderSide(color: c.border)),
                  ),
            child: Opacity(opacity: a.isRead ? 0.55 : 1.0, child: body),
          ),
        ),
      ),
    );
  }

  String get _excerpt => plainText(article.aiSummary ?? article.summary);

  Widget _title(UColors c, {int lines = 3, double size = 16}) => Text(
    article.title ?? article.url ?? '',
    maxLines: lines,
    overflow: TextOverflow.ellipsis,
    style: TextStyle(
      fontSize: size,
      height: 1.25,
      fontWeight: article.isRead ? FontWeight.w500 : FontWeight.w700,
      color: c.text,
    ),
  );

  /// "• Xataka · 5 min ★ ♥"
  Widget _meta(AppLocalizations t, UColors c, {bool time = true}) {
    final a = article;
    final text = [
      sourceTitle,
      if (time) timeAgo(t, a.publishedAt),
      ?note,
    ].where((s) => s.isNotEmpty).join(' · ');
    return Row(
      children: [
        if (!a.isRead)
          Padding(
            padding: const EdgeInsets.only(right: 6),
            child: CircleAvatar(radius: 3.5, backgroundColor: c.accent),
          ),
        Flexible(
          child: Text(
            text,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: c.muted, fontSize: 12),
          ),
        ),
        if (a.dupCount > 1)
          Padding(
            padding: const EdgeInsets.only(left: 6),
            child: Text(
              '+${a.dupCount - 1}',
              style: TextStyle(color: c.muted, fontSize: 12),
            ),
          ),
        if (a.isSaved)
          const Padding(
            padding: EdgeInsets.only(left: 6),
            child: Icon(Icons.star, size: 14, color: _gold),
          ),
        if (a.isFavorite)
          Padding(
            padding: const EdgeInsets.only(left: 4),
            child: Icon(Icons.favorite, size: 13, color: c.danger),
          ),
      ],
    );
  }

  Widget _image(String url, {double? width, double? height}) =>
      CachedNetworkImage(
        imageUrl: url,
        width: width,
        height: height,
        fit: BoxFit.cover,
        errorWidget: (_, _, _) => const SizedBox.shrink(),
      );

  Widget _compact(BuildContext context, AppLocalizations t, UColors c) =>
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: _title(c, lines: 2, size: 15)),
                const SizedBox(width: 8),
                Text(
                  timeAgo(t, article.publishedAt),
                  style: TextStyle(color: c.muted, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 3),
            _meta(t, c, time: false),
          ],
        ),
      );

  Widget _cardList(BuildContext context, AppLocalizations t, UColors c) {
    final img = article.imageUrl;
    final excerpt = _excerpt;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [_meta(t, c), const SizedBox(height: 4), _title(c)],
                ),
              ),
              if (img != null) ...[
                const SizedBox(width: 12),
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: _image(img, width: 84, height: 84),
                ),
              ],
            ],
          ),
          // Full width under the picture, like the web's card list.
          if (excerpt.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              excerpt,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: c.muted, fontSize: 13.5),
            ),
          ],
        ],
      ),
    );
  }

  Widget _card(BuildContext context, AppLocalizations t, UColors c) {
    final img = article.imageUrl;
    final excerpt = _excerpt;
    final grid = style == ListStyle.masonry;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (img != null)
          grid
              ? _image(img)
              : AspectRatio(aspectRatio: 16 / 9, child: _image(img)),
        Padding(
          padding: EdgeInsets.fromLTRB(grid ? 10 : 16, 10, grid ? 10 : 16, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _title(c, lines: grid ? 4 : 3, size: grid ? 14.5 : 17),
              const SizedBox(height: 4),
              _meta(t, c),
              if (excerpt.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  excerpt,
                  maxLines: grid ? 4 : 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: c.muted,
                    fontSize: grid ? 12.5 : 13.5,
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
