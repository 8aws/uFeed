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
}
