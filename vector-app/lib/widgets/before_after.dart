import 'package:flutter/material.dart';

/// Swipe-divider comparison: [before] underneath, [after] revealed from the left.
class BeforeAfter extends StatefulWidget {
  final Widget before;
  final Widget after;

  const BeforeAfter({super.key, required this.before, required this.after});

  @override
  State<BeforeAfter> createState() => _BeforeAfterState();
}

class _BeforeAfterState extends State<BeforeAfter> {
  double _fraction = 0.5;

  @override
  Widget build(BuildContext context) {
    final divider = Theme.of(context).colorScheme.primary;
    return LayoutBuilder(builder: (context, constraints) {
      final w = constraints.maxWidth;
      return GestureDetector(
        onHorizontalDragUpdate: (d) => setState(() {
          _fraction = (d.localPosition.dx / w).clamp(0.02, 0.98);
        }),
        onTapDown: (d) => setState(() {
          _fraction = (d.localPosition.dx / w).clamp(0.02, 0.98);
        }),
        child: Stack(
          fit: StackFit.expand,
          children: [
            widget.before,
            ClipRect(
              clipper: _LeftClipper(_fraction),
              child: widget.after,
            ),
            Positioned(
              left: w * _fraction - 1,
              top: 0,
              bottom: 0,
              child: Container(width: 2, color: divider),
            ),
            Positioned(
              left: w * _fraction - 16,
              top: constraints.maxHeight / 2 - 16,
              child: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: divider,
                  shape: BoxShape.circle,
                  boxShadow: const [
                    BoxShadow(color: Colors.black38, blurRadius: 6)
                  ],
                ),
                child: const Icon(Icons.unfold_more,
                    size: 18, color: Colors.white),
              ),
            ),
            Positioned(
              left: 8,
              top: 8,
              child: _label(context, 'VECTOR'),
            ),
            Positioned(
              right: 8,
              top: 8,
              child: _label(context, 'ORIGINAL'),
            ),
          ],
        ),
      );
    });
  }

  Widget _label(BuildContext context, String text) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: Colors.black54,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(text,
            style: const TextStyle(
                color: Colors.white,
                fontSize: 10,
                fontWeight: FontWeight.w600,
                letterSpacing: 1.2)),
      );
}

class _LeftClipper extends CustomClipper<Rect> {
  final double fraction;
  _LeftClipper(this.fraction);

  @override
  Rect getClip(Size size) => Rect.fromLTWH(0, 0, size.width * fraction, size.height);

  @override
  bool shouldReclip(_LeftClipper old) => old.fraction != fraction;
}
