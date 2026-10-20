import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../api/api_client.dart';
import '../../api/models.dart';
import '../../auth/session.dart';
import '../../core/config.dart';
import '../../core/dialogs.dart';
import '../../core/prefs.dart';
import '../../core/layout.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';
import '../../listen/listen_bar.dart';
import '../home/home_state.dart';
import '../reader/article_html.dart';

final keywordsProvider = FutureProvider.autoDispose<List<MutedKeyword>>(
  (ref) => ref.watch(apiProvider).keywords(),
);

String accountError(AppLocalizations t, ApiException e) => switch (e.code) {
  'wrong_password' => t.wrongPassword,
  'demo_account' => t.demoAccount,
  'last_admin' => t.lastAdmin,
  'guest_account' => t.guestNeedsAccount,
  'email_taken' => t.emailTaken,
  'registration_closed' => t.registrationClosed,
  'rate_limited' => t.tryLater,
  _ => t.somethingFailed,
};

String roleName(AppLocalizations t, Role r) => switch (r) {
  Role.guest => t.roleGuest,
  Role.free => t.roleFree,
  Role.general => t.roleGeneral,
  Role.vip => t.roleVip,
  Role.editor => t.roleEditor,
  Role.admin => t.roleAdmin,
};

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final user = ref.watch(sessionProvider).value;
    if (user == null) return const SizedBox.shrink();

    Widget section(String title, List<Widget> children) => Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
            child: Text(
              title.toUpperCase(),
              style: TextStyle(
                color: c.muted,
                fontSize: 12,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.5,
              ),
            ),
          ),
          Material(
            color: c.surface,
            child: Column(children: children),
          ),
        ],
      ),
    );

    final staff = user.role == Role.editor || user.role == Role.admin;
    return Scaffold(
      appBar: AppBar(title: Text(t.settings)),
      body: CenteredColumn(
        child: ListView(
          padding: const EdgeInsets.only(bottom: 40),
          children: [
            section(t.account, [
              if (user.isGuest) ...[
                ListTile(
                  leading: const Icon(Icons.person_outline),
                  title: Text(t.guestTitle),
                  subtitle: Text(t.guestBody),
                  isThreeLine: true,
                ),
                ListTile(
                  leading: Icon(Icons.person_add_alt, color: c.accent),
                  title: Text(
                    t.guestUpgrade,
                    style: TextStyle(
                      color: c.accent,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  onTap: () => _upgrade(context, ref),
                ),
                ListTile(
                  leading: const Icon(Icons.logout),
                  title: Text(t.guestLeave),
                  onTap: () => _leaveGuest(context, ref),
                ),
              ] else ...[
                ListTile(
                  leading: const Icon(Icons.person_outline),
                  title: Text(user.email),
                  subtitle: Text('${t.plan}: ${roleName(t, user.role)}'),
                ),
                ListTile(
                  leading: const Icon(Icons.key_outlined),
                  title: Text(t.changePassword),
                  onTap: () => _changePassword(context, ref),
                ),
                ListTile(
                  leading: const Icon(Icons.logout),
                  title: Text(t.logout),
                  onTap: () {
                    context.pop();
                    ref.read(sessionProvider.notifier).logout();
                  },
                ),
              ],
            ]),
            if (!user.isGuest)
              section(t.digestTitle, [_DigestSettings(user: user)]),
            section(t.voiceSettings, [
              ListTile(
                leading: const Icon(Icons.record_voice_over_outlined),
                title: Text(t.voiceSettings),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => showVoiceSheet(context),
              ),
              const _DisplaySettings(),
            ]),
            section(t.filters, const [_Filters()]),
            section(t.feeds, [
              ListTile(
                leading: const Icon(Icons.upload_file),
                title: Text(t.importOpml),
                onTap: () => _importOpml(context, ref),
              ),
              ListTile(
                leading: const Icon(Icons.ios_share),
                title: Text(t.exportOpml),
                onTap: () => _exportOpml(context, ref),
              ),
            ]),
            section('uFeed', [
              _link(context, Icons.public, t.web, '/'),
              if (staff) _link(context, Icons.tune, t.curation, '/curation'),
              // Administration is reached from the local network or VPN only,
              // so the app doesn't link to it (editors' curation stays).
              _link(
                context,
                Icons.workspace_premium_outlined,
                t.plansAndLimits,
                '/plans',
              ),
              _link(context, Icons.privacy_tip_outlined, t.privacy, '/privacy'),
              _link(context, Icons.help_outline, t.support, '/support'),
              const _VersionTile(),
            ]),
            if (!user.isGuest)
              section(t.deleteAccount, [
                ListTile(
                  leading: Icon(Icons.delete_forever, color: c.danger),
                  title: Text(
                    t.deleteAccount,
                    style: TextStyle(color: c.danger),
                  ),
                  subtitle: Text(t.deleteAccountHint),
                  onTap: () => _deleteAccount(context, ref),
                ),
              ]),
          ],
        ),
      ),
    );
  }

  Widget _link(
    BuildContext context,
    IconData icon,
    String label,
    String path,
  ) => ListTile(
    leading: Icon(icon),
    title: Text(label),
    trailing: const Icon(Icons.open_in_new, size: 18),
    onTap: () => openLink(Uri.parse('$serverUrl$path')),
  );

  Future<void> _changePassword(BuildContext context, WidgetRef ref) async {
    final t = AppLocalizations.of(context);
    final current = TextEditingController();
    final next = TextEditingController();
    final again = TextEditingController();
    String? error;
    await showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) {
          Future<void> save() async {
            if (next.text.length < 8) {
              return setState(() => error = t.passwordTooShort);
            }
            if (next.text != again.text) {
              return setState(() => error = t.passwordMismatch);
            }
            try {
              final tokens = await ref
                  .read(apiProvider)
                  .changePassword(current.text, next.text);
              await ref.read(tokenStoreProvider).save(tokens);
              if (context.mounted) {
                Navigator.of(context).pop();
                toast(context, t.passwordChanged);
              }
            } on ApiException catch (e) {
              setState(() => error = accountError(t, e));
            }
          }

          InputDecoration deco(String label) =>
              InputDecoration(labelText: label);
          return AlertDialog(
            title: Text(t.changePassword),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: current,
                  obscureText: true,
                  autofillHints: const [AutofillHints.password],
                  decoration: deco(t.currentPassword),
                ),
                TextField(
                  controller: next,
                  obscureText: true,
                  autofillHints: const [AutofillHints.newPassword],
                  decoration: deco(t.newPassword),
                ),
                TextField(
                  controller: again,
                  obscureText: true,
                  autofillHints: const [AutofillHints.newPassword],
                  decoration: deco(t.confirmPassword),
                ),
                if (error != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text(t.cancel),
              ),
              FilledButton(onPressed: save, child: Text(t.changePassword)),
            ],
          );
        },
      ),
    );
    current.dispose();
    next.dispose();
    again.dispose();
  }

  /// A guest registers: email and password, and the feeds stay.
  Future<void> _upgrade(BuildContext context, WidgetRef ref) async {
    final t = AppLocalizations.of(context);
    final email = TextEditingController();
    final password = TextEditingController();
    String? error;
    var busy = false;
    await showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) {
          Future<void> save() async {
            final mail = email.text.trim();
            if (!mail.contains('@')) return setState(() => error = t.email);
            if (password.text.length < 8) {
              return setState(() => error = t.passwordTooShort);
            }
            setState(() {
              busy = true;
              error = null;
            });
            try {
              await ref
                  .read(sessionProvider.notifier)
                  .upgrade(mail, password.text);
              if (context.mounted) {
                Navigator.of(context).pop();
                toast(context, t.accountCreated);
              }
            } on ApiException catch (e) {
              setState(() {
                busy = false;
                error = e.isUnreachable
                    ? t.serverUnavailable
                    : accountError(t, e);
              });
            }
          }

          return AlertDialog(
            title: Text(t.guestUpgrade),
            content: AutofillGroup(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    autofillHints: const [AutofillHints.email],
                    decoration: InputDecoration(labelText: t.email),
                  ),
                  TextField(
                    controller: password,
                    obscureText: true,
                    autofillHints: const [AutofillHints.newPassword],
                    decoration: InputDecoration(labelText: t.password),
                  ),
                  if (error != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text(t.cancel),
              ),
              FilledButton(
                onPressed: busy ? null : save,
                child: Text(t.register),
              ),
            ],
          );
        },
      ),
    );
    email.dispose();
    password.dispose();
  }

  /// A guest has no way back in, so leaving deletes the guest profile.
  Future<void> _leaveGuest(BuildContext context, WidgetRef ref) async {
    final t = AppLocalizations.of(context);
    final ok = await confirm(
      context,
      message: t.guestLeaveHint,
      action: t.guestLeave,
    );
    if (!ok) return;
    try {
      await ref.read(apiProvider).deleteAccount();
      if (context.mounted) context.pop();
      await ref.read(sessionProvider.notifier).logout();
    } on ApiException catch (e) {
      if (context.mounted) toast(context, accountError(t, e));
    }
  }

  /// Required by the App Store: delete the account from inside the app.
  Future<void> _deleteAccount(BuildContext context, WidgetRef ref) async {
    final t = AppLocalizations.of(context);
    final password = await promptText(
      context,
      title: t.deleteAccount,
      hint: t.password,
      obscure: true,
    );
    if (password == null || !context.mounted) return;
    final ok = await confirm(
      context,
      message: t.deleteAccountHint,
      action: t.deleteAccount,
    );
    if (!ok) return;
    try {
      await ref.read(apiProvider).deleteAccount(password);
      if (context.mounted) context.pop();
      await ref.read(sessionProvider.notifier).logout();
    } on ApiException catch (e) {
      if (context.mounted) {
        toast(context, accountError(t, e));
      }
    }
  }

  Future<void> _importOpml(BuildContext context, WidgetRef ref) async {
    final t = AppLocalizations.of(context);
    final picked = await FilePicker.pickFiles();
    if (picked.isEmpty) return;
    final file = picked.single;
    try {
      final bytes = await file.readAsBytes();
      final r = await ref.read(apiProvider).importOpml(bytes, file.name);
      await ref.read(sidebarProvider.notifier).reload();
      ref.invalidate(articleListProvider);
      if (context.mounted) {
        toast(context, t.opmlImported(r.imported, r.skipped));
      }
    } on ApiException catch (e) {
      if (context.mounted) {
        toast(
          context,
          e.code.startsWith('plan_limit')
              ? (ref.read(sessionProvider).value?.isGuest ?? false
                    ? t.planLimitFeedsGuest
                    : t.planLimitFeeds)
              : t.somethingFailed,
        );
      }
    }
  }

  Future<void> _exportOpml(BuildContext context, WidgetRef ref) async {
    final t = AppLocalizations.of(context);
    try {
      final xml = await ref.read(apiProvider).exportOpml();
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/ufeed.opml');
      await file.writeAsString(xml);
      await SharePlus.instance.share(
        ShareParams(files: [XFile(file.path, mimeType: 'text/xml')]),
      );
    } on ApiException {
      if (context.mounted) toast(context, t.somethingFailed);
    }
  }
}

