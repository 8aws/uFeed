import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/features/reader/article_html.dart';

void main() {
  test('safeUri keeps only http(s) and resolves relative links', () {
    final base = Uri.parse('https://example.com/blog/post');
    expect(safeUri('javascript:alert(1)'), isNull);
    expect(safeUri('data:text/html,hi'), isNull);
    expect(
      safeUri('/img/a.png', base).toString(),
      'https://example.com/img/a.png',
    );
    expect(safeUri('https://x.org/a').toString(), 'https://x.org/a');
    expect(safeUri(''), isNull);
  });

  test('embedOf finds YouTube and Vimeo videos', () {
    expect(embedOf(null, 'youtube:dQw4w9WgXcQ'), (
      provider: 'youtube',
      id: 'dQw4w9WgXcQ',
    ));
    expect(
      embedOf('https://www.youtube.com/watch?v=dQw4w9WgXcQ', null)?.id,
      'dQw4w9WgXcQ',
    );
    expect(embedOf('https://youtu.be/dQw4w9WgXcQ', null)?.id, 'dQw4w9WgXcQ');
    expect(embedOf('https://vimeo.com/123456', null), (
      provider: 'vimeo',
      id: '123456',
    ));
    expect(embedOf('https://example.com/watch?v=dQw4w9WgXcQ', null), isNull);
    expect(embedOf(null, 'youtube:bad'), isNull);
  });
}
