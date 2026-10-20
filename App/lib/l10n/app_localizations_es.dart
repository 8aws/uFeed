// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Spanish Castilian (`es`).
class AppLocalizationsEs extends AppLocalizations {
  AppLocalizationsEs([String locale = 'es']) : super(locale);

  @override
  String get appName => 'uFeed';

  @override
  String get all => 'Todo';

  @override
  String get unread => 'No leídos';

  @override
  String get saved => 'Guardados';

  @override
  String get favorites => 'Favoritos';

  @override
  String get folders => 'Carpetas';

  @override
  String get feeds => 'Fuentes';

  @override
  String get settings => 'Ajustes';

  @override
  String get logout => 'Cerrar sesión';

  @override
  String get login => 'Entrar';

  @override
  String get register => 'Crear cuenta';

  @override
  String get email => 'Correo';

  @override
  String get password => 'Contraseña';

  @override
  String get needAccount => '¿No tienes cuenta?';

  @override
  String get haveAccount => '¿Ya tienes cuenta?';

  @override
  String get loginFailed => 'Fallo al entrar. Revisa tus credenciales.';

  @override
  String get registerFailed => 'No se pudo crear la cuenta.';

  @override
  String get registrationClosed =>
      'El registro de cuentas está cerrado en este servidor.';

  @override
  String get passwordTooShort => 'Mínimo 8 caracteres.';

  @override
  String get forgotPassword => '¿Has olvidado la contraseña?';

  @override
  String get forgotHint =>
      'Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una nueva contraseña.';

  @override
  String get sendResetLink => 'Enviar enlace';

  @override
  String get resetSent =>
      'Si ese correo tiene cuenta en uFeed, te hemos enviado un enlace (válido 1 hora). Revisa también el correo no deseado.';

  @override
  String get tryLater => 'Demasiados intentos; prueba más tarde.';

  @override
  String get backToLogin => 'Volver a entrar';

  @override
  String get noArticles => 'Aún no hay nada aquí.';

  @override
  String get noUnreadHere => 'No hay nada sin leer aquí.';

  @override
  String get loading => 'Cargando…';

  @override
  String get offline => 'Sin conexión con el servidor.';

  @override
  String get retry => 'Reintentar';

  @override
  String get markAllRead => 'Marcar todo leído';

  @override
  String get markRead => 'Marcar leído';

  @override
  String get markUnread => 'Marcar no leído';

  @override
  String get save => 'Guardar';

  @override
  String get unsave => 'Quitar';

  @override
  String get favorite => 'Favorito';

  @override
  String get unfavorite => 'Quitar favorito';

  @override
  String get trending => 'Tendencias';

  @override
  String get forYou => 'Para ti';

  @override
  String get openOriginal => 'Abrir original';

  @override
  String get share => 'Compartir';

  @override
  String minutesAgo(int n) {
    return '$n min';
  }

  @override
  String hoursAgo(int n) {
    return '$n h';
  }

  @override
  String daysAgo(int n) {
    return '$n d';
  }

  @override
  String readingMinutes(int n) {
    return '$n min de lectura';
  }

  @override
  String get listen => 'Escuchar';

  @override
  String get listenPreparing => 'Preparando audio…';

  @override
  String get listenPlan => 'Tu plan no incluye la voz del servidor.';

  @override
  String get listenRateLimited =>
      'Demasiadas peticiones de audio esta hora; prueba más tarde.';

  @override
  String get listenUnavailable =>
      'La voz del servidor no está disponible ahora.';

  @override
  String get listenLangUnsupported =>
      'No hay voz de servidor para el idioma de este artículo.';

  @override
  String get view => 'Vista';

  @override
  String get viewList => 'Lista';

  @override
  String get viewCardList => 'Lista de tarjetas';

  @override
  String get viewCards => 'Tarjetas';

  @override
  String get viewMasonry => 'Mosaico';

  @override
  String get showAllPosts => 'Ver también los leídos';