/// Daily digest by email: hour and days (same as the web's Settings).
class _DigestSettings extends ConsumerStatefulWidget {
  const _DigestSettings({required this.user});

  final User user;

  @override
  ConsumerState<_DigestSettings> createState() => _DigestSettingsState();
}

class _DigestSettingsState extends ConsumerState<_DigestSettings> {
  late int? _hour = widget.user.digestHour;
  late int _days = widget.user.digestDays;

  static const _every = 127, _weekdays = 31, _weekends = 96;

  Future<void> _save({int? hour, bool clearHour = false, int? days}) async {
    final t = AppLocalizations.of(context);
    final before = (_hour, _days);
    setState(() {
      if (clearHour) {
        _hour = null;
      } else if (hour != null) {
        _hour = hour;
      }
      if (days != null) _days = days;
    });
    try {
      await ref.read(apiProvider).updateMe({
        if (clearHour || hour != null) 'digest_hour': _hour,
        if (days != null) 'digest_days': _days,
      });
    } on ApiException {
      setState(() {
        _hour = before.$1;
        _days = before.$2;
      });
      if (mounted) toast(context, t.somethingFailed);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final letters = t.digestDayLetters.split(',');
    final preset = switch (_days) {
      _every => 'every',
      _weekdays => 'weekdays',
      _weekends => 'weekends',
      _ => 'custom',
    };
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(t.digestHint, style: TextStyle(color: c.muted, fontSize: 13)),
          const SizedBox(height: 8),
          Row(
            children: [
              Text(t.digestAt),
              const SizedBox(width: 12),
              DropdownButton<int>(
                value: _hour ?? -1,
                items: [
                  DropdownMenuItem(value: -1, child: Text(t.digestOff)),
                  for (var h = 0; h < 24; h++)
                    DropdownMenuItem(
                      value: h,
                      child: Text('${h.toString().padLeft(2, '0')}:00'),
                    ),
                ],
                onChanged: (h) =>
                    h == -1 ? _save(clearHour: true) : _save(hour: h),
              ),
            ],
          ),
          if (_hour != null) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (key, label, days) in [
                  ('every', t.digestEveryDay, _every),
                  ('weekdays', t.digestWeekdays, _weekdays),
                  ('weekends', t.digestWeekends, _weekends),
                ])
                  ChoiceChip(
                    label: Text(label),
                    selected: preset == key,
                    onSelected: (_) => _save(days: days),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              children: [
                for (var i = 0; i < 7; i++)
                  FilterChip(
                    label: Text(letters.length == 7 ? letters[i] : '$i'),
                    selected: _days & (1 << i) != 0,
                    onSelected: (on) {
                      final next = on ? _days | (1 << i) : _days & ~(1 << i);
                      if (next != 0) _save(days: next);
                    },
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// Text size, font and the automatic full article.
class _DisplaySettings extends ConsumerWidget {
  const _DisplaySettings();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context);
    final p = ref.watch(displayPrefsProvider);
    final set = ref.read(displayPrefsProvider.notifier).update;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(t.appearance),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            showSelectedIcon: false,
            segments: [
              ButtonSegment(value: 'system', label: Text(t.themeSystem)),
              ButtonSegment(value: 'light', label: Text(t.themeLight)),
              ButtonSegment(value: 'dark', label: Text(t.themeDark)),
            ],
            selected: {p.theme},
            onSelectionChanged: (v) => set(p.copyWith(theme: v.first)),
          ),
          const SizedBox(height: 12),
          Text(t.textSize),
          const SizedBox(height: 8),
          SegmentedButton<double>(
            showSelectedIcon: false,
            segments: [
              for (final s in textScales)
                ButtonSegment(
                  value: s,
                  label: Text(
                    'A',
                    style: TextStyle(fontSize: 13 * s),
                    textScaler: TextScaler.noScaling,
                  ),
                ),
            ],
            selected: {p.textScale},
            onSelectionChanged: (v) => set(p.copyWith(textScale: v.first)),
          ),
          const SizedBox(height: 12),
          Text(t.font),
          const SizedBox(height: 8),
          SegmentedButton<bool>(
            showSelectedIcon: false,
            segments: [
              ButtonSegment(value: false, label: Text(t.fontSystem)),
              const ButtonSegment(
                value: true,
                label: Text(
                  'Atkinson',
                  style: TextStyle(fontFamily: 'Atkinson Hyperlegible'),
                ),
              ),
            ],
            selected: {p.atkinson},
            onSelectionChanged: (v) => set(p.copyWith(atkinson: v.first)),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(t.autoFull),
            value: p.autoFull,
            onChanged: (v) => set(p.copyWith(autoFull: v)),
          ),
        ],
      ),
    );
  }
}

