import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/api/models.dart';
import 'package:ufeed/core/prefs.dart';
import 'package:ufeed/listen/listen_controller.dart';

Article _a(String id) => Article.fromJson({
  'id': id,
  'source_id': 's',
  'is_read': false,
  'is_saved': false,
  'is_favorite': false,
});

void main() {
  test('speech prefs survive a round trip', () {
    const p = SpeechPrefs(server: true, gender: 'm', rate: 1.25, radioPosts: 0);
    final back = SpeechPrefs.fromJson(p.toJson());
    expect(back.server, isTrue);
    expect(back.gender, 'm');
    expect(back.rate, 1.25);
    expect(back.radioPosts, 0);
    expect(back.radioMinutes, 30);
  });

  test('radio length follows the post limit and the list', () {
    final queue = [for (var i = 0; i < 4; i++) _a('a$i')];
    final now = DateTime(2026);
    expect(
      RadioSession(queue: queue, pos: 0, startedAt: now, maxPosts: 10).total,
      4,
    );
    expect(
      RadioSession(queue: queue, pos: 0, startedAt: now, maxPosts: 2).total,
      2,
    );
    expect(RadioSession(queue: queue, pos: 0, startedAt: now).total, 4);
  });

  test('plan limits from the site config', () {
    final site = SiteConfig.fromJson({
      'registration_open': true,
      'plan_limits': {
        'general': {
          'tts_server': true,
          'post_radio': true,
          'radio_max_posts': 5,
          'radio_max_minutes': 20,
        },
        'free': {'tts_server': false},
      },
    });
    expect(site.planLimits[Role.general]!.radioMaxPosts, 5);
    expect(site.planLimits[Role.free]!.postRadio, isFalse);
  });
}
