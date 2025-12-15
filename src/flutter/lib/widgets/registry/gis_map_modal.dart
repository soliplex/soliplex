import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import 'package:soliplex/widgets/registry/gis_card_widget.dart';

/// Modal dialog with an interactive OpenStreetMap view.
///
/// Shows one or more locations with markers and optional accuracy circles.
/// Supports pan and zoom interactions.
class GISMapModal extends StatelessWidget {
  const GISMapModal({
    required this.coordinates,
    super.key,
    this.initialZoom = 15,
    this.title,
    this.showAccuracyCircle = true,
  });
  final List<GISCoordinate> coordinates;
  final double initialZoom;
  final String? title;
  final bool showAccuracyCircle;

  /// Calculate the center point of all coordinates.
  LatLng get _center {
    if (coordinates.isEmpty) return const LatLng(0, 0);
    if (coordinates.length == 1) return coordinates.first.toLatLng();

    double sumLat = 0;
    double sumLng = 0;
    for (final coord in coordinates) {
      sumLat += coord.latitude;
      sumLng += coord.longitude;
    }
    return LatLng(sumLat / coordinates.length, sumLng / coordinates.length);
  }

  /// Calculate bounds that contain all coordinates with padding.
  LatLngBounds? get _bounds {
    if (coordinates.isEmpty) return null;
    if (coordinates.length == 1) {
      return null; // Use center/zoom for single point
    }

    var minLat = coordinates.first.latitude;
    var maxLat = coordinates.first.latitude;
    var minLng = coordinates.first.longitude;
    var maxLng = coordinates.first.longitude;

    for (final coord in coordinates) {
      if (coord.latitude < minLat) minLat = coord.latitude;
      if (coord.latitude > maxLat) maxLat = coord.latitude;
      if (coord.longitude < minLng) minLng = coord.longitude;
      if (coord.longitude > maxLng) maxLng = coord.longitude;
    }

    return LatLngBounds(LatLng(minLat, minLng), LatLng(maxLat, maxLng));
  }

  @override
  Widget build(BuildContext context) {
    final center = _center;
    final pointCount = coordinates.length;
    final first = coordinates.isNotEmpty ? coordinates.first : null;

    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
              ),
              child: Row(
                children: [
                  Icon(Icons.map, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      title ?? (pointCount > 1 ? 'Locations' : 'Location'),
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(),
                    tooltip: 'Close',
                  ),
                ],
              ),
            ),
            // Map
            SizedBox(
              height: MediaQuery.of(context).size.height * 0.6,
              width: MediaQuery.of(context).size.width * 0.9,
              child: FlutterMap(
                options: _bounds != null
                    ? MapOptions(
                        initialCameraFit: CameraFit.bounds(
                          bounds: _bounds!,
                          padding: const EdgeInsets.all(50),
                        ),
                      )
                    : MapOptions(
                        initialCenter: center,
                        initialZoom: initialZoom,
                      ),
                children: [
                  // OpenStreetMap tiles
                  TileLayer(
                    urlTemplate:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName: 'com.example.agui_dash_2',
                  ),
                  // Accuracy circles
                  if (showAccuracyCircle)
                    CircleLayer(
                      circles: coordinates
                          .where((c) => c.accuracy != null && c.accuracy! > 0)
                          .map(
                            (c) => CircleMarker(
                              point: c.toLatLng(),
                              radius: c.accuracy!,
                              useRadiusInMeter: true,
                              color: (c.color ?? Colors.blue).withAlpha(40),
                              borderColor: (c.color ?? Colors.blue).withAlpha(
                                150,
                              ),
                              borderStrokeWidth: 2,
                            ),
                          )
                          .toList(),
                    ),
                  // Location markers
                  MarkerLayer(
                    markers: coordinates
                        .map(
                          (c) => Marker(
                            point: c.toLatLng(),
                            width: 40,
                            height: 40,
                            child: Icon(
                              Icons.location_on,
                              color: c.color ?? Colors.red,
                              size: 40,
                            ),
                          ),
                        )
                        .toList(),
                  ),
                ],
              ),
            ),
            // Coordinates footer
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.my_location,
                    size: 16,
                    color: Colors.grey.shade600,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    pointCount > 1
                        ? '$pointCount points'
                        : first != null
                        // ignore: lines_longer_than_80_chars (auto-documented)
                        ? '${first.latitude.toStringAsFixed(6)}, ${first.longitude.toStringAsFixed(6)}'
                        : 'No coordinates',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontFamily: 'monospace',
                      color: Colors.grey.shade700,
                    ),
                  ),
                  if (pointCount == 1 && first?.accuracy != null) ...[
                    const SizedBox(width: 16),
                    Icon(
                      Icons.gps_fixed,
                      size: 16,
                      color: Colors.grey.shade600,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '±${first!.accuracy!.toStringAsFixed(1)}m',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.grey.shade700,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