/// Muted words and muted feeds.
class _Filters extends ConsumerStatefulWidget {
  const _Filters();

  @override
  ConsumerState<_Filters> createState() => _FiltersState();
}

class _FiltersState extends ConsumerState<_Filters> {
  final _word = TextEditingController();

  @override
  void dispose() {
    _word.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    try {
      await action();
      ref.invalidate(keywordsProvider);
      ref.invalidate(articleListProvider);
    } on ApiException {
      if (mounted) toast(context, AppLocalizations.of(context).somethingFailed);
    }
  }

  Future<void> _add() async {
    final w = _word.text.trim();
    if (w.isEmpty) return;
    _word.clear();
    await _run(() => ref.read(apiProvider).addKeyword(w));
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final words = ref.watch(keywordsProvider).value ?? const <MutedKeyword>[];
    final muted = [
      for (final s
          in ref.watch(sidebarProvider).value?.subs ?? const <Subscription>[])
        if (s.muted) s,
    ];
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(t.filtersHint, style: TextStyle(color: c.muted, fontSize: 13)),
          TextField(
            controller: _word,
            maxLength: 100,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _add(),
            decoration: InputDecoration(
              hintText: t.addKeyword,
              counterText: '',
              suffixIcon: IconButton(
                tooltip: t.addKeyword,
                icon: const Icon(Icons.add),
                onPressed: _add,
              ),
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final k in words)
                InputChip(
                  label: Text(k.keyword),
                  onDeleted: () =>
                      _run(() => ref.read(apiProvider).removeKeyword(k.id)),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            t.mutedSources,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          Text(
            t.mutedSourcesHint,
            style: TextStyle(color: c.muted, fontSize: 13),
          ),
          if (muted.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(t.noMuted, style: TextStyle(color: c.muted)),
            ),
          for (final s in muted)
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              leading: const Icon(Icons.volume_off_outlined),
              title: Text(s.title),
              trailing: TextButton(
                onPressed: () => _run(() async {
                  await ref.read(apiProvider).updateSubscription(s.id, {
                    'muted': false,
                  });
                  await ref.read(sidebarProvider.notifier).reload();
                }),
                child: Text(t.unmute),
              ),
            ),
        ],
      ),
    );
  }
}

/// "uFeed 1.1.0 (5)": which build is installed, for support.
class _VersionTile extends StatelessWidget {
  const _VersionTile();

  @override
  Widget build(BuildContext context) => FutureBuilder<PackageInfo>(
    future: PackageInfo.fromPlatform(),
    builder: (context, snap) {
      final i = snap.data;
      return ListTile(
        dense: true,
        leading: const Icon(Icons.info_outline),
        title: Text(
          i == null ? 'uFeed' : 'uFeed ${i.version} (${i.buildNumber})',
          style: TextStyle(color: context.colors.muted),
        ),
      );
    },
  );
}
