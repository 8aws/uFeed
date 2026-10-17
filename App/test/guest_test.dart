import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/auth/starter_feeds.dart';

List<CatalogSection> _catalog() => [
  for (final s
      in jsonDecode(File('assets/catalog.json').readAsStringSync()) as List)
    CatalogSection.fromJson(s as Json),
];

void main() {
  test('a guest account is told apart from a registered one', () {
    final guest = User.fromJson({
      'id': 'u1',
      'email': 'guest-abc@guest.example.org',
      'role': 'guest',
      'is_guest': true,
      'locale': 'es',
    });
    expect(guest.isGuest, isTrue);
    expect(guest.role, Role.guest);
    expect(User.fromJson(guest.toJson()).isGuest, isTrue);

    final regular = User.fromJson({
      'id': 'u2',
      'email': 'a@b.es',
      'role': 'free',
    });
    expect(regular.isGuest, isFalse);
    expect(Role.parse('guest'), Role.guest);
  });

  test('the site says whether guests are welcome (yes if it does not say)', () {
    expect(
      SiteConfig.fromJson({'registration_open': false}).guestAccess,
      isTrue,
    );
    expect(
      SiteConfig.fromJson({
        'registration_open': true,
        'guest_access': false,
      }).guestAccess,
      isFalse,
    );
  });

  test('starter feeds: one per section, in the visitor\'s language', () {
    final es = pickStarterFeeds(_catalog(), 'es');
    expect(es.length, inInclusiveRange(6, 8));
    expect(es.every((f) => f.lang == 'es'), isTrue);
    expect({for (final f in es) f.url}.length, es.length);

    final en = pickStarterFeeds(_catalog(), 'en');
    expect(en.every((f) => f.lang == 'en'), isTrue);

    // A language the catalogue lacks still gets feeds (the first of each).
    expect(pickStarterFeeds(_catalog(), 'fr'), isNotEmpty);
    expect(pickStarterFeeds(const [], 'es'), isEmpty);
  });
}
