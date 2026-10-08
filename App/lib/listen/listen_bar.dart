import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/models.dart';
import '../auth/plan.dart';
import '../core/prefs.dart';
import '../core/theme.dart';
import '../l10n/app_localizations.dart';
import 'listen_controller.dart';

String _clock(Duration d) {
  final m = d.inMinutes;
  final s = (d.inSeconds % 60).toString().padLeft(2, '0');
  return '$m:$s';
}

String _errorText(AppLocalizations t, String code) => switch (code) {
  'plan_limit_tts' => t.listenPlan,
  'rate_limited' => t.listenRateLimited,
  'tts_lang' => t.listenLangUnsupported,
  'network' => t.offline,
  _ => t.listenUnavailable,
};

/// The reader's listen bar: "Listen" and Post radio when nothing of this
/// article is playing; the player controls when it is.
class ListenBar extends ConsumerWidget {
  const ListenBar({
    super.key,
    required this.article,
    required this.source,
    required this.list,
    required this.index,
    required this.sourceOf,
  });

  final Article article;
  final String source;

  /// The list the reader was opened from, for Post radio.
  final List<Article> list;
  final int index;
  final String Function(Article) sourceOf;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final s = ref.watch(listenProvider);
    final ctrl = ref.read(listenProvider.notifier);
    final plan = ref.watch(planProvider).value;

    if (!s.isFor(article) || !(s.active || s.status == ListenStatus.ended)) {
      return Row(
        children: [
          OutlinedButton.icon(
            onPressed: () => ctrl.start(article, source: source),
            icon: const Icon(Icons.headphones),
            label: Text(t.listen),
          ),
          if (plan?.postRadio ?? false) ...[
            const SizedBox(width: 8),
            IconButton(
              tooltip: t.postRadioStart,
              icon: const Icon(Icons.radio),
              onPressed: () => ctrl.startRadio(list, index, sourceOf: sourceOf),
            ),
          ],
          const Spacer(),
          IconButton(
            tooltip: t.voiceSettings,
            icon: const Icon(Icons.tune),
            onPressed: () => showVoiceSheet(context),
          ),
          if (s.isFor(article) && s.error != null)
            Flexible(
              child: Text(
                _errorText(t, s.error!),
                style: TextStyle(color: c.danger, fontSize: 12),
              ),
            ),
        ],
      );
    }
    return PlayerControls(state: s);
  }
}

/// Play/pause, ±15 s (or ±1 sentence), speed and where we are.
class PlayerControls extends ConsumerWidget {
  const PlayerControls({super.key, required this.state, this.compact = false});

  final ListenState state;
  final bool compact;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final s = state;
    final ctrl = ref.read(listenProvider.notifier);
    final device = s.engine == Engine.device;
    final where = switch (s.engine) {
      Engine.device when s.parts > 0 => t.sentence(s.part + 1, s.parts),
      Engine.server || Engine.live =>
        '${_clock(s.position)} / '
            '${s.duration == null ? t.listenGenerating : _clock(s.duration!)}',
      _ => s.status == ListenStatus.preparing ? t.listenPreparing : '',
    };
    final radio = s.radio;

    return Row(
      children: [
        if (!compact)
          IconButton(
            tooltip: t.back15,
            icon: Icon(device ? Icons.skip_previous : Icons.replay_10),
            onPressed: () => ctrl.seekBy(const Duration(seconds: -15)),
          ),
        IconButton.filled(
          tooltip: s.playing ? t.pause : t.play,
          onPressed: s.status == ListenStatus.preparing ? null : ctrl.toggle,
          icon: s.status == ListenStatus.preparing
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Icon(s.playing ? Icons.pause : Icons.play_arrow),
        ),
        if (!compact)
          IconButton(
            tooltip: t.forward15,
            icon: Icon(device ? Icons.skip_next : Icons.forward_10),
            onPressed: () => ctrl.seekBy(const Duration(seconds: 15)),
          ),
        const SizedBox(width: 4),
        Expanded(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (compact || radio != null)
                Text(
                  radio != null
                      ? '📻 ${t.radioPosition(radio.pos + 1, radio.total)}'
                      : (s.article?.title ?? ''),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              Text(
                where,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: c.muted,
                  fontSize: 12.5,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
        ),
        PopupMenuButton<double>(
          tooltip: t.listenSpeed,
          initialValue: s.rate,
          onSelected: ctrl.setRate,
          itemBuilder: (_) => [
            for (final r in SpeechPrefs.rates)
              CheckedPopupMenuItem(
                value: r,
                checked: r == s.rate,
                child: Text('${r}x'),
              ),
          ],
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Text(
              '${s.rate}x',
              style: TextStyle(color: c.accent, fontWeight: FontWeight.w600),
            ),
          ),
        ),
        if (radio != null)
          IconButton(
            tooltip: t.radioNext,
            icon: const Icon(Icons.skip_next),
            onPressed: ctrl.next,
          ),
        IconButton(
          tooltip: radio != null ? t.radioStop : t.stop,
          icon: const Icon(Icons.stop),
          onPressed: ctrl.stop,
        ),
      ],
    );
  }
}

