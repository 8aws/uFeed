import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';

/// Ask for a short text (a name). Null if cancelled or left empty.
Future<String?> promptText(
  BuildContext context, {
  required String title,
  String initial = '',
  String? hint,
  bool obscure = false,
}) async {
  final t = AppLocalizations.of(context);
  final ctrl = TextEditingController(text: initial);
  final value = await showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: TextField(
        controller: ctrl,
        autofocus: true,
        obscureText: obscure,
        decoration: InputDecoration(hintText: hint),
        onSubmitted: (v) => Navigator.of(context).pop(v),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(t.cancel),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(ctrl.text),
          child: Text(t.done),
        ),
      ],
    ),
  );
  ctrl.dispose();
  final v = value?.trim();
  return v == null || v.isEmpty ? null : v;
}

/// Yes/no for a destructive action.
Future<bool> confirm(
  BuildContext context, {
  required String message,
  required String action,
  String? cancel,
}) async {
  final t = AppLocalizations.of(context);
  final ok = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      content: Text(message),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(cancel ?? t.cancel),
        ),
        FilledButton(
          style: FilledButton.styleFrom(
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(action),
        ),
      ],
    ),
  );
  return ok ?? false;
}

void toast(BuildContext context, String message) => ScaffoldMessenger.of(
  context,
).showSnackBar(SnackBar(content: Text(message)));
