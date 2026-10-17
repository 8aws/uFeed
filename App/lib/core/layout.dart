import 'package:flutter/widgets.dart';

/// For trying the layout in a simulator that can't be rotated
/// (`--dart-define=UFEED_TWOPANE=true`).
const _forceTwoPane = bool.fromEnvironment('UFEED_TWOPANE');

/// Landscape on a screen big enough (iPad, Mac window, iPhone Duo open): the
/// list and the open article go side by side, like a desktop reader. In
/// portrait, and on phones (even in landscape: they are too short), the list
/// and the article take turns.
bool useTwoPane(BuildContext context) {
  final s = MediaQuery.sizeOf(context);
  if (_forceTwoPane) return s.width >= 700;
  return s.width > s.height && s.width >= 700 && s.height >= 560;
}

/// Width of the list pane when it's beside the article.
double listPaneWidth(double total) => (total * 0.38).clamp(340, 460);

/// How many columns the masonry list gets in `width` points: 2 on phones, more
/// where there is room (about 220 points each).
int masonryColumns(double width) =>
    width < 500 ? 2 : (width / 220).floor().clamp(2, 5);

/// Reading text stops getting wider than this, however big the pane.
const readingWidth = 720.0;

/// Keeps a screen of rows (settings, add a feed…) to a comfortable width,
/// centred, when the window is much wider than a phone.
class CenteredColumn extends StatelessWidget {
  const CenteredColumn({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: readingWidth),
      child: child,
    ),
  );
}
