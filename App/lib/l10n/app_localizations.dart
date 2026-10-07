import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_es.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('es'),
  ];

  /// No description provided for @appName.
  ///
  /// In es, this message translates to:
  /// **'uFeed'**
  String get appName;

  /// No description provided for @all.
  ///
  /// In es, this message translates to:
  /// **'Todo'**
  String get all;

  /// No description provided for @unread.
  ///
  /// In es, this message translates to:
  /// **'No leídos'**
  String get unread;

  /// No description provided for @saved.
  ///
  /// In es, this message translates to:
  /// **'Guardados'**
  String get saved;

  /// No description provided for @favorites.
  ///
  /// In es, this message translates to:
  /// **'Favoritos'**
  String get favorites;

  /// No description provided for @folders.
  ///
  /// In es, this message translates to:
  /// **'Carpetas'**
  String get folders;

  /// No description provided for @feeds.
  ///
  /// In es, this message translates to:
  /// **'Fuentes'**
  String get feeds;

  /// No description provided for @settings.
  ///
  /// In es, this message translates to:
  /// **'Ajustes'**
  String get settings;

  /// No description provided for @logout.
  ///
  /// In es, this message translates to:
  /// **'Cerrar sesión'**
  String get logout;

  /// No description provided for @login.
  ///
  /// In es, this message translates to:
  /// **'Entrar'**
  String get login;

  /// No description provided for @register.
  ///
  /// In es, this message translates to:
  /// **'Crear cuenta'**
  String get register;

  /// No description provided for @email.
  ///
  /// In es, this message translates to:
  /// **'Correo'**
  String get email;

  /// No description provided for @password.
  ///
  /// In es, this message translates to:
  /// **'Contraseña'**
  String get password;

  /// No description provided for @needAccount.
  ///
  /// In es, this message translates to:
  /// **'¿No tienes cuenta?'**
  String get needAccount;

  /// No description provided for @haveAccount.
  ///
  /// In es, this message translates to:
  /// **'¿Ya tienes cuenta?'**
  String get haveAccount;

  /// No description provided for @loginFailed.
  ///
  /// In es, this message translates to:
  /// **'Fallo al entrar. Revisa tus credenciales.'**
  String get loginFailed;

  /// No description provided for @registerFailed.
  ///
  /// In es, this message translates to:
  /// **'No se pudo crear la cuenta.'**
  String get registerFailed;

  /// No description provided for @registrationClosed.
  ///
  /// In es, this message translates to:
  /// **'El registro de cuentas está cerrado en este servidor.'**
  String get registrationClosed;

  /// No description provided for @passwordTooShort.
  ///
  /// In es, this message translates to:
  /// **'Mínimo 8 caracteres.'**
  String get passwordTooShort;

  /// No description provided for @forgotPassword.
  ///
  /// In es, this message translates to:
  /// **'¿Has olvidado la contraseña?'**
  String get forgotPassword;

  /// No description provided for @forgotHint.
  ///
  /// In es, this message translates to:
  /// **'Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una nueva contraseña.'**
  String get forgotHint;

  /// No description provided for @sendResetLink.
  ///
  /// In es, this message translates to:
  /// **'Enviar enlace'**
  String get sendResetLink;

  /// No description provided for @resetSent.
  ///
  /// In es, this message translates to:
  /// **'Si ese correo tiene cuenta en uFeed, te hemos enviado un enlace (válido 1 hora). Revisa también el correo no deseado.'**
  String get resetSent;

  /// No description provided for @tryLater.
  ///
  /// In es, this message translates to:
  /// **'Demasiados intentos; prueba más tarde.'**
  String get tryLater;

  /// No description provided for @backToLogin.
  ///
  /// In es, this message translates to:
  /// **'Volver a entrar'**
  String get backToLogin;

  /// No description provided for @noArticles.
  ///
  /// In es, this message translates to:
  /// **'Aún no hay nada aquí.'**
  String get noArticles;

  /// No description provided for @noUnreadHere.
  ///
  /// In es, this message translates to:
  /// **'No hay nada sin leer aquí.'**
  String get noUnreadHere;

  /// No description provided for @loading.
  ///
  /// In es, this message translates to:
  /// **'Cargando…'**
  String get loading;

  /// No description provided for @offline.
  ///
  /// In es, this message translates to:
  /// **'Sin conexión con el servidor.'**
  String get offline;

  /// No description provided for @retry.
  ///
  /// In es, this message translates to:
  /// **'Reintentar'**
  String get retry;

  /// No description provided for @markAllRead.
  ///
  /// In es, this message translates to:
  /// **'Marcar todo leído'**
  String get markAllRead;

  /// No description provided for @markRead.
  ///
  /// In es, this message translates to:
  /// **'Marcar leído'**
  String get markRead;

  /// No description provided for @markUnread.
  ///
  /// In es, this message translates to:
  /// **'Marcar no leído'**
  String get markUnread;

  /// No description provided for @save.
  ///
  /// In es, this message translates to:
  /// **'Guardar'**
  String get save;

  /// No description provided for @unsave.
  ///
  /// In es, this message translates to:
  /// **'Quitar'**
  String get unsave;

  /// No description provided for @favorite.
  ///
  /// In es, this message translates to:
  /// **'Favorito'**
  String get favorite;

  /// No description provided for @unfavorite.
  ///
  /// In es, this message translates to:
  /// **'Quitar favorito'**
  String get unfavorite;

  /// No description provided for @trending.
  ///
  /// In es, this message translates to:
  /// **'Tendencias'**
  String get trending;

  /// No description provided for @forYou.
  ///
  /// In es, this message translates to:
  /// **'Para ti'**
  String get forYou;

  /// No description provided for @openOriginal.
  ///
  /// In es, this message translates to:
  /// **'Abrir original'**
  String get openOriginal;

  /// No description provided for @share.
  ///
  /// In es, this message translates to:
  /// **'Compartir'**
  String get share;

  /// No description provided for @minutesAgo.
  ///
  /// In es, this message translates to:
  /// **'{n} min'**
  String minutesAgo(int n);

  /// No description provided for @hoursAgo.
  ///
  /// In es, this message translates to:
  /// **'{n} h'**
  String hoursAgo(int n);

  /// No description provided for @daysAgo.
  ///
  /// In es, this message translates to:
  /// **'{n} d'**
  String daysAgo(int n);

  /// No description provided for @readingMinutes.
  ///
  /// In es, this message translates to:
  /// **'{n} min de lectura'**
  String readingMinutes(int n);

  /// No description provided for @listen.
  ///
  /// In es, this message translates to:
  /// **'Escuchar'**
  String get listen;

  /// No description provided for @listenPreparing.
  ///
  /// In es, this message translates to:
  /// **'Preparando audio…'**
  String get listenPreparing;

  /// No description provided for @listenPlan.
  ///
  /// In es, this message translates to:
  /// **'Tu plan no incluye la voz del servidor.'**
  String get listenPlan;

  /// No description provided for @listenRateLimited.
  ///
  /// In es, this message translates to:
  /// **'Demasiadas peticiones de audio esta hora; prueba más tarde.'**
  String get listenRateLimited;

  /// No description provided for @listenUnavailable.
  ///
  /// In es, this message translates to:
  /// **'La voz del servidor no está disponible ahora.'**
  String get listenUnavailable;

  /// No description provided for @listenLangUnsupported.
  ///
  /// In es, this message translates to:
  /// **'No hay voz de servidor para el idioma de este artículo.'**
  String get listenLangUnsupported;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'es'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'es':
      return AppLocalizationsEs();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
