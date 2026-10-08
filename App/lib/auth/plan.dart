import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/models.dart';
import '../core/prefs.dart';
import 'session.dart';

/// What the signed-in account's plan allows; the last known limits are kept
/// so the app behaves the same without network.
final planProvider = FutureProvider<PlanLimits>((ref) async {
  final user = ref.watch(sessionProvider).value;
  final prefs = ref.read(prefsProvider);
  const key = 'ufeed_plan';
  if (user == null) return const PlanLimits();
  try {
    final site = await ref.read(apiProvider).site();
    final limits = site.planLimits[user.role] ?? const PlanLimits();
    await prefs.setString(key, jsonEncode(limits.toJson()));
    return limits;
  } on Object {
    final raw = prefs.getString(key);
    return raw == null
        ? const PlanLimits()
        : PlanLimits.fromJson(jsonDecode(raw) as Json);
  }
});
