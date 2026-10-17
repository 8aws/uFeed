import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

/// A network picture decoded at the size it's drawn, not the size it was
/// published (feeds often ship 3000 px photos for an 84 px thumbnail; at full
/// size a list of them is hundreds of MB and iOS ends the app).
class NetImage extends StatelessWidget {
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
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, box) {
      final dpr = MediaQuery.devicePixelRatioOf(context);
      final w =
          width ??
          (box.hasBoundedWidth
              ? box.maxWidth
              : MediaQuery.sizeOf(context).width);
      // With `cover` in a box shorter than the picture's own shape (a square
      // thumbnail of a wide photo), the height decides: leave room for it.
      var base = height != null && height! > w ? height! : w;
      if (fit == BoxFit.cover && height != null) base *= 1.6;
      final px = (base * dpr).round().clamp(32, _maxPx);
      return CachedNetworkImage(
        imageUrl: url,
        width: width,
        height: height,
        fit: fit,
        memCacheWidth: px,
        errorListener: onError == null ? null : (_) => onError!(),
        errorWidget: (_, _, _) => error ?? const SizedBox.shrink(),
      );
    },
  );
}
