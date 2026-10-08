import 'package:html/dom.dart' as dom;
import 'package:html/parser.dart' as html_parser;

/// Text worth reading from an article's HTML (same rules as the web's
/// readableText): no code, captions, tables, media or video cards; each block
/// ends with a pause.
String readableText(String title, String? html) {
  final body = html == null ? '' : _blocks(html).map(_withStop).join(' ');
  final head = title.trim();
  if (head.isEmpty) return body;
  return body.isEmpty ? _withStop(head) : '${_withStop(head)} $body';
}

/// Text to read from a translation (title + paragraphs).
String translationText(String? title, List<String> paragraphs) {
  final body = paragraphs.where((p) => p.trim().isNotEmpty).map(_withStop);
  return [
    if (title != null && title.trim().isNotEmpty) _withStop(title),
    ...body,
  ].join(' ');
}

String _withStop(String s) {
  final t = s.trim();
  return RegExp(r'[.!?…:;]$').hasMatch(t) ? t : '$t.';
}

const _skip = {
  'pre',
  'code',
  'figcaption',
  'table',
  'audio',
  'video',
  'iframe',
  'script',
  'style',
  'object',
  'embed',
  'form',
};
const _block = {
  'p',
  'li',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'blockquote',
  'div',
  'dd',
  'dt',
  'section',
  'article',
  'figure',
};

List<String> _blocks(String html) {
  final doc = html_parser.parseFragment(html);
  final out = <String>[];
  final buf = StringBuffer();
  void flush() {
    final t = buf.toString().replaceAll(RegExp(r'\s+'), ' ').trim();
    if (t.isNotEmpty) out.add(t);
    buf.clear();
  }

  void walk(dom.Node n) {
    if (n is dom.Text) {
      buf.write(n.text);
      return;
    }
    if (n is! dom.Element) {
      for (final c in n.nodes) {
        walk(c);
      }
      return;
    }
    final tag = n.localName ?? '';
    if (_skip.contains(tag) || n.attributes.containsKey('data-embed')) return;
    if (tag == 'br') {
      flush();
      return;
    }
    final block = _block.contains(tag);
    if (block) flush();
    for (final c in n.nodes) {
      walk(c);
    }
    if (block) flush();
  }

  walk(doc);
  flush();
  return out;
}

/// Sentence-sized pieces of at most [max] characters, for the device voice
/// (pause/resume and speed changes restart at the current sentence).
List<String> chunks(String text, {int max = 220}) {
  final out = <String>[];
  for (final sentence in text.split(RegExp(r'(?<=[.!?…;:])\s+'))) {
    var s = sentence.trim();
    while (s.length > max) {
      final comma = s.lastIndexOf(', ', max);
      final space = s.lastIndexOf(' ', max);
      final cut = comma > space ? comma : space;
      final at = cut > 40 ? cut + 1 : max;
      out.add(s.substring(0, at).trim());
      s = s.substring(at).trim();
    }
    if (s.isNotEmpty) out.add(s);
  }
  return out;
}
