import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/api_client.dart';
import '../../api/models.dart';
import '../../auth/session.dart';
import '../../core/dialogs.dart';
import '../../l10n/app_localizations.dart';
import '../home/home_state.dart';

/// Long press on a feed in the side menu.
Future<void> showFeedActions(
  BuildContext context,
  WidgetRef ref,
  Subscription sub,
) async {
  final t = AppLocalizations.of(context);
  final api = ref.read(apiProvider);
  final side = ref.read(sidebarProvider).value;

  Future<void> run(Future<void> Function() action) async {
    try {
      await action();
      await ref.read(sidebarProvider.notifier).reload();
      ref.invalidate(articleListProvider);
    } on ApiException {
      if (context.mounted) toast(context, t.somethingFailed);
    }
  }

  final choice = await showModalBottomSheet<String>(
    context: context,
    showDragHandle: true,
    builder: (context) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            title: Text(
              sub.title,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.edit_outlined),
            title: Text(t.rename),
            onTap: () => Navigator.of(context).pop('rename'),
          ),
          ListTile(
            leading: const Icon(Icons.drive_file_move_outline),
            title: Text(t.moveTo),
            onTap: () => Navigator.of(context).pop('move'),
          ),
          ListTile(
            leading: Icon(
              sub.muted ? Icons.volume_up_outlined : Icons.volume_off_outlined,
            ),
            title: Text(sub.muted ? t.unmute : t.mute),
            onTap: () => Navigator.of(context).pop('mute'),
          ),
          ListTile(
            leading: Icon(
              Icons.delete_outline,
              color: Theme.of(context).colorScheme.error,
            ),
            title: Text(t.unsubscribe),
            onTap: () => Navigator.of(context).pop('unsubscribe'),
          ),
        ],
      ),
    ),
  );
  if (!context.mounted || choice == null) return;

  switch (choice) {
    case 'rename':
      final name = await promptText(
        context,
        title: t.rename,
        initial: sub.title,
      );
      if (name != null) {
        await run(() => api.updateSubscription(sub.id, {'custom_title': name}));
      }
    case 'move':
      final folders = side?.folders ?? const <Folder>[];
      final picked = await showModalBottomSheet<(String?,)>(
        context: context,
        showDragHandle: true,
        builder: (context) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              ListTile(
                leading: const Icon(Icons.inbox_outlined),
                title: Text(t.noFolder),
                selected: sub.folderId == null,
                onTap: () => Navigator.of(context).pop((null,)),
              ),
              for (final f in folders)
                ListTile(
                  leading: const Icon(Icons.folder_outlined),
                  title: Text(f.name),
                  selected: sub.folderId == f.id,
                  onTap: () => Navigator.of(context).pop((f.id,)),
                ),
              ListTile(
                leading: const Icon(Icons.create_new_folder_outlined),
                title: Text(t.newFolder),
                onTap: () => Navigator.of(context).pop(('__new__',)),
              ),
            ],
          ),
        ),
      );
      if (picked == null || !context.mounted) return;
      var folderId = picked.$1;
      if (folderId == '__new__') {
        final name = await promptText(context, title: t.newFolder);
        if (name == null) return;
        try {
          folderId = (await api.createFolder(name)).id;
        } on ApiException {
          if (context.mounted) toast(context, t.somethingFailed);
          return;
        }
      }
      await run(() => api.updateSubscription(sub.id, {'folder_id': folderId}));
    case 'mute':
      await run(() => api.updateSubscription(sub.id, {'muted': !sub.muted}));
    case 'unsubscribe':
      final ok = await confirm(
        context,
        message: t.confirmUnsubscribe,
        action: t.unsubscribe,
      );
      if (!ok) return;
      final current = ref.read(filterProvider);
      await run(() => api.unsubscribe(sub.id));
      if (current.kind == FilterKind.source && current.id == sub.source.id) {
        ref.read(filterProvider.notifier).set(const Filter(FilterKind.unread));
      }
  }
}

/// Long press on a folder in the side menu.
Future<void> showFolderActions(
  BuildContext context,
  WidgetRef ref,
  Folder folder,
) async {
  final t = AppLocalizations.of(context);
  final api = ref.read(apiProvider);
  final choice = await showModalBottomSheet<String>(
    context: context,
    showDragHandle: true,
    builder: (context) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            title: Text(
              folder.name,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.edit_outlined),
            title: Text(t.rename),
            onTap: () => Navigator.of(context).pop('rename'),
          ),
          ListTile(
            leading: Icon(
              Icons.delete_outline,
              color: Theme.of(context).colorScheme.error,
            ),
            title: Text(t.deleteFolder),
            onTap: () => Navigator.of(context).pop('delete'),
          ),
        ],
      ),
    ),
  );
  if (!context.mounted || choice == null) return;
  try {
    if (choice == 'rename') {
      final name = await promptText(
        context,
        title: t.rename,
        initial: folder.name,
      );
      if (name == null) return;
      await api.renameFolder(folder.id, name);
    } else {
      final ok = await confirm(
        context,
        message: t.confirmDeleteFolder,
        action: t.delete,
      );
      if (!ok) return;
      await api.deleteFolder(folder.id);
      final current = ref.read(filterProvider);
      if (current.kind == FilterKind.folder && current.id == folder.id) {
        ref.read(filterProvider.notifier).set(const Filter(FilterKind.unread));
      }
    }
    await ref.read(sidebarProvider.notifier).reload();
  } on ApiException {
    if (context.mounted) toast(context, t.somethingFailed);
  }
}

/// "New folder" in the side menu.
Future<void> createFolder(BuildContext context, WidgetRef ref) async {
  final t = AppLocalizations.of(context);
  final name = await promptText(context, title: t.newFolder);
  if (name == null) return;
  try {
    await ref.read(apiProvider).createFolder(name);
    await ref.read(sidebarProvider.notifier).reload();
  } on ApiException {
    if (context.mounted) toast(context, t.somethingFailed);
  }
}
