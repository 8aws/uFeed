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

/// One row of the list. Swipe right toggles read, swipe left toggles saved
/// (same as the web); long press marks read without opening.
class ArticleTile extends StatelessWidget {
  const ArticleTile({
    super.key,
    required this.article,
    required this.sourceTitle,
    required this.onOpen,
    required this.onToggleRead,
    required this.onToggleSaved,
  });

  final Article article;
  final String sourceTitle;
  final VoidCallback onOpen;
  final VoidCallback onToggleRead;
  final VoidCallback onToggleSaved;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final a = article;
    final excerpt = plainText(a.aiSummary ?? a.summary);
    final dim = a.isRead ? 0.55 : 1.0;

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
        const Color(0xFFF59E0B),
      ),
      child: Material(
        color: c.surface,
        child: InkWell(
          onTap: onOpen,
          onLongPress: a.isRead ? null : onToggleRead,
          child: Container(
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(color: c.border)),
            ),
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
            child: Opacity(
              opacity: dim,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            if (!a.isRead)
                              Padding(
                                padding: const EdgeInsets.only(right: 6),
                                child: CircleAvatar(
                                  radius: 3.5,
                                  backgroundColor: c.accent,
                                ),
                              ),
                            Flexible(
                              child: Text(
                                '$sourceTitle · ${timeAgo(t, a.publishedAt)}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(color: c.muted, fontSize: 12),
                              ),
                            ),
                            if (a.isSaved)
                              const Padding(
                                padding: EdgeInsets.only(left: 6),
                                child: Icon(
                                  Icons.star,
                                  size: 14,
                                  color: Color(0xFFF59E0B),
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          a.title ?? '',
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 16,
                            height: 1.25,
                            fontWeight: a.isRead
                                ? FontWeight.w500
                                : FontWeight.w700,
                            color: c.text,
                          ),
                        ),
                        if (excerpt.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            excerpt,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(color: c.muted, fontSize: 13.5),
                          ),
                        ],
                      ],
                    ),
                  ),
                  if (a.imageUrl != null) ...[
                    const SizedBox(width: 12),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: CachedNetworkImage(
                        imageUrl: a.imageUrl!,
                        width: 84,
                        height: 84,
                        fit: BoxFit.cover,
                        errorWidget: (_, _, _) => const SizedBox.shrink(),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
