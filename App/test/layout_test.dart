import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ufeed/core/layout.dart';

Future<bool> _twoPane(WidgetTester tester, double w, double h) async {
  late bool result;
  await tester.pumpWidget(
    MediaQuery(
      data: MediaQueryData(size: Size(w, h)),
      child: Builder(
        builder: (context) {
          result = useTwoPane(context);
          return const SizedBox();
        },
      ),
    ),
  );
  return result;
}

void main() {
  testWidgets(
    'list and article go side by side only in landscape on big screens',
    (tester) async {
      // iPhone Duo open: portrait as it is now, landscape like a desktop.
      expect(await _twoPane(tester, 669, 951), isFalse);
      expect(await _twoPane(tester, 951, 669), isTrue);
      // iPad (13"): portrait and landscape.
      expect(await _twoPane(tester, 1032, 1376), isFalse);
      expect(await _twoPane(tester, 1376, 1032), isTrue);
      // A Mac window, narrow and wide.
      expect(await _twoPane(tester, 600, 800), isFalse);
      expect(await _twoPane(tester, 1100, 760), isTrue);
      // Phones, even sideways, keep one pane.
      expect(await _twoPane(tester, 393, 852), isFalse);
      expect(await _twoPane(tester, 932, 430), isFalse);
    },
  );

  test('masonry columns grow with the room, phones keep two', () {
    expect(masonryColumns(375), 2);
    expect(masonryColumns(430), 2);
    expect(masonryColumns(669), 3);
    expect(masonryColumns(1032), 4);
    expect(masonryColumns(2000), 5);
  });

  test('the list pane stays between 340 and 460 points', () {
    expect(listPaneWidth(700), 340);
    expect(listPaneWidth(951), closeTo(361.4, 0.1));
    expect(listPaneWidth(1600), 460);
  });
}
