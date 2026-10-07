import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'api/models.dart';
import 'auth/session.dart';
import 'core/theme.dart';
import 'features/home/home_screen.dart';
import 'features/login/login_screen.dart';
import 'features/reader/reader_screen.dart';
import 'l10n/app_localizations.dart';

final routerProvider = Provider<GoRouter>((ref) {
  // Re-run the redirect whenever the session changes (sign in / out).
  final changes = ValueNotifier(0);
  ref.listen(sessionProvider, (_, _) => changes.value++);
  ref.onDispose(changes.dispose);

  return GoRouter(
    refreshListenable: changes,
    redirect: (context, state) {
      final session = ref.read(sessionProvider);
      if (session.isLoading || session.hasError) return '/start';
      final signedIn = session.value != null;
      final at = state.matchedLocation;
      if (!signedIn) return at == '/login' ? null : '/login';
      if (at == '/login' || at == '/start') return '/';
      return null;
    },
    routes: [
      GoRoute(path: '/start', builder: (_, _) => const _StartScreen()),
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
      GoRoute(path: '/', builder: (_, _) => const HomeScreen()),
      GoRoute(
        path: '/article/:id',
        builder: (_, state) => ReaderScreen(article: state.extra! as Article),
      ),
    ],
  );
});

class UFeedApp extends ConsumerWidget {
  const UFeedApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      onGenerateTitle: (context) => AppLocalizations.of(context).appName,
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      routerConfig: ref.watch(routerProvider),
    );
  }
}

/// While the saved session is checked; or a retry if the server is unreachable.
class _StartScreen extends ConsumerWidget {
  const _StartScreen();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context);
    final session = ref.watch(sessionProvider);
    return Scaffold(
      body: Center(
        child: session.hasError
            ? Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(t.offline),
                  const SizedBox(height: 8),
                  FilledButton(
                    onPressed: ref.read(sessionProvider.notifier).retry,
                    child: Text(t.retry),
                  ),
                ],
              )
            : const CircularProgressIndicator(),
      ),
    );
  }
}
