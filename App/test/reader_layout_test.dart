import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/core/theme.dart';
import 'package:ufeed/features/reader/article_html.dart';

const _yt = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';

void main() {
  group('a video link inside a sentence', () {
    test('keeps its words and puts the card after the paragraph', () {
      final out = withEmbedCards(
        '<p>Ayer, durante la <a href="$_yt">rueda de prensa</a> que siguió al '
        'Consejo, habló.</p><p>Otro párrafo.</p>',
      );
      expect(out, contains('rueda de prensa'));
      expect(out, contains('data-link="1"'));
      final card = out.indexOf('data-embedcard="youtube:dQw4w9WgXcQ"');
      expect(card, greaterThan(out.indexOf('habló.')));
      expect(card, lessThan(out.indexOf('Otro párrafo')));
    });

    test('two videos in one paragraph keep their order, one card each', () {
      final out = withEmbedCards(
        '<p>Mira <a href="$_yt">esto</a> y <a href="https://youtu.be/aaaaaaaaaaa">'
        'aquello</a>.</p>',
      );
      expect(RegExp('data-embedcard').allMatches(out).length, 2);
      expect(
        out.indexOf('youtube:dQw4w9WgXcQ'),
        lessThan(out.indexOf('youtube:aaaaaaaaaaa')),
      );
    });

    test(
      'a link that is the whole paragraph, or has no words, is the card',
      () {
        const whole = '<p><a href="$_yt">Ver el vídeo</a></p>';
        expect(withEmbedCards(whole), whole);
        const thumb = '<p>Antes <a href="$_yt"><img src="x.jpg"></a></p>';
        expect(withEmbedCards(thumb), thumb);
      },
    );

    test(
      'the placeholders the server writes, and other links, are untouched',
      () {
        const placeholder =
            '<p><a href="$_yt" data-embed="youtube:dQw4w9WgXcQ">▶ YouTube</a></p>';
        expect(withEmbedCards(placeholder), placeholder);
        const plain = '<p>Lee <a href="https://example.com/a">esto</a>.</p>';
        expect(withEmbedCards(plain), plain);
      },
    );
  });

  group('tables', () {
    test('the sites own sizing goes, the content and its style stay', () {
      final out = tidyTables(
        '<table width="100%" style="width:100%;border:1px solid red">'
        '<colgroup><col width="5"></colgroup>'
        '<tr><th width="3%" nowrap style="word-break:break-all;color:#f00">MODELO</th>'
        '<td style="padding:0 60px"><span style="white-space:nowrap">x</span></td></tr></table>',
      );
      expect(out, isNot(contains('width')));
      expect(out, isNot(contains('colgroup')));
      expect(out, isNot(contains('nowrap')));
      expect(out, isNot(contains('word-break')));
      expect(out, isNot(contains('padding')));
      expect(out, contains('color:#f00'));
      expect(out, contains('border:1px solid red'));
      expect(out, contains('MODELO'));
      const noTable = '<p style="width:10px">hi</p>';
      expect(tidyTables(noTable), noTable);
    });

    Future<void> show(WidgetTester tester, String html, double width) async {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        MaterialApp(
          theme: buildTheme(Brightness.light),
          home: Scaffold(
            body: SingleChildScrollView(
              child: ArticleHtml(
                html: html,
                baseUrl: null,
                textStyle: const TextStyle(fontSize: 16),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    String table(int cols) =>
        '<table><tr>${[for (var i = 0; i < cols; i++) '<th>Modelo</th>'].join()}</tr>'
        '<tr>${[for (var i = 0; i < cols; i++) '<td>Precio</td>'].join()}</tr></table>';

    testWidgets('a table with many columns scrolls sideways, not squeezed', (
      tester,
    ) async {
      await show(tester, table(5), 360);
      final scroller = find.byWidgetPredicate(
        (w) =>
            w is SingleChildScrollView && w.scrollDirection == Axis.horizontal,
      );
      // The renderer's own scroller and ours, which gives every column room.
      expect(scroller, findsNWidgets(2));
      // Wide enough for every column to keep its words whole.
      expect(
        tester
            .getSize(find.textContaining('Modelo', findRichText: true).first)
            .height,
        lessThan(30),
      );
    });

    testWidgets('a table that fits is laid out as usual', (tester) async {
      await show(tester, table(2), 360);
      expect(
        find.byWidgetPredicate(
          (w) =>
              w is SingleChildScrollView &&
              w.scrollDirection == Axis.horizontal,
        ),
        findsOneWidget, // only the renderer's own
      );
      expect(
        find.textContaining('Modelo', findRichText: true).first,
        findsOneWidget,
      );
    });
  });
}
