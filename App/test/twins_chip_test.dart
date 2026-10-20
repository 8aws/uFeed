import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/core/theme.dart';
import 'package:ufeed/features/home/article_tile.dart';
import 'package:ufeed/l10n/app_localizations.dart';

Article _article({int dup = 1, int other = 0}) => Article(
  id: 'a',
  sourceId: 's',
  url: null,
  title: 'Same story',
  author: null,
  summary: null,
  aiSummary: null,
  contentHtml: null,
  imageUrl: null,
  lang: 'es',
  wordCount: null,
  publishedAt: DateTime.now(),
  fullStatus: null,
  isRead: false,
  isSaved: false,
  isFavorite: false,
  dupCount: dup,
  otherCopies: other,
);

Future<void> _show(WidgetTester tester, Article a, VoidCallback onTwins) =>
    tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(Brightness.light),
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: ArticleTile(
            article: a,
            sourceTitle: 'Xataka',
            onOpen: () {},
            onToggleRead: () {},
            onToggleSaved: () {},
            onTwins: onTwins,
          ),
        ),
      ),
    );

void main() {
  testWidgets('no chip when the story has no other copies', (tester) async {
    await _show(tester, _article(), () {});
    expect(find.byIcon(Icons.layers_outlined), findsNothing);
  });

  testWidgets('the chip counts copies in your feeds and elsewhere, and opens', (
    tester,
  ) async {
    var opened = 0;
    await _show(tester, _article(dup: 2, other: 3), () => opened++);
    expect(find.byIcon(Icons.layers_outlined), findsOneWidget);
    expect(find.text('4'), findsOneWidget); // 1 in your feeds + 3 elsewhere
    await tester.tap(find.byIcon(Icons.layers_outlined));
    expect(opened, 1);
  });

  testWidgets('copies only in feeds you do not follow still show the chip', (
    tester,
  ) async {
    await _show(tester, _article(other: 2), () {});
    expect(find.text('2'), findsOneWidget);
  });
}
