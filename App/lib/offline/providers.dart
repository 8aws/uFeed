import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import '../core/prefs.dart';
import 'local_store.dart';
import 'outbox.dart';

final outboxProvider = Provider<Outbox>((ref) {
  final box = Outbox(ref.watch(prefsProvider), ref.watch(apiProvider));
  ref.onDispose(box.pending.close);
  return box;
});

final localStoreProvider = Provider<LocalStore>((ref) => LocalStore());

/// Saved articles kept for offline reading, by id.
class OfflineSavedNotifier extends Notifier<Map<String, OfflineArticle>> {
  @override
  Map<String, OfflineArticle> build() => const {};

  void set(List<OfflineArticle> items) =>
      state = {for (final i in items) i.article.id: i};
}

final offlineSavedProvider =
    NotifierProvider<OfflineSavedNotifier, Map<String, OfflineArticle>>(
      OfflineSavedNotifier.new,
    );

/// Bumped when something is saved/unsaved, so the offline copy follows.
class SavedChangesNotifier extends Notifier<int> {
  @override
  int build() => 0;

  void bump() => state++;
}

final savedChangesProvider = NotifierProvider<SavedChangesNotifier, int>(
  SavedChangesNotifier.new,
);
