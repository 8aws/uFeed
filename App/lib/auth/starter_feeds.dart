import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../features/home/home_state.dart';
import 'session.dart';

/// Sections the first feeds come from (one each), so a new visitor has
/// something to read at once.
const _starterSections = [
  'tech',
  'world',
  'science',
  'business',
  'culture',
  'gaming',
  'sports',
  'space',
];

/// The feeds to start with: one per section, in the visitor's language when
/// the section has one. Uses the list editors curated on the server, or the
/// built-in one.
List<CatalogFeed> pickStarterFeeds(List<CatalogSection> catalog, String lang) {
  final picks = <CatalogFeed>[];
  for (final id in _starterSections) {
    final section = catalog.where((s) => s.id == id).firstOrNull;
    if (section == null || section.feeds.isEmpty) continue;
    picks.add(
      section.feeds.where((f) => f.lang == lang).firstOrNull ??
          section.feeds.first,
    );
  }
  return picks;
}

/// Subscribes a new guest to the starter feeds, in the background, and
/// refreshes the screen as they arrive. Failures are ignored: the visitor
/// can always add feeds from the catalogue.
Future<void> subscribeStarterFeeds(Ref ref, String lang) async {
  final api = ref.read(apiProvider);
  List<CatalogSection> catalog;
  try {
    catalog = await api.catalog() ?? await _bundled();
  } on ApiException {
    catalog = await _bundled();
  }
  var added = 0;
  await Future.wait([
    for (final f in pickStarterFeeds(catalog, lang))
      api
          .subscribe(f.url)
          .then((_) => added++)
          .onError<Object>((_, _) => added),
  ]);
  if (added == 0 || ref.read(sessionProvider).value == null) return;
  await ref.read(sidebarProvider.notifier).reload();
  ref.invalidate(articleListProvider);
}

Future<List<CatalogSection>> _bundled() async {
  final raw = await rootBundle.loadString('assets/catalog.json');
  return [
    for (final s in jsonDecode(raw) as List) CatalogSection.fromJson(s as Json),
  ];
}
