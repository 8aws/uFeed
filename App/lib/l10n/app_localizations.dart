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

  /// No description provided for @view.
  ///
  /// In es, this message translates to:
  /// **'Vista'**
  String get view;

  /// No description provided for @viewList.
  ///
  /// In es, this message translates to:
  /// **'Lista'**
  String get viewList;

  /// No description provided for @viewCardList.
  ///
  /// In es, this message translates to:
  /// **'Lista de tarjetas'**
  String get viewCardList;

  /// No description provided for @viewCards.
  ///
  /// In es, this message translates to:
  /// **'Tarjetas'**
  String get viewCards;

  /// No description provided for @viewMasonry.
  ///
  /// In es, this message translates to:
  /// **'Mosaico'**
  String get viewMasonry;

  /// No description provided for @showAllPosts.
  ///
  /// In es, this message translates to:
  /// **'Ver también los leídos'**
  String get showAllPosts;

  /// No description provided for @readers.
  ///
  /// In es, this message translates to:
  /// **'{n, plural, =1{1 lector} other{{n} lectores}}'**
  String readers(int n);

  /// No description provided for @trendingNow.
  ///
  /// In es, this message translates to:
  /// **'Tendencia ahora'**
  String get trendingNow;

  /// No description provided for @top.
  ///
  /// In es, this message translates to:
  /// **'Top'**
  String get top;

  /// No description provided for @mostSaved.
  ///
  /// In es, this message translates to:
  /// **'Más guardados'**
  String get mostSaved;

  /// No description provided for @deepReads.
  ///
  /// In es, this message translates to:
  /// **'Lecturas profundas'**
  String get deepReads;

  /// No description provided for @hiddenGems.
  ///
  /// In es, this message translates to:
  /// **'Joyas ocultas'**
  String get hiddenGems;

  /// No description provided for @by.
  ///
  /// In es, this message translates to:
  /// **'por'**
  String get by;

  /// No description provided for @planLimitAi.
  ///
  /// In es, this message translates to:
  /// **'Tu plan no incluye funciones de IA.'**
  String get planLimitAi;

  /// No description provided for @aiGenerating.
  ///
  /// In es, this message translates to:
  /// **'Generando…'**
  String get aiGenerating;

  /// No description provided for @aiQueued.
  ///
  /// In es, this message translates to:
  /// **'En cola, puesto {n}'**
  String aiQueued(int n);

  /// No description provided for @aiFailed.
  ///
  /// In es, this message translates to:
  /// **'No se pudo generar el resumen. Pulsa la barra para reintentar.'**
  String get aiFailed;

  /// No description provided for @aiDailyLimit.
  ///
  /// In es, this message translates to:
  /// **'Has usado los resúmenes IA de hoy. Los que ya existen siguen disponibles.'**
  String get aiDailyLimit;

  /// No description provided for @aiSummary.
  ///
  /// In es, this message translates to:
  /// **'Resumen IA'**
  String get aiSummary;

  /// No description provided for @aiUnavailable.
  ///
  /// In es, this message translates to:
  /// **'La IA no está disponible ahora.'**
  String get aiUnavailable;

  /// No description provided for @aiRate.
  ///
  /// In es, this message translates to:
  /// **'Demasiados resúmenes IA esta hora; prueba más tarde.'**
  String get aiRate;

  /// No description provided for @translate.
  ///
  /// In es, this message translates to:
  /// **'Traducir'**
  String get translate;

  /// No description provided for @translating.
  ///
  /// In es, this message translates to:
  /// **'Traduciendo…'**
  String get translating;

  /// No description provided for @showOriginal.
  ///
  /// In es, this message translates to:
  /// **'Ver original'**
  String get showOriginal;

  /// No description provided for @machineTranslation.
  ///
  /// In es, this message translates to:
  /// **'Traducción automática'**
  String get machineTranslation;

  /// No description provided for @translateUnavailable.
  ///
  /// In es, this message translates to:
  /// **'La traducción no está disponible ahora.'**
  String get translateUnavailable;

  /// No description provided for @textSize.
  ///
  /// In es, this message translates to:
  /// **'Tamaño del texto'**
  String get textSize;

  /// No description provided for @font.
  ///
  /// In es, this message translates to:
  /// **'Tipo de letra'**
  String get font;

  /// No description provided for @fontSystem.
  ///
  /// In es, this message translates to:
  /// **'Del sistema'**
  String get fontSystem;

  /// No description provided for @fullArticle.
  ///
  /// In es, this message translates to:
  /// **'Artículo completo'**
  String get fullArticle;

  /// No description provided for @showExcerpt.
  ///
  /// In es, this message translates to:
  /// **'Extracto del feed'**
  String get showExcerpt;

  /// No description provided for @fullLoading.
  ///
  /// In es, this message translates to:
  /// **'Cargando el artículo completo…'**
  String get fullLoading;

  /// No description provided for @fullNote.
  ///
  /// In es, this message translates to:
  /// **'Artículo completo desde la web'**
  String get fullNote;

  /// No description provided for @fullUnavailable.
  ///
  /// In es, this message translates to:
  /// **'No se pudo cargar el artículo completo desde la web.'**
  String get fullUnavailable;

  /// No description provided for @autoFull.
  ///
  /// In es, this message translates to:
  /// **'Cargar el artículo completo cuando la fuente solo da un extracto'**
  String get autoFull;

  /// No description provided for @similar.
  ///
  /// In es, this message translates to:
  /// **'Similares'**
  String get similar;

  /// No description provided for @more.
  ///
  /// In es, this message translates to:
  /// **'Más'**
  String get more;

  /// No description provided for @offlineBanner.
  ///
  /// In es, this message translates to:
  /// **'Sin conexión: mostrando la copia guardada en el dispositivo.'**
  String get offlineBanner;

  /// No description provided for @pendingSync.
  ///
  /// In es, this message translates to:
  /// **'{n, plural, =1{1 cambio pendiente de sincronizar} other{{n} cambios pendientes de sincronizar}}'**
  String pendingSync(int n);

  /// No description provided for @listenDevice.
  ///
  /// In es, this message translates to:
  /// **'Dispositivo'**
  String get listenDevice;

  /// No description provided for @listenServer.
  ///
  /// In es, this message translates to:
  /// **'Servidor'**
  String get listenServer;

  /// No description provided for @listenSpeed.
  ///
  /// In es, this message translates to:
  /// **'Velocidad'**
  String get listenSpeed;

  /// No description provided for @serverVoice.
  ///
  /// In es, this message translates to:
  /// **'Voz del servidor'**
  String get serverVoice;

  /// No description provided for @voiceFemale.
  ///
  /// In es, this message translates to:
  /// **'Femenina'**
  String get voiceFemale;

  /// No description provided for @voiceMale.
  ///
  /// In es, this message translates to:
  /// **'Masculina'**
  String get voiceMale;

  /// No description provided for @deviceVoice.
  ///
  /// In es, this message translates to:
  /// **'Voz del dispositivo'**
  String get deviceVoice;

  /// No description provided for @deviceVoiceHint.
  ///
  /// In es, this message translates to:
  /// **'En iPhone, descarga las voces «Mejorada» o «Premium» (Ajustes → Accesibilidad → Contenido leído) para un sonido mucho mejor.'**
  String get deviceVoiceHint;

  /// No description provided for @serverVoiceHint.
  ///
  /// In es, this message translates to:
  /// **'Voz neuronal generada en el servidor: suena igual en todos tus dispositivos.'**
  String get serverVoiceHint;

  /// No description provided for @autoRead.
  ///
  /// In es, this message translates to:
  /// **'Leer los artículos en voz alta al abrirlos'**
  String get autoRead;

  /// No description provided for @readMyLang.
  ///
  /// In es, this message translates to:
  /// **'Leer siempre en mi idioma'**
  String get readMyLang;

  /// No description provided for @readMyLangHint.
  ///
  /// In es, this message translates to:
  /// **'Los artículos en otro idioma (inglés ↔ español) se traducen antes de leerlos.'**
  String get readMyLangHint;

  /// No description provided for @speechEngine.
  ///
  /// In es, this message translates to:
  /// **'Voz preferida'**
  String get speechEngine;

  /// No description provided for @postRadio.
  ///
  /// In es, this message translates to:
  /// **'Post radio'**
  String get postRadio;

  /// No description provided for @postRadioStart.
  ///
  /// In es, this message translates to:
  /// **'Post radio: escuchar esta lista'**
  String get postRadioStart;

  /// No description provided for @radioNext.
  ///
  /// In es, this message translates to:
  /// **'Siguiente post'**
  String get radioNext;

  /// No description provided for @radioStop.
  ///
  /// In es, this message translates to:
  /// **'Parar la radio'**
  String get radioStop;

  /// No description provided for @radioHint.
  ///
  /// In es, this message translates to:
  /// **'Lee los posts de la lista uno tras otro, con un breve sonido entre ellos. Un post solo se marca como leído si se ha escuchado al menos el 70 %.'**
  String get radioHint;

  /// No description provided for @radioStopAfter.
  ///
  /// In es, this message translates to:
  /// **'Parar tras'**
  String get radioStopAfter;

  /// No description provided for @radioPosts.
  ///
  /// In es, this message translates to:
  /// **'posts'**
  String get radioPosts;

  /// No description provided for @radioMinutes.
  ///
  /// In es, this message translates to:
  /// **'min'**
  String get radioMinutes;

  /// No description provided for @radioDone.
  ///
  /// In es, this message translates to:
  /// **'Post radio terminada'**
  String get radioDone;

  /// No description provided for @radioUnlimited.
  ///
  /// In es, this message translates to:
  /// **'sin límite'**
  String get radioUnlimited;

  /// No description provided for @radioPosition.
  ///
  /// In es, this message translates to:
  /// **'Post {n} de {total}'**
  String radioPosition(int n, int total);

  /// No description provided for @sentence.
  ///
  /// In es, this message translates to:
  /// **'Frase {n} de {total}'**
  String sentence(int n, int total);

  /// No description provided for @voiceSettings.
  ///
  /// In es, this message translates to:
  /// **'Voz y lectura'**
  String get voiceSettings;

  /// No description provided for @back15.
  ///
  /// In es, this message translates to:
  /// **'Atrás 10 s'**
  String get back15;

  /// No description provided for @forward15.
  ///
  /// In es, this message translates to:
  /// **'Adelante 10 s'**
  String get forward15;

  /// No description provided for @play.
  ///
  /// In es, this message translates to:
  /// **'Reproducir'**
  String get play;

  /// No description provided for @pause.
  ///
  /// In es, this message translates to:
  /// **'Pausa'**
  String get pause;

  /// No description provided for @stop.
  ///
  /// In es, this message translates to:
  /// **'Parar'**
  String get stop;

  /// No description provided for @listenGenerating.
  ///
  /// In es, this message translates to:
  /// **'generando'**
  String get listenGenerating;

  /// No description provided for @addFeed.
  ///
  /// In es, this message translates to:
  /// **'Añadir fuente'**
  String get addFeed;

  /// No description provided for @addFeedPlaceholder.
  ///
  /// In es, this message translates to:
  /// **'URL del blog o feed…'**
  String get addFeedPlaceholder;

  /// No description provided for @discover.
  ///
  /// In es, this message translates to:
  /// **'Buscar feeds'**
  String get discover;

  /// No description provided for @subscribe.
  ///
  /// In es, this message translates to:
  /// **'Suscribirse'**
  String get subscribe;

  /// No description provided for @subscribed.
  ///
  /// In es, this message translates to:
  /// **'Suscrito'**
  String get subscribed;

  /// No description provided for @noFeedsFound.
  ///
  /// In es, this message translates to:
  /// **'No se encontraron feeds en esa URL.'**
  String get noFeedsFound;

  /// No description provided for @unsubscribe.
  ///
  /// In es, this message translates to:
  /// **'Cancelar suscripción'**
  String get unsubscribe;

  /// No description provided for @confirmUnsubscribe.
  ///
  /// In es, this message translates to:
  /// **'¿Cancelar la suscripción a esta fuente?'**
  String get confirmUnsubscribe;

  /// No description provided for @importOpml.
  ///
  /// In es, this message translates to:
  /// **'Importar OPML'**
  String get importOpml;

  /// No description provided for @exportOpml.
  ///
  /// In es, this message translates to:
  /// **'Exportar OPML'**
  String get exportOpml;

  /// No description provided for @opmlImported.
  ///
  /// In es, this message translates to:
  /// **'{n} fuentes importadas, {m} omitidas.'**
  String opmlImported(int n, int m);

  /// No description provided for @account.
  ///
  /// In es, this message translates to:
  /// **'Cuenta'**
  String get account;

  /// No description provided for @starterSources.
  ///
  /// In es, this message translates to:
  /// **'Sugerencias iniciales'**
  String get starterSources;

  /// No description provided for @catalogAdd.
  ///
  /// In es, this message translates to:
  /// **'Añadir'**
  String get catalogAdd;

  /// No description provided for @catalogRemove.
  ///
  /// In es, this message translates to:
  /// **'Quitar'**
  String get catalogRemove;

  /// No description provided for @catalogAddAll.
  ///
  /// In es, this message translates to:
  /// **'Añadir todas'**
  String get catalogAddAll;

  /// No description provided for @allLangs.
  ///
  /// In es, this message translates to:
  /// **'Todas'**
  String get allLangs;

  /// No description provided for @langEs.
  ///
  /// In es, this message translates to:
  /// **'Español'**
  String get langEs;

  /// No description provided for @langEn.
  ///
  /// In es, this message translates to:
  /// **'Inglés'**
  String get langEn;

  /// No description provided for @plan.
  ///
  /// In es, this message translates to:
  /// **'Plan'**
  String get plan;

  /// No description provided for @roleFree.
  ///
  /// In es, this message translates to:
  /// **'Gratis'**
  String get roleFree;

  /// No description provided for @roleGeneral.
  ///
  /// In es, this message translates to:
  /// **'General'**
  String get roleGeneral;

  /// No description provided for @roleVip.
  ///
  /// In es, this message translates to:
  /// **'VIP'**
  String get roleVip;

  /// No description provided for @roleEditor.
  ///
  /// In es, this message translates to:
  /// **'Editor'**
  String get roleEditor;

  /// No description provided for @roleAdmin.
  ///
  /// In es, this message translates to:
  /// **'Administrador'**
  String get roleAdmin;

  /// No description provided for @admin.
  ///
  /// In es, this message translates to:
  /// **'Administración'**
  String get admin;

  /// No description provided for @curation.
  ///
  /// In es, this message translates to:
  /// **'Curación'**
  String get curation;

  /// No description provided for @privacy.
  ///
  /// In es, this message translates to:
  /// **'Privacidad'**
  String get privacy;

  /// No description provided for @support.
  ///
  /// In es, this message translates to:
  /// **'Soporte'**
  String get support;

  /// No description provided for @currentPassword.
  ///
  /// In es, this message translates to:
  /// **'Contraseña actual'**
  String get currentPassword;

  /// No description provided for @newPassword.
  ///
  /// In es, this message translates to:
  /// **'Nueva contraseña'**
  String get newPassword;

  /// No description provided for @confirmPassword.
  ///
  /// In es, this message translates to:
  /// **'Repite la nueva contraseña'**
  String get confirmPassword;

  /// No description provided for @changePassword.
  ///
  /// In es, this message translates to:
  /// **'Cambiar contraseña'**
  String get changePassword;

  /// No description provided for @passwordChanged.
  ///
  /// In es, this message translates to:
  /// **'Contraseña cambiada. Se ha cerrado la sesión en otros dispositivos.'**
  String get passwordChanged;

  /// No description provided for @passwordMismatch.
  ///
  /// In es, this message translates to:
  /// **'Las contraseñas no coinciden.'**
  String get passwordMismatch;

  /// No description provided for @wrongPassword.
  ///
  /// In es, this message translates to:
  /// **'La contraseña actual no es correcta.'**
  String get wrongPassword;

  /// No description provided for @deleteAccount.
  ///
  /// In es, this message translates to:
  /// **'Eliminar cuenta'**
  String get deleteAccount;

  /// No description provided for @deleteAccountHint.
  ///
  /// In es, this message translates to:
  /// **'Borra tu cuenta y todos sus datos (fuentes, carpetas, guardados, claves). No se puede deshacer. Escribe tu contraseña para confirmar.'**
  String get deleteAccountHint;

  /// No description provided for @digestTitle.
  ///
  /// In es, this message translates to:
  /// **'Resumen diario por correo'**
  String get digestTitle;

  /// No description provided for @digestHint.
  ///
  /// In es, this message translates to:
  /// **'Lo más relevante de las últimas 24 horas en tus fuentes, una vez al día.'**
  String get digestHint;

  /// No description provided for @digestOff.
  ///
  /// In es, this message translates to:
  /// **'Desactivado'**
  String get digestOff;

  /// No description provided for @digestAt.
  ///
  /// In es, this message translates to:
  /// **'A las'**
  String get digestAt;

  /// No description provided for @digestEveryDay.
  ///
  /// In es, this message translates to:
  /// **'Todos los días'**
  String get digestEveryDay;

  /// No description provided for @digestWeekdays.
  ///
  /// In es, this message translates to:
  /// **'Laborables (L–V)'**
  String get digestWeekdays;

  /// No description provided for @digestWeekends.
  ///
  /// In es, this message translates to:
  /// **'Fin de semana'**
  String get digestWeekends;

  /// No description provided for @digestCustom.
  ///
  /// In es, this message translates to:
  /// **'Elegir días'**
  String get digestCustom;

  /// No description provided for @digestDayLetters.
  ///
  /// In es, this message translates to:
  /// **'L,M,X,J,V,S,D'**
  String get digestDayLetters;

  /// No description provided for @mute.
  ///
  /// In es, this message translates to:
  /// **'Silenciar'**
  String get mute;

  /// No description provided for @unmute.
  ///
  /// In es, this message translates to:
  /// **'Quitar silencio'**
  String get unmute;

  /// No description provided for @filters.
  ///
  /// In es, this message translates to:
  /// **'Filtros'**
  String get filters;

  /// No description provided for @filtersHint.
  ///
  /// In es, this message translates to:
  /// **'Oculta los artículos cuyo título o resumen contenga estas palabras. Guardados y favoritos nunca se ocultan.'**
  String get filtersHint;

  /// No description provided for @addKeyword.
  ///
  /// In es, this message translates to:
  /// **'Añade una palabra o frase…'**
  String get addKeyword;

  /// No description provided for @mutedSources.
  ///
  /// In es, this message translates to:
  /// **'Fuentes silenciadas'**
  String get mutedSources;

  /// No description provided for @mutedSourcesHint.
  ///
  /// In es, this message translates to:
  /// **'No aparecen en No leídos, Todo, carpetas ni recomendaciones; abre la fuente para leerla.'**
  String get mutedSourcesHint;

  /// No description provided for @noMuted.
  ///
  /// In es, this message translates to:
  /// **'Nada silenciado.'**
  String get noMuted;

  /// No description provided for @planLimitFeeds.
  ///
  /// In es, this message translates to:
  /// **'Has llegado al límite de fuentes de tu plan.'**
  String get planLimitFeeds;

  /// No description provided for @appearance.
  ///
  /// In es, this message translates to:
  /// **'Apariencia'**
  String get appearance;

  /// No description provided for @deleteFolder.
  ///
  /// In es, this message translates to:
  /// **'Eliminar carpeta'**
  String get deleteFolder;

  /// No description provided for @confirmDeleteFolder.
  ///
  /// In es, this message translates to:
  /// **'¿Eliminar esta carpeta? Sus fuentes pasan a la raíz.'**
  String get confirmDeleteFolder;

  /// No description provided for @newFolder.
  ///
  /// In es, this message translates to:
  /// **'Nueva carpeta'**
  String get newFolder;

  /// No description provided for @noFolder.
  ///
  /// In es, this message translates to:
  /// **'Sin carpeta'**
  String get noFolder;

  /// No description provided for @rename.
  ///
  /// In es, this message translates to:
  /// **'Cambiar nombre'**
  String get rename;

  /// No description provided for @moveTo.
  ///
  /// In es, this message translates to:
  /// **'Mover a carpeta'**
  String get moveTo;

  /// No description provided for @name.
  ///
  /// In es, this message translates to:
  /// **'Nombre'**
  String get name;

  /// No description provided for @cancel.
  ///
  /// In es, this message translates to:
  /// **'Cancelar'**
  String get cancel;

  /// No description provided for @delete.
  ///
  /// In es, this message translates to:
  /// **'Eliminar'**
  String get delete;

  /// No description provided for @done.
  ///
  /// In es, this message translates to:
  /// **'Hecho'**
  String get done;

  /// No description provided for @feedsAndFolders.
  ///
  /// In es, this message translates to:
  /// **'Fuentes y carpetas'**
  String get feedsAndFolders;

  /// No description provided for @somethingFailed.
  ///
  /// In es, this message translates to:
  /// **'No se pudo completar. Inténtalo de nuevo.'**
  String get somethingFailed;

  /// No description provided for @web.
  ///
  /// In es, this message translates to:
  /// **'Abrir en la web'**
  String get web;

  /// No description provided for @demoAccount.
  ///
  /// In es, this message translates to:
  /// **'La cuenta de demostración no se puede cambiar ni eliminar.'**
  String get demoAccount;

  /// No description provided for @lastAdmin.
  ///
  /// In es, this message translates to:
  /// **'Nombra a otra persona administradora antes de eliminar esta cuenta.'**
  String get lastAdmin;

  /// No description provided for @settingsMenu.
  ///
  /// In es, this message translates to:
  /// **'Ajustes'**
  String get settingsMenu;

  /// No description provided for @confirmMarkAllRead.
  ///
  /// In es, this message translates to:
  /// **'¿Marcar como leídos todos los artículos de esta vista?'**
  String get confirmMarkAllRead;

  /// No description provided for @newItems.
  ///
  /// In es, this message translates to:
  /// **'{n, plural, =1{1 artículo nuevo} other{{n} artículos nuevos}}'**
  String newItems(int n);

  /// No description provided for @noNew.
  ///
  /// In es, this message translates to:
  /// **'Sin novedades'**
  String get noNew;

  /// No description provided for @refreshWait.
  ///
  /// In es, this message translates to:
  /// **'Disponible en {n} min'**
  String refreshWait(int n);

  /// No description provided for @offlineAudio.
  ///
  /// In es, this message translates to:
  /// **'Audio sin conexión de los guardados'**
  String get offlineAudio;

  /// No description provided for @offlineAudioHint.
  ///
  /// In es, this message translates to:
  /// **'Guarda en este iPhone la voz del servidor de tus 20 últimos artículos guardados (~1,5 MB cada uno) para escucharlos sin conexión. La voz del dispositivo ya funciona sin conexión.'**
  String get offlineAudioHint;

  /// No description provided for @offlineAudioStarted.
  ///
  /// In es, this message translates to:
  /// **'Descargando el audio de tus guardados… (puedes seguir usando la app)'**
  String get offlineAudioStarted;

  /// No description provided for @serverUnavailable.
  ///
  /// In es, this message translates to:
  /// **'El servidor no responde ahora mismo. Inténtalo en un rato.'**
  String get serverUnavailable;

  /// No description provided for @folderNowEmpty.
  ///
  /// In es, this message translates to:
  /// **'La carpeta «{name}» se ha quedado vacía. ¿Quieres borrarla? También puedes dejarla para fuentes que añadas más adelante.'**
  String folderNowEmpty(String name);

  /// No description provided for @keepFolder.
  ///
  /// In es, this message translates to:
  /// **'Mantener'**
  String get keepFolder;

  /// No description provided for @refresh.
  ///
  /// In es, this message translates to:
  /// **'Actualizar'**
  String get refresh;
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