/// Below the article list while something plays (the audio keeps going
/// while browsing); tapping it opens that article.
class MiniPlayer extends ConsumerWidget {
  const MiniPlayer({super.key, required this.onOpen});

  final void Function(Article) onOpen;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final s = ref.watch(listenProvider);
    if (!s.active || s.article == null) return const SizedBox.shrink();
    return Material(
      color: c.surface,
      child: InkWell(
        onTap: () => onOpen(s.article!),
        child: Container(
          decoration: BoxDecoration(
            border: Border(top: BorderSide(color: c.border)),
          ),
          padding: const EdgeInsets.fromLTRB(12, 4, 4, 4),
          child: SafeArea(
            top: false,
            child: PlayerControls(state: s, compact: true),
          ),
        ),
      ),
    );
  }
}

/// Voice and reading options (the app has no Settings screen yet).
Future<void> showVoiceSheet(BuildContext context) => showModalBottomSheet<void>(
  context: context,
  showDragHandle: true,
  isScrollControlled: true,
  builder: (context) => Consumer(
    builder: (context, ref, _) {
      final t = AppLocalizations.of(context);
      final c = context.colors;
      final p = ref.watch(speechPrefsProvider);
      final plan = ref.watch(planProvider).value ?? const PlanLimits();
      final set = ref.read(speechPrefsProvider.notifier).update;
      Widget hint(String text) => Padding(
        padding: const EdgeInsets.only(top: 4, bottom: 12),
        child: Text(text, style: TextStyle(color: c.muted, fontSize: 12.5)),
      );
      return SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                t.voiceSettings,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 12),
              if (plan.ttsServer) ...[
                Text(t.speechEngine),
                const SizedBox(height: 8),
                SegmentedButton<bool>(
                  showSelectedIcon: false,
                  segments: [
                    ButtonSegment(value: false, label: Text(t.listenDevice)),
                    ButtonSegment(value: true, label: Text(t.listenServer)),
                  ],
                  selected: {p.server},
                  onSelectionChanged: (v) => set(p.copyWith(server: v.first)),
                ),
                hint(p.server ? t.serverVoiceHint : t.deviceVoiceHint),
                if (p.server) ...[
                  SegmentedButton<String>(
                    showSelectedIcon: false,
                    segments: [
                      ButtonSegment(value: 'f', label: Text(t.voiceFemale)),
                      ButtonSegment(value: 'm', label: Text(t.voiceMale)),
                    ],
                    selected: {p.gender},
                    onSelectionChanged: (v) => set(p.copyWith(gender: v.first)),
                  ),
                  const SizedBox(height: 12),
                ],
              ] else
                hint(t.deviceVoiceHint),
              if (plan.aiFeatures) ...[
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(t.readMyLang),
                  value: p.myLanguage,
                  onChanged: (v) => set(p.copyWith(myLanguage: v)),
                ),
                hint(t.readMyLangHint),
              ],
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(t.autoRead),
                value: p.autoRead,
                onChanged: (v) => set(p.copyWith(autoRead: v)),
              ),
              if (plan.postRadio) ...[
                const Divider(height: 24),
                Text('📻 ${t.postRadio}'),
                hint(t.radioHint),
                Row(
                  children: [
                    Text(t.radioStopAfter),
                    const SizedBox(width: 12),
                    DropdownButton<int>(
                      value: p.radioPosts,
                      items: [
                        for (final n in const [5, 10, 20, 0])
                          DropdownMenuItem(
                            value: n,
                            child: Text(
                              n == 0 ? t.radioUnlimited : '$n ${t.radioPosts}',
                            ),
                          ),
                      ],
                      onChanged: (n) => set(p.copyWith(radioPosts: n)),
                    ),
                    const SizedBox(width: 12),
                    DropdownButton<int>(
                      value: p.radioMinutes,
                      items: [
                        for (final n in const [15, 30, 60, 0])
                          DropdownMenuItem(
                            value: n,
                            child: Text(
                              n == 0
                                  ? t.radioUnlimited
                                  : '$n ${t.radioMinutes}',
                            ),
                          ),
                      ],
                      onChanged: (n) => set(p.copyWith(radioMinutes: n)),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      );
    },
  ),
);
