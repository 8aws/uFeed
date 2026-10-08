import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/listen/readable.dart';

void main() {
  test('reads blocks with pauses and skips code, captions and videos', () {
    const html = '''
<p>Primer párrafo con <a href="x">un enlace</a></p>
<figure><img src="a.jpg"><figcaption>Pie de foto</figcaption></figure>
<pre><code>print("hola")</code></pre>
<h2>Un título</h2>
<ul><li>Uno</li><li>Dos!</li></ul>
<p><a href="https://youtu.be/x" data-embed="youtube:dQw4w9WgXcQ">▶ YouTube</a></p>''';
    expect(
      readableText('Titular', html),
      'Titular. Primer párrafo con un enlace. Un título. Uno. Dos!',
    );
  });

  test('chunks long sentences at commas or spaces', () {
    final long = 'Palabra, ' * 60;
    final parts = chunks('Corta. $long');
    expect(parts.first, 'Corta.');
    expect(parts.every((p) => p.length <= 220), isTrue);
    expect(
      parts.join(' ').replaceAll(RegExp(r'\s+'), ' '),
      'Corta. ${long.trim()}',
    );
  });

  test('translation text adds stops', () {
    expect(translationText('Título', ['Uno', 'Dos.']), 'Título. Uno. Dos.');
  });
}
