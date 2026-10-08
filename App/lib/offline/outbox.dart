import 'dart:async';
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../api/models.dart';

// Offline outbox, the same as the web app's (Frontend/src/lib/outbox.ts).
//
// Changes are applied to the screen at once and sent to the server; if the
// network is down (or the server hiccups) they are kept here and sent later:
// when the connection comes back or the app returns to the foreground.
//
// - Article state (read / saved / favorite): only the latest value per
//   article and field is kept, so toggling offline sends one request or none.
// - Operations (mark all read, reading stats, open/share): kept in order,
//   each with the moment it happened, which the server uses (a late "mark
//   all" doesn't swallow newer posts; late stats don't inflate Trending).
// Both are sent together in chronological order.

enum Field { read, saved, favorite }

class StateChange {
  const StateChange(this.id, this.field, this.value, this.at);

  final String id;
  final Field field;
  final bool value;
  final DateTime at;

  String get key => '$id:${field.name}';

  Map<String, Object?> toJson() => {
    'id': id,
    'field': field.name,
    'value': value,
    'at': at.millisecondsSinceEpoch,
  };

  factory StateChange.fromJson(Map<String, dynamic> j) => StateChange(
    j['id'] as String,
    Field.values.byName(j['field'] as String),
    j['value'] as bool,
    DateTime.fromMillisecondsSinceEpoch(j['at'] as int),
  );
}

/// mark all read | read event | open/share.
sealed class Op {
  const Op(this.at);

  final DateTime at;

  Map<String, Object?> toJson();

  static Op fromJson(Map<String, dynamic> j) {
    final at = DateTime.fromMillisecondsSinceEpoch(j['at'] as int);
    return switch (j['type']) {
      'markAll' => MarkAll(
        at,
        folderId: j['folder_id'] as String?,
        sourceId: j['source_id'] as String?,
      ),
      'readEvent' => ReadEvent(
        at,
        j['id'] as String,
        Duration(milliseconds: j['dwell_ms'] as int),
        (j['completion'] as num).toDouble(),
      ),
      _ => Engage(at, j['id'] as String, j['kind'] as String),
    };
  }
}

class MarkAll extends Op {
  const MarkAll(super.at, {this.folderId, this.sourceId});

  final String? folderId;
  final String? sourceId;

  @override
  Map<String, Object?> toJson() => {
    'type': 'markAll',
    'at': at.millisecondsSinceEpoch,
    'folder_id': folderId,
    'source_id': sourceId,
  };
}

class ReadEvent extends Op {
  const ReadEvent(super.at, this.id, this.dwell, this.completion);

  final String id;
  final Duration dwell;
  final double completion;

  @override
  Map<String, Object?> toJson() => {
    'type': 'readEvent',
    'at': at.millisecondsSinceEpoch,
    'id': id,
    'dwell_ms': dwell.inMilliseconds,
    'completion': completion,
  };
}

class Engage extends Op {
  const Engage(super.at, this.id, this.kind);

  final String id;
  final String kind; // open | share | skip

  @override
  Map<String, Object?> toJson() => {
    'type': 'engage',
    'at': at.millisecondsSinceEpoch,
    'id': id,
    'kind': kind,
  };
}

enum Sent { sent, queued, dropped }

class Outbox {
  Outbox(this._prefs, this._api, {DateTime Function()? now})
    : _now = now ?? DateTime.now;

  final SharedPreferences _prefs;
  final ApiClient _api;
  final DateTime Function() _now;

  static const _statesKey = 'ufeed_outbox';
  static const _opsKey = 'ufeed_outbox_ops';
  static const maxAge = Duration(days: 30); // older changes are dropped
  static const maxOps = 300; // stats beyond this are dropped oldest-first

  /// How many changes are waiting (for a small indicator).
  final pending = StreamController<int>.broadcast();

  Map<String, StateChange> _states() {
    final raw = _prefs.getString(_statesKey);
    if (raw == null) return {};
    final m = jsonDecode(raw) as Map<String, dynamic>;
    return {
      for (final e in m.entries)
        e.key: StateChange.fromJson(e.value as Map<String, dynamic>),
    };
  }

  List<Op> _ops() {
    final raw = _prefs.getString(_opsKey);
    if (raw == null) return [];
    return [
      for (final e in jsonDecode(raw) as List)
        Op.fromJson(e as Map<String, dynamic>),
    ];
  }

  Future<void> _saveStates(Map<String, StateChange> q) async {
    if (q.isEmpty) {
      await _prefs.remove(_statesKey);
    } else {
      await _prefs.setString(
        _statesKey,
        jsonEncode({for (final e in q.entries) e.key: e.value.toJson()}),
      );
    }
    pending.add(count);
  }

  Future<void> _saveOps(List<Op> ops) async {
    if (ops.isEmpty) {
      await _prefs.remove(_opsKey);
    } else {
      await _prefs.setString(
        _opsKey,
        jsonEncode([for (final o in ops) o.toJson()]),
      );
    }
    pending.add(count);
  }

  int get count => _states().length + _ops().length;

  /// Worth retrying later: no network, rate limit or server error. Anything
  /// else (e.g. 404: the article was purged) will never succeed.
  static bool retriable(Object e) =>
      e is! ApiException || e.isNetwork || e.status == 429 || e.status >= 500;

  Future<void> _sendState(StateChange c) => switch (c.field) {
    Field.read => _api.setRead(c.id, c.value),
    Field.saved => _api.setSaved(c.id, c.value),
    Field.favorite => _api.setFavorite(c.id, c.value),
  };

