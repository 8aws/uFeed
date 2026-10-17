import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

/// A network picture decoded at the size it's drawn, not the size it was
/// published (feeds often ship 3000 px photos for an 84 px thumbnail; at full
/// size a list of them is hundreds of MB and iOS ends the app).
class NetImage extends StatefulWidget {
  const NetImage(
    this.url, {
    super.key,
    this.width,
    this.height,
    this.fit = BoxFit.cover,
    this.error,
    this.onError,
  });

  final String url;
  final double? width;
  final double? height;
  final BoxFit fit;

  /// Shown when the picture can't be loaded (nothing by default).
  final Widget? error;

  /// Called (once the load has failed) so the parent can drop the empty space.
  final VoidCallback? onError;

  /// Never decode wider than this, whatever the screen (a full-width
  /// picture on an iPad is about this many pixels).
  static const _maxPx = 1600;

  @override
  State<NetImage> createState() => _NetImageState();
}

class _NetImageState extends State<NetImage> {
  /// How many times it has been asked again after failing (a slow or dropped
  /// connection, not a broken picture): after 2 s, then 6 s; only then does it
  /// give up and tell the parent.
  int _attempt = 0;
  static const _waits = [Duration(seconds: 2), Duration(seconds: 6)];

  void _failed() {
    if (!mounted) return;
    if (_attempt >= _waits.length) {
      widget.onError?.call();
      return;
    }
    final wait = _waits[_attempt];
    Future<void>.delayed(wait, () {
      if (mounted) setState(() => _attempt++);
    });
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, box) {
      final dpr = MediaQuery.devicePixelRatioOf(context);
      final w =
          widget.width ??
          (box.hasBoundedWidth
              ? box.maxWidth
              : MediaQuery.sizeOf(context).width);
      // With `cover` in a box shorter than the picture's own shape (a square
      // thumbnail of a wide photo), the height decides: leave room for it.
      final h = widget.height;
      var base = h != null && h > w ? h : w;
      if (widget.fit == BoxFit.cover && h != null) base *= 1.6;
      final px = (base * dpr).round().clamp(32, NetImage._maxPx);
      return CachedNetworkImage(
        // A new key per attempt asks for the picture again.
        key: ValueKey(_attempt),
        imageUrl: widget.url,
        width: widget.width,
        height: widget.height,
        fit: widget.fit,
        memCacheWidth: px,
        errorListener: (_) => _failed(),
        errorWidget: (_, _, _) => widget.error ?? const SizedBox.shrink(),
      );
    },
  );
}
