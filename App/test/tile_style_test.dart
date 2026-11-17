import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/core/theme.dart';
import 'package:ufeed/features/home/article_tile.dart';
import 'package:ufeed/l10n/app_localizations.dart';

const _article = Article(
  id: 'a',
  sourceId: 's',
  url: null,
  title: 'Same story',
  author: null,
  summary: 'A long summary of the story',
  aiSummary: null,
  contentHtml: null,
  imageUrl: null,
  lang: 'es',
  wordCount: null,
  publishedAt: null,
  fullStatus: null,
  isRead: false,
  isSaved: false,
  isFavorite: false,
  dupCount: 1,
  otherCopies: 0,
);

void main() {
  testWidgets('the mosaic tile keeps the title and drops the summary', (
    tester,
  ) async {
    Future<void> show(ListStyle style) => tester.pumpWidget(
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
            article: _article,
            style: style,
            sourceTitle: 'Xataka',
            onOpen: () {},
            onToggleRead: () {},
            onToggleSaved: () {},
            onTwins: () {},
          ),
        ),
      ),
    );
    await show(ListStyle.masonry);
    expect(find.text('Same story'), findsOneWidget);
    expect(find.text('A long summary of the story'), findsNothing);
    await show(ListStyle.cards);
    expect(find.text('A long summary of the story'), findsOneWidget);
  });
}