  /// `late`: sent from the queue, so it carries the moment it happened; sent
  /// right away it doesn't, and the server's clock applies.
  Future<void> _sendOp(Op o, {required bool late}) {
    final at = late ? o.at : null;
    return switch (o) {
      MarkAll() => _api.markAllRead(
        folderId: o.folderId,
        sourceId: o.sourceId,
        before: o.at,
      ),
      ReadEvent() => _api.readEvent(o.id, o.dwell, o.completion, at: at),
      Engage() => _api.engage(o.id, o.kind, at: at),
    };
  }

  /// Send a state change now, or queue it if that isn't possible right now.
  /// Throws only for permanent failures (the caller may undo the change).
  Future<Sent> setState(String id, Field field, bool value) async {
    final change = StateChange(id, field, value, _now());
    final q = _states()..remove(change.key); // a newer value supersedes
    await _saveStates(q);
    // With an older operation queued (e.g. an offline "mark all read"),
    // sending this now would apply it out of order: queue it behind.
    if (_ops().isEmpty) {
      try {
        await _sendState(change);
        return Sent.sent;
      } catch (e) {
        if (!retriable(e)) rethrow;
      }
    }
    await _saveStates(_states()..[change.key] = change);
    return Sent.queued;
  }

  /// Send an operation now, or queue it. Permanent failures are dropped.
  Future<Sent> run(Op op) async {
    final behind = _ops().isNotEmpty || _states().isNotEmpty;
    if (!behind) {
      try {
        await _sendOp(op, late: false);
        return Sent.sent;
      } catch (e) {
        if (!retriable(e)) return Sent.dropped;
      }
    }
    var ops = [..._ops(), op];
    if (ops.length > maxOps) {
      // Drop the oldest stats first; "mark all read" is worth keeping.
      var extra = ops.length - maxOps;
      ops = [
        for (final o in ops)
          if (o is MarkAll || extra-- <= 0) o,
      ];
    }
    await _saveOps(ops);
    return Sent.queued;
  }

  Future<int>? _flushing;

  /// Send everything queued, oldest first. Stops at the first failure worth
  /// retrying (the network is probably still down). Returns how many changes
  /// reached the server.
  Future<int> flush() => _flushing ??= () async {
    var sent = 0;
    try {
      final items = <(DateTime, Object)>[
        for (final s in _states().values) (s.at, s),
        for (final o in _ops()) (o.at, o),
      ]..sort((a, b) => a.$1.compareTo(b.$1));
      for (final (at, item) in items) {
        final expired = _now().difference(at) > maxAge;
        try {
          if (!expired) {
            await (item is StateChange
                ? _sendState(item)
                : _sendOp(item as Op, late: true));
            sent++;
          }
        } catch (e) {
          if (retriable(e)) break;
        }
        if (item is StateChange) {
          await _dropState(item);
        } else {
          await _dropOp(item as Op);
        }
      }
    } finally {
      _flushing = null;
    }
    return sent;
  }();

  Future<void> _dropState(StateChange c) async {
    final q = _states();
    // Only if it wasn't replaced by a newer change meanwhile.
    if (q[c.key]?.at == c.at) await _saveStates(q..remove(c.key));
  }

  Future<void> _dropOp(Op o) async {
    final ops = _ops();
    final i = ops.indexWhere(
      (x) => x.at == o.at && x.runtimeType == o.runtimeType,
    );
    if (i >= 0) await _saveOps(ops..removeAt(i));
  }

  /// Overlay queued changes on articles from the server, so a post read
  /// offline doesn't come back as unread before the change is synced.
  /// `folderOf`: source -> folder, for folder-wide "mark all read".
  List<Article> applyPending(
    List<Article> items, {
    String? Function(String sourceId)? folderOf,
  }) {
    final q = _states();
    final marks = _ops().whereType<MarkAll>().toList();
    if (q.isEmpty && marks.isEmpty) return items;
    return [for (final a in items) _overlay(a, q, marks, folderOf)];
  }

  Article _overlay(
    Article a,
    Map<String, StateChange> q,
    List<MarkAll> marks,
    String? Function(String)? folderOf,
  ) {
    // A queued "mark all read" covers what had arrived when it was pressed
    // (individual changes made after it still win, below).
    final arrived = a.fetchedAt ?? a.publishedAt;
    DateTime? markedAt;
    for (final m in marks) {
      if (arrived != null && arrived.isAfter(m.at)) continue;
      if (m.sourceId != null && a.sourceId != m.sourceId) continue;
      if (m.folderId != null &&
          m.sourceId == null &&
          folderOf?.call(a.sourceId) != m.folderId) {
        continue;
      }
      if (markedAt == null || m.at.isAfter(markedAt)) markedAt = m.at;
    }
    var read = markedAt != null ? true : a.isRead;
    final r = q['${a.id}:read'];
    final s = q['${a.id}:saved'];
    final f = q['${a.id}:favorite'];
    if (r != null && (markedAt == null || r.at.isAfter(markedAt))) {
      read = r.value;
    }
    return a.copyWith(isRead: read, isSaved: s?.value, isFavorite: f?.value);
  }

  /// On sign out: what's queued belongs to that account.
  Future<void> clear() async {
    await _prefs.remove(_statesKey);
    await _prefs.remove(_opsKey);
    pending.add(0);
  }
}
