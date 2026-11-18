import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:workmanager/workmanager.dart';

import '../api/api_client.dart';
import '../api/token_store.dart';
import '../core/config.dart';

/// Name of the periodic check: also the iOS background task identifier (it is
/// listed in Info.plist and registered in AppDelegate).
const notifyTask = 'es.uverse.ufeed.notify';

const _kEnabled = 'ufeed_notify';
const _kMin = 'ufeed_notify_min';
const _kBase = 'ufeed_notify_base';
const _kLanguage = 'ufeed_language';

/// What to do about the unread total found by a check.
class NotifyDecision {
  const NotifyDecision({
    required this.show,
    required this.count,
    required this.baseline,
  });

  /// Tell the person.
  final bool show;

  /// How many new articles since the last time they were told or looked.
  final int count;

  /// The total to remember for next time.
  final int baseline;
}

/// `baseline` is the unread total the person last saw (or was told about).
/// Fewer than `min` new articles wait quietly and add up; reading lowers the
/// baseline so only what arrives afterwards counts.
NotifyDecision decideNotification({
  required int total,
  required int baseline,
  required int min,
}) {
  if (total <= baseline) {
    return NotifyDecision(show: false, count: 0, baseline: total);
  }
  final count = total - baseline;
  return count >= min
      ? NotifyDecision(show: true, count: count, baseline: total)
      : NotifyDecision(show: false, count: count, baseline: baseline);
}

/// The text of the notification (the background isolate has no localisations).
({String title, String body}) notificationText(String lang, int count) =>
    lang == 'es'
    ? (
        title: 'uFeed',
        body: count == 1 ? '1 artículo nuevo' : '$count artículos nuevos',
      )
    : (
        title: 'uFeed',
        body: count == 1 ? '1 new article' : '$count new articles',
      );

/// The check, with what it needs passed in (so it can be tested): reads the
/// unread total and, if enough is new, shows a notification.
Future<bool> checkForNew({
  required SharedPreferences prefs,
  required Future<int?> Function() totalUnread,
  required Future<void> Function(String title, String body, int badge) show,
  String Function()? language,
}) async {
  if (!(prefs.getBool(_kEnabled) ?? false)) return false;
  final total = await totalUnread();
  if (total == null) return false; // not signed in, or no connection
  final baseline = prefs.getInt(_kBase) ?? total;
  final d = decideNotification(
    total: total,
    baseline: baseline,
    min: prefs.getInt(_kMin) ?? 1,
  );
  if (d.show) {
    final text = notificationText(language?.call() ?? 'en', d.count);
    await show(text.title, text.body, total);
  }
  await prefs.setInt(_kBase, d.baseline);
  return d.show;
}

final _plugin = FlutterLocalNotificationsPlugin();

Future<void> _initPlugin() => _plugin.initialize(
  settings: const InitializationSettings(
    iOS: DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    ),
  ),
);

Future<void> _showNow(String title, String body, int badge) async {
  await _initPlugin();
  await _plugin.show(
    id: 1,
    title: title,
    body: body,
    notificationDetails: NotificationDetails(
      iOS: DarwinNotificationDetails(
        badgeNumber: badge,
        threadIdentifier: 'new-articles',
      ),
    ),
  );
}

/// Runs in the background isolate that the system starts now and then.
@pragma('vm:entry-point')
void notifyDispatcher() {
  Workmanager().executeTask((task, input) async {
    WidgetsFlutterBinding.ensureInitialized();
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_kLanguage);
    final lang = saved == 'es' || saved == 'en'
        ? saved!
        : (WidgetsBinding.instance.platformDispatcher.locale.languageCode ==
                  'es'
              ? 'es'
              : 'en');
    final api = ApiClient(
      baseUrl: apiBase,
      tokens: SecureTokenStore(),
      locale: () => lang,
    );
    await checkForNew(
      prefs: prefs,
      language: () => lang,
      totalUnread: () async {
        if (await SecureTokenStore().read() == null) return null;
        try {
          return (await api.unreadCounts()).total;
        } on ApiException {
          return null;
        }
      },
      show: _showNow,
    );
    return true;
  });
}

bool get _supported => Platform.isIOS || Platform.isAndroid;

/// Start-up: let the system know who runs the checks.
Future<void> initNotifications() async {
  if (!_supported) return;
  await Workmanager().initialize(notifyDispatcher);
}

/// Turn the notifications on: asks for permission first. False if refused.
Future<bool> enableNotifications(SharedPreferences prefs, {int min = 1}) async {
  if (!_supported) return false;
  await _initPlugin();
  final ios = _plugin
      .resolvePlatformSpecificImplementation<
        IOSFlutterLocalNotificationsPlugin
      >();
  final granted =
      await ios?.requestPermissions(alert: true, badge: true, sound: false) ??
      true;
  if (!granted) return false;
  await prefs.setBool(_kEnabled, true);
  await prefs.setInt(_kMin, min);
  await Workmanager().registerPeriodicTask(
    notifyTask,
    notifyTask,
    frequency: const Duration(hours: 1),
    existingWorkPolicy: ExistingPeriodicWorkPolicy.update,
  );
  return true;
}

Future<void> disableNotifications(SharedPreferences prefs) async {
  await prefs.setBool(_kEnabled, false);
  if (_supported) await Workmanager().cancelByUniqueName(notifyTask);
}

Future<void> setNotifyMin(SharedPreferences prefs, int min) =>
    prefs.setInt(_kMin, min);

/// What the person is looking at now: nothing counts as new until it grows.
Future<void> markSeen(SharedPreferences prefs, int total) async {
  if (prefs.getBool(_kEnabled) ?? false) await prefs.setInt(_kBase, total);
}

bool notificationsOn(SharedPreferences prefs) =>
    prefs.getBool(_kEnabled) ?? false;

int notifyMin(SharedPreferences prefs) => prefs.getInt(_kMin) ?? 1;
