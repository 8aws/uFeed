// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'uFeed';

  @override
  String get all => 'All';

  @override
  String get unread => 'Unread';

  @override
  String get saved => 'Saved';

  @override
  String get favorites => 'Favorites';

  @override
  String get folders => 'Folders';

  @override
  String get feeds => 'Feeds';

  @override
  String get settings => 'Settings';

  @override
  String get logout => 'Sign out';

  @override
  String get login => 'Sign in';

  @override
  String get register => 'Create account';

  @override
  String get email => 'Email';

  @override
  String get password => 'Password';

  @override
  String get needAccount => 'No account yet?';

  @override
  String get haveAccount => 'Already have an account?';

  @override
  String get loginFailed => 'Sign-in failed. Check your credentials.';

  @override
  String get registerFailed => 'Could not create the account.';

  @override
  String get registrationClosed => 'Registration is closed on this server.';

  @override
  String get passwordTooShort => 'At least 8 characters.';

  @override
  String get forgotPassword => 'Forgot your password?';

  @override
  String get forgotHint =>
      'Enter your account email and we\'ll send you a link to choose a new password.';

  @override
  String get sendResetLink => 'Send link';

  @override
  String get resetSent =>
      'If that email has a uFeed account, we\'ve sent you a link (valid for 1 hour). Check your spam folder too.';

  @override
  String get tryLater => 'Too many attempts; try again later.';

  @override
  String get backToLogin => 'Back to sign in';

  @override
  String get noArticles => 'Nothing here yet.';

  @override
  String get noUnreadHere => 'Nothing unread here.';

  @override
  String get loading => 'Loading…';

  @override
  String get offline => 'Can\'t reach the server.';

  @override
  String get retry => 'Retry';

  @override
  String get markAllRead => 'Mark all read';

  @override
  String get markRead => 'Mark read';

  @override
  String get markUnread => 'Mark unread';

  @override
  String get save => 'Save';

  @override
  String get unsave => 'Remove';

  @override
  String get favorite => 'Favorite';

  @override
  String get unfavorite => 'Unfavorite';

  @override
  String get trending => 'Trending';

  @override
  String get forYou => 'For you';

  @override
  String get openOriginal => 'Open original';

  @override
  String get share => 'Share';

  @override
  String minutesAgo(int n) {
    return '${n}m';
  }

  @override
  String hoursAgo(int n) {
    return '${n}h';
  }

  @override
  String daysAgo(int n) {
    return '${n}d';
  }

  @override
  String readingMinutes(int n) {
    return '$n min read';
  }

  @override
  String get listen => 'Listen';

  @override
  String get listenPreparing => 'Preparing audio…';

  @override
  String get listenPlan => 'Your plan doesn\'t include the server voice.';

  @override
  String get listenRateLimited =>
      'Too many audio requests this hour; try again later.';

  @override
  String get listenUnavailable =>
      'The server voice isn\'t available right now.';

  @override
  String get listenLangUnsupported =>
      'No server voice for this article\'s language.';

  @override
  String get view => 'View';

  @override
  String get viewList => 'List';

  @override
  String get viewCardList => 'Card list';

  @override
  String get viewCards => 'Cards';

  @override
  String get viewMasonry => 'Masonry';

  @override
  String get showAllPosts => 'Show read posts too';

  @override
  String readers(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n readers',
      one: '1 reader',
    );
    return '$_temp0';
  }

  @override
  String get trendingNow => 'Trending now';

  @override
  String get top => 'Top';

  @override
  String get mostSaved => 'Most saved';

  @override
  String get deepReads => 'Deep reads';

  @override
  String get hiddenGems => 'Hidden gems';
}
