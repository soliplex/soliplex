import 'dart:math';

import 'package:flutter/material.dart';

class BackgroundImageStack extends StatelessWidget {
  const BackgroundImageStack({
    required this.image,
    this.top,
    this.bottom,
    this.opacity = 0.04,
    required this.child,
    super.key,
  });

  final ImageProvider<Object> image;
  final double? top;
  final double? bottom;
  final double opacity;
  final Widget child;
  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final screenHeight = MediaQuery.of(context).size.height;

    final dimensions = min(screenWidth, screenHeight);

    return Stack(
      alignment: Alignment.center,
      children: [
        (top != null || bottom != null)
            ? Positioned(
                top: top,
                bottom: bottom,
                child: BGImageContainer(
                  dimensions: dimensions,
                  image: image,
                  opacity: opacity,
                ),
              )
            : BGImageContainer(
                dimensions: dimensions,
                image: image,
                opacity: opacity,
              ),
        child,
      ],
    );
  }
}

class BGImageContainer extends StatelessWidget {
  const BGImageContainer({
    super.key,
    required this.dimensions,
    required this.image,
    required this.opacity,
  });

  final double dimensions;
  final ImageProvider<Object> image;
  final double opacity;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: dimensions < 600 ? dimensions / 2 : 300,
      width: dimensions < 600 ? dimensions / 2 : 300,
      decoration: BoxDecoration(
        color: Colors.transparent,
        image: DecorationImage(
          image: image,
          opacity: opacity,
          fit: BoxFit.scaleDown,
        ),
      ),
    );
  }
}
