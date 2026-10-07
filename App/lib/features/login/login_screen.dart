import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/api_client.dart';
import '../../auth/session.dart';
import '../../core/theme.dart';
import '../../l10n/app_localizations.dart';

enum _Mode { login, register, forgot }

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  _Mode _mode = _Mode.login;
  bool _busy = false;
  bool _registrationOpen = false;
  String? _error;
  String? _notice;

  @override
  void initState() {
    super.initState();
    // Debug builds only: a local test account passed at build time
    // (--dart-define=UFEED_DEV_EMAIL=… / UFEED_DEV_PASSWORD=…), since the
    // simulator can't paste into Flutter fields from automation.
    if (kDebugMode) {
      _email.text = const String.fromEnvironment('UFEED_DEV_EMAIL');
      _password.text = const String.fromEnvironment('UFEED_DEV_PASSWORD');
    }
    ref
        .read(apiProvider)
        .site()
        .then((s) {
          if (mounted) setState(() => _registrationOpen = s.registrationOpen);
        })
        .catchError((_) {});
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final t = AppLocalizations.of(context);
    final email = _email.text.trim();
    final password = _password.text;
    if (email.isEmpty) return;
    if (_mode == _Mode.register && password.length < 8) {
      setState(() => _error = t.passwordTooShort);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    final session = ref.read(sessionProvider.notifier);
    try {
      switch (_mode) {
        case _Mode.login:
          await session.login(email, password);
        case _Mode.register:
          await session.register(email, password);
        case _Mode.forgot:
          await ref.read(apiProvider).forgotPassword(email);
          if (mounted) setState(() => _notice = t.resetSent);
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = switch (e) {
          _ when e.isNetwork => t.offline,
          _ when e.status == 429 => t.tryLater,
          _ when e.code == 'registration_closed' => t.registrationClosed,
          _ when _mode == _Mode.register => t.registerFailed,
          _ => t.loginFailed,
        };
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _switch(_Mode mode) => setState(() {
    _mode = mode;
    _error = null;
    _notice = null;
  });

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.colors;
    final title = switch (_mode) {
      _Mode.login => t.login,
      _Mode.register => t.register,
      _Mode.forgot => t.forgotPassword,
    };
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 380),
              child: AutofillGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Center(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(18),
                        child: Image.asset(
                          'assets/icon/ufeed_icon.png',
                          width: 72,
                          height: 72,
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      t.appName,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineSmall
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      title,
                      textAlign: TextAlign.center,
                      style: TextStyle(color: c.muted),
                    ),
                    const SizedBox(height: 24),
                    if (_mode == _Mode.forgot) ...[
                      Text(t.forgotHint, style: TextStyle(color: c.muted)),
                      const SizedBox(height: 12),
                    ],
                    TextField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      autocorrect: false,
                      autofillHints: const [AutofillHints.email],
                      textInputAction: _mode == _Mode.forgot
                          ? TextInputAction.done
                          : TextInputAction.next,
                      onSubmitted: (_) =>
                          _mode == _Mode.forgot ? _submit() : null,
                      decoration: InputDecoration(
                        labelText: t.email,
                        border: const OutlineInputBorder(),
                      ),
                    ),
                    if (_mode != _Mode.forgot) ...[
                      const SizedBox(height: 12),
                      TextField(
                        controller: _password,
                        obscureText: true,
                        autofillHints: [
                          _mode == _Mode.register
                              ? AutofillHints.newPassword
                              : AutofillHints.password,
                        ],
                        textInputAction: TextInputAction.done,
                        onSubmitted: (_) => _submit(),
                        decoration: InputDecoration(
                          labelText: t.password,
                          border: const OutlineInputBorder(),
                        ),
                      ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Text(_error!, style: TextStyle(color: c.danger)),
                    ],
                    if (_notice != null) ...[
                      const SizedBox(height: 12),
                      Text(_notice!),
                    ],
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: _busy ? null : _submit,
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      child: _busy
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(
                              _mode == _Mode.forgot ? t.sendResetLink : title,
                            ),
                    ),
                    const SizedBox(height: 12),
                    if (_mode == _Mode.login) ...[
                      TextButton(
                        onPressed: () => _switch(_Mode.forgot),
                        child: Text(t.forgotPassword),
                      ),
                      if (_registrationOpen)
                        TextButton(
                          onPressed: () => _switch(_Mode.register),
                          child: Text('${t.needAccount} ${t.register}'),
                        ),
                    ] else
                      TextButton(
                        onPressed: () => _switch(_Mode.login),
                        child: Text(
                          _mode == _Mode.register
                              ? '${t.haveAccount} ${t.login}'
                              : t.backToLogin,
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