  @override
  String readers(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n lectores',
      one: '1 lector',
    );
    return '$_temp0';
  }

  @override
  String get trendingNow => 'Tendencia ahora';

  @override
  String get top => 'Top';

  @override
  String get mostSaved => 'Más guardados';

  @override
  String get deepReads => 'Lecturas profundas';

  @override
  String get hiddenGems => 'Joyas ocultas';

  @override
  String get by => 'por';

  @override
  String get planLimitAi => 'Tu plan no incluye funciones de IA.';

  @override
  String get aiGenerating => 'Generando…';

  @override
  String aiQueued(int n) {
    return 'En cola, puesto $n';
  }

  @override
  String get aiFailed =>
      'No se pudo generar el resumen. Pulsa la barra para reintentar.';

  @override
  String get aiDailyLimit =>
      'Has usado los resúmenes IA de hoy. Los que ya existen siguen disponibles.';

  @override
  String get aiSummary => 'Resumen IA';

  @override
  String get aiUnavailable => 'La IA no está disponible ahora.';

  @override
  String get aiRate => 'Demasiados resúmenes IA esta hora; prueba más tarde.';

  @override
  String get translate => 'Traducir';

  @override
  String get translating => 'Traduciendo…';

  @override
  String get showOriginal => 'Ver original';

  @override
  String get machineTranslation => 'Traducción automática';

  @override
  String get translateUnavailable => 'La traducción no está disponible ahora.';

  @override
  String get textSize => 'Tamaño del texto';

  @override
  String get font => 'Tipo de letra';

  @override
  String get fontSystem => 'Del sistema';

  @override
  String get fullArticle => 'Artículo completo';

  @override
  String get showExcerpt => 'Extracto del feed';

  @override
  String get fullLoading => 'Cargando el artículo completo…';

  @override
  String get fullNote => 'Artículo completo desde la web';

  @override
  String get fullUnavailable =>
      'No se pudo cargar el artículo completo desde la web.';

  @override
  String get autoFull =>
      'Cargar el artículo completo cuando la fuente solo da un extracto';

  @override
  String get similar => 'Similares';

  @override
  String get more => 'Más';

  @override
  String get offlineBanner =>
      'Sin conexión: mostrando la copia guardada en el dispositivo.';

  @override
  String pendingSync(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n cambios pendientes de sincronizar',
      one: '1 cambio pendiente de sincronizar',
    );
    return '$_temp0';
  }

  @override
  String get listenDevice => 'Dispositivo';

  @override
  String get listenServer => 'Servidor';

  @override
  String get listenSpeed => 'Velocidad';

  @override
  String get serverVoice => 'Voz del servidor';

  @override
  String get voiceFemale => 'Femenina';

  @override
  String get voiceMale => 'Masculina';

  @override
  String get deviceVoice => 'Voz del dispositivo';

  @override
  String get deviceVoiceHint =>
      'En iPhone, descarga las voces «Mejorada» o «Premium» (Ajustes → Accesibilidad → Contenido leído) para un sonido mucho mejor.';

  @override
  String get serverVoiceHint =>
      'Voz neuronal generada en el servidor: suena igual en todos tus dispositivos.';

  @override
  String get autoRead => 'Leer los artículos en voz alta al abrirlos';

  @override
  String get readMyLang => 'Leer siempre en mi idioma';

  @override
  String get readMyLangHint =>
      'Los artículos en otro idioma (inglés ↔ español) se traducen antes de leerlos.';

  @override
  String get speechEngine => 'Voz preferida';

  @override
  String get postRadio => 'Post radio';

  @override
  String get postRadioStart => 'Post radio: escuchar esta lista';

  @override
  String get radioNext => 'Siguiente post';

  @override
  String get radioStop => 'Parar la radio';

  @override
  String get radioHint =>
      'Lee los posts de la lista uno tras otro, con un breve sonido entre ellos. Un post solo se marca como leído si se ha escuchado al menos el 70 %.';

  @override
  String get radioStopAfter => 'Parar tras';

  @override
  String get radioPosts => 'posts';

  @override
  String get radioMinutes => 'min';

  @override
  String get radioDone => 'Post radio terminada';

  @override
  String get radioUnlimited => 'sin límite';

  @override
  String radioPosition(int n, int total) {
    return 'Post $n de $total';
  }

  @override
  String sentence(int n, int total) {
    return 'Frase $n de $total';
  }

  @override
  String get voiceSettings => 'Voz y lectura';

  @override
  String get back15 => 'Atrás 10 s';

  @override
  String get forward15 => 'Adelante 10 s';

  @override
  String get play => 'Reproducir';

  @override
  String get pause => 'Pausa';

  @override
  String get stop => 'Parar';

  @override
  String get listenGenerating => 'generando';

  @override
  String get addFeed => 'Añadir fuente';

  @override
  String get addFeedPlaceholder => 'URL del blog o feed…';

  @override
  String get discover => 'Buscar feeds';

  @override
  String get subscribe => 'Suscribirse';

  @override
  String get subscribed => 'Suscrito';

  @override
  String get noFeedsFound => 'No se encontraron feeds en esa URL.';

  @override
  String get unsubscribe => 'Cancelar suscripción';

  @override
  String get confirmUnsubscribe => '¿Cancelar la suscripción a esta fuente?';

  @override
  String get importOpml => 'Importar OPML';

  @override
  String get exportOpml => 'Exportar OPML';

  @override
  String opmlImported(int n, int m) {
    return '$n fuentes importadas, $m omitidas.';
  }

  @override
  String get account => 'Cuenta';

  @override
  String get starterSources => 'Sugerencias iniciales';

  @override
  String get catalogAdd => 'Añadir';

  @override
  String get catalogRemove => 'Quitar';

  @override
  String get catalogAddAll => 'Añadir todas';

  @override
  String get allLangs => 'Todas';

  @override
  String get langEs => 'Español';

  @override
  String get langEn => 'Inglés';

  @override
  String get plan => 'Plan';

  @override
  String get roleFree => 'Gratis';

  @override
  String get roleGeneral => 'General';

  @override
  String get roleVip => 'VIP';

  @override
  String get roleEditor => 'Editor';

  @override
  String get roleAdmin => 'Administrador';

  @override
  String get admin => 'Administración';

  @override
  String get curation => 'Curación';

  @override
  String get privacy => 'Privacidad';

  @override
  String get support => 'Soporte';

  @override
  String get currentPassword => 'Contraseña actual';

  @override
  String get newPassword => 'Nueva contraseña';

  @override
  String get confirmPassword => 'Repite la nueva contraseña';

  @override
  String get changePassword => 'Cambiar contraseña';

  @override
  String get passwordChanged =>
      'Contraseña cambiada. Se ha cerrado la sesión en otros dispositivos.';

  @override
  String get passwordMismatch => 'Las contraseñas no coinciden.';

  @override
  String get wrongPassword => 'La contraseña actual no es correcta.';

  @override
  String get deleteAccount => 'Eliminar cuenta';

  @override
  String get deleteAccountHint =>
      'Borra tu cuenta y todos sus datos (fuentes, carpetas, guardados, claves). No se puede deshacer. Escribe tu contraseña para confirmar.';

  @override
  String get digestTitle => 'Resumen diario por correo';

  @override
  String get digestHint =>
      'Lo más relevante de las últimas 24 horas en tus fuentes, una vez al día.';

  @override
  String get digestOff => 'Desactivado';

  @override
  String get digestAt => 'A las';

  @override
  String get digestEveryDay => 'Todos los días';

  @override
  String get digestWeekdays => 'Laborables (L–V)';

  @override
  String get digestWeekends => 'Fin de semana';

  @override
  String get digestCustom => 'Elegir días';

  @override
  String get digestDayLetters => 'L,M,X,J,V,S,D';

  @override
  String get mute => 'Silenciar';

  @override
  String get unmute => 'Quitar silencio';

  @override
  String get filters => 'Filtros';

  @override
  String get filtersHint =>
      'Oculta los artículos cuyo título o resumen contenga estas palabras. Guardados y favoritos nunca se ocultan.';

  @override
  String get addKeyword => 'Añade una palabra o frase…';

  @override
  String get mutedSources => 'Fuentes silenciadas';

  @override
  String get mutedSourcesHint =>
      'No aparecen en No leídos, Todo, carpetas ni recomendaciones; abre la fuente para leerla.';

  @override
  String get noMuted => 'Nada silenciado.';

  @override
  String get planLimitFeeds => 'Has llegado al límite de fuentes de tu plan.';

  @override
  String get appearance => 'Apariencia';

  @override
  String get deleteFolder => 'Eliminar carpeta';

  @override
  String get confirmDeleteFolder =>
      '¿Eliminar esta carpeta? Sus fuentes pasan a la raíz.';

  @override
  String get newFolder => 'Nueva carpeta';

  @override
  String get noFolder => 'Sin carpeta';

  @override
  String get rename => 'Cambiar nombre';

  @override
  String get moveTo => 'Mover a carpeta';

  @override
  String get name => 'Nombre';

  @override
  String get cancel => 'Cancelar';

  @override
  String get delete => 'Eliminar';

  @override
  String get done => 'Hecho';

  @override
  String get feedsAndFolders => 'Fuentes y carpetas';

  @override
  String get somethingFailed => 'No se pudo completar. Inténtalo de nuevo.';

  @override
  String get web => 'Abrir en la web';

  @override
  String get demoAccount =>
      'La cuenta de demostración no se puede cambiar ni eliminar.';

  @override
  String get lastAdmin =>
      'Nombra a otra persona administradora antes de eliminar esta cuenta.';

  @override
  String get settingsMenu => 'Ajustes';

  @override
  String get confirmMarkAllRead =>
      '¿Marcar como leídos todos los artículos de esta vista?';

  @override
  String newItems(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n artículos nuevos',
      one: '1 artículo nuevo',
    );
    return '$_temp0';
  }

  @override
  String get noNew => 'Sin novedades';

  @override
  String refreshWait(int n) {
    return 'Disponible en $n min';
  }

  @override
  String get offlineAudio => 'Audio sin conexión de los guardados';

  @override
  String get offlineAudioHint =>
      'Guarda en este iPhone la voz del servidor de tus 20 últimos artículos guardados (~1,5 MB cada uno) para escucharlos sin conexión. La voz del dispositivo ya funciona sin conexión.';

  @override
  String get offlineAudioStarted =>
      'Descargando el audio de tus guardados… (puedes seguir usando la app)';

  @override
  String get serverUnavailable =>
      'El servidor no responde ahora mismo. Inténtalo en un rato.';

  @override
  String folderNowEmpty(String name) {
    return 'La carpeta «$name» se ha quedado vacía. ¿Quieres borrarla? También puedes dejarla para fuentes que añadas más adelante.';
  }

  @override
  String get keepFolder => 'Mantener';

  @override
  String get refresh => 'Actualizar';

  @override
  String get roleGuest => 'Invitado';

  @override
  String get continueWithoutAccount => 'Continuar sin cuenta';

  @override
  String get guestIntro =>
      'Lee y organiza tus fuentes sin registrarte. Cuando quieras la IA, la voz del servidor o usar tus datos en otros dispositivos, crea una cuenta.';

  @override
  String get guestTitle => 'Estás usando uFeed sin cuenta';

  @override
  String get guestBody =>
      'Tus fuentes y guardados están solo en este perfil de invitado. Crea una cuenta para conservarlos, usarlos en otros dispositivos y activar la IA y la voz del servidor.';

  @override
  String get guestUpgrade => 'Crear cuenta con mis datos';

  @override
  String get guestLeave => 'Salir y borrar mis datos';

  @override
  String get guestLeaveHint =>
      'Se borrarán las fuentes y guardados de este perfil de invitado. No se puede deshacer.';

  @override
  String get guestNeedsAccount => 'Crea una cuenta para usar esta función.';

  @override
  String get planLimitFeedsGuest =>
      'Has llegado al límite de fuentes sin cuenta. Crea una cuenta para añadir más.';

  @override
  String get accountCreated => 'Cuenta creada';

  @override
  String get emailTaken =>
      'Ese correo ya tiene una cuenta. Inicia sesión con él desde la pantalla de acceso.';

  @override
  String get selectArticle => 'Elige un artículo de la lista';

  @override
  String get plansAndLimits => 'Planes y límites';

  @override
  String get themeSystem => 'Sistema';

  @override
  String get themeLight => 'Claro';

  @override
  String get themeDark => 'Oscuro';

  @override
  String get foldFolder => 'Plegar carpeta';

  @override
  String get unfoldFolder => 'Desplegar carpeta';

  @override
  String get twinsTitle => 'Más sobre esta noticia';

  @override
  String get twinsInYours => 'En tus fuentes';

  @override
  String get twinsElsewhere => 'En fuentes que no sigues';

  @override
  String get twinsNote =>
      'No cuentan en tus no leídos mientras no sigas la fuente.';

  @override
  String get twinsNone => 'No hay más copias.';

  @override
  String get openOnSite => 'Abrir en su web';

  @override
  String get followThisFeed => 'Seguir esta fuente';

  @override
  String get feedAdded => 'Fuente añadida';
}
