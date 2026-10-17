import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'reader_screen.dart';

/// The article open in the right-hand pane when the list and the article go
/// side by side (see `useTwoPane`): what it was opened with, and which one of
/// those is showing now (swiping the reader moves it, the list highlights it).
class OpenArticle {
  const OpenArticle(this.args, this.currentId);

  final ReaderArgs args;
  final String currentId;
}

final openArticleProvider = NotifierProvider<OpenArticleNotifier, OpenArticle?>(
  OpenArticleNotifier.new,
);

class OpenArticleNotifier extends Notifier<OpenArticle?> {
  @override
  OpenArticle? build() => null;

  void open(ReaderArgs args) =>
      state = OpenArticle(args, args.articles[args.index].id);

  /// The reader moved to another page of the same list.
  void follow(String id) {
    final o = state;
    if (o != null && o.currentId != id) state = OpenArticle(o.args, id);
  }

  void close() => state = null;
}
