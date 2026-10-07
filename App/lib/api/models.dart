// The API's JSON shapes (see API/openapi.json), written by hand for the
// routes the app uses. Field names follow the server; Dart names are camelCase.

typedef Json = Map<String, dynamic>;

DateTime? _date(Object? v) => v is String ? DateTime.tryParse(v) : null;

enum Role {
  free,
  general,
  vip,
  editor,
  admin;

  static Role parse(Object? v) =>
      Role.values.firstWhere((r) => r.name == v, orElse: () => Role.free);
}

class Tokens {
  const Tokens({required this.access, required this.refresh});

  final String access;
  final String refresh;

  factory Tokens.fromJson(Json j) => Tokens(
    access: j['access_token'] as String,
    refresh: j['refresh_token'] as String,
  );
}

class User {
  const User({
    required this.id,
    required this.email,
    required this.displayName,
    required this.locale,
    required this.role,
    required this.mustChangePassword,
  });

  final String id;
  final String email;
  final String? displayName;
  final String locale;
  final Role role;
  final bool mustChangePassword;

  factory User.fromJson(Json j) => User(
    id: j['id'] as String,
    email: j['email'] as String,
    displayName: j['display_name'] as String?,
    locale: j['locale'] as String? ?? 'es',
    role: Role.parse(j['role']),
    mustChangePassword: j['must_change_password'] as bool? ?? false,
  );
}

class Folder {
  const Folder({required this.id, required this.name, required this.position});

  final String id;
  final String name;
  final int position;

  factory Folder.fromJson(Json j) => Folder(
    id: j['id'] as String,
    name: j['name'] as String,
    position: j['position'] as int? ?? 0,
  );
}

class Source {
  const Source({
    required this.id,
    required this.feedUrl,
    required this.siteUrl,
    required this.title,
    required this.faviconUrl,
  });

  final String id;
  final String feedUrl;
  final String? siteUrl;
  final String? title;
  final String? faviconUrl;

  factory Source.fromJson(Json j) => Source(
    id: j['id'] as String,
    feedUrl: j['feed_url'] as String,
    siteUrl: j['site_url'] as String?,
    title: j['title'] as String?,
    faviconUrl: j['favicon_url'] as String?,
  );
}

class Subscription {
  const Subscription({
    required this.id,
    required this.source,
    required this.folderId,
    required this.customTitle,
    required this.unreadCount,
    required this.muted,
  });

  final String id;
  final Source source;
  final String? folderId;
  final String? customTitle;
  final int unreadCount;
  final bool muted;

  String get title => customTitle ?? source.title ?? source.feedUrl;

  Subscription withUnread(int n) => Subscription(
    id: id,
    source: source,
    folderId: folderId,
    customTitle: customTitle,
    unreadCount: n < 0 ? 0 : n,
    muted: muted,
  );

  factory Subscription.fromJson(Json j) => Subscription(
    id: j['id'] as String,
    source: Source.fromJson(j['source'] as Json),
    folderId: j['folder_id'] as String?,
    customTitle: j['custom_title'] as String?,
    unreadCount: j['unread_count'] as int? ?? 0,
    muted: j['muted'] as bool? ?? false,
  );
}

class Article {
  const Article({
    required this.id,
    required this.sourceId,
    required this.url,
    required this.title,
    required this.author,
    required this.summary,
    required this.aiSummary,
    required this.contentHtml,
    required this.imageUrl,
    required this.lang,
    required this.wordCount,
    required this.publishedAt,
    required this.fullStatus,
    required this.isRead,
    required this.isSaved,
    required this.isFavorite,
    required this.dupCount,
  });

  final String id;
  final String sourceId;
  final String? url;
  final String? title;
  final String? author;
  final String? summary;
  final String? aiSummary;
  final String? contentHtml;
  final String? imageUrl;
  final String? lang;
  final int? wordCount;
  final DateTime? publishedAt;
  final String? fullStatus;
  final bool isRead;
  final bool isSaved;
  final bool isFavorite;
  final int dupCount;

  Article copyWith({bool? isRead, bool? isSaved, bool? isFavorite}) => Article(
    id: id,
    sourceId: sourceId,
    url: url,
    title: title,
    author: author,
    summary: summary,
    aiSummary: aiSummary,
    contentHtml: contentHtml,
    imageUrl: imageUrl,
    lang: lang,
    wordCount: wordCount,
    publishedAt: publishedAt,
    fullStatus: fullStatus,
    isRead: isRead ?? this.isRead,
    isSaved: isSaved ?? this.isSaved,
    isFavorite: isFavorite ?? this.isFavorite,
    dupCount: dupCount,
  );

  factory Article.fromJson(Json j) => Article(
    id: j['id'] as String,
    sourceId: j['source_id'] as String,
    url: j['url'] as String?,
    title: j['title'] as String?,
    author: j['author'] as String?,
    summary: j['summary'] as String?,
    aiSummary: j['ai_summary'] as String?,
    contentHtml: j['content_html'] as String?,
    imageUrl: j['image_url'] as String?,
    lang: j['lang'] as String?,
    wordCount: j['word_count'] as int?,
    publishedAt: _date(j['published_at']),
    fullStatus: j['full_status'] as String?,
    isRead: j['is_read'] as bool? ?? false,
    isSaved: j['is_saved'] as bool? ?? false,
    isFavorite: j['is_favorite'] as bool? ?? false,
    dupCount: j['dup_count'] as int? ?? 1,
  );
}

class Page<T> {
  const Page({required this.items, required this.nextCursor});

  final List<T> items;
  final String? nextCursor;

  factory Page.fromJson(Json j, T Function(Json) item) => Page(
    items: [for (final e in j['items'] as List) item(e as Json)],
    nextCursor: j['next_cursor'] as String?,
  );
}

class SiteConfig {
  const SiteConfig({
    required this.registrationOpen,
    required this.contactEmail,
  });

  final bool registrationOpen;
  final String? contactEmail;

  factory SiteConfig.fromJson(Json j) => SiteConfig(
    registrationOpen: j['registration_open'] as bool? ?? false,
    contactEmail: j['contact_email'] as String?,
  );
}
