import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import 'package:soliplex/widgets/registry/gis_map_modal.dart';
import 'package:soliplex/widgets/registry/widget_utils.dart';

/// Represents a single GIS coordinate point with optional metadata.
class GISCoordinate {
  const GISCoordinate({
    required this.latitude,
    required this.longitude,
    this.accuracy,
    this.label,
    this.color,
  });

  factory GISCoordinate.fromMap(Map<String, dynamic> data) {
    return GISCoordinate(
      latitude: parseDouble(data['latitude']) ?? 0.0,
      longitude: parseDouble(data['longitude']) ?? 0.0,
      accuracy: parseDouble(data['accuracy']),
      label: data['label'] as String?,
      color: parseColor(data['color']),
    );
  }
  final double latitude;
  final double longitude;
  final double? accuracy;
  final String? label;
  final Color? color;

  LatLng toLatLng() => LatLng(latitude, longitude);
}

/// GIS Card widget for displaying one or more locations on an OpenStreetMap.
///
/// Shows a static map thumbnail in the chat that opens an interactive
/// map modal when tapped. Supports multiple coordinate points.
class GISCardWidget extends StatelessWidget {
  const GISCardWidget({
    required this.coordinates,
    super.key,
    this.zoom = 15,
    this.title,
    this.showAccuracyCircle = true,
    this.onTap,
  });

  /// Create from JSON data.
  ///
  /// Supports two formats:
  ///
  /// Single coordinate (legacy):
  /// ```json
  /// {
  ///   "latitude": 37.7749,
  ///   "longitude": -122.4194,
  ///   "accuracy": 10.0,
  ///   "zoom": 15,
  ///   "title": "Your Location",
  ///   "showAccuracyCircle": true
  /// }
  /// ```
  ///
  /// Multiple coordinates:
  /// ```json
  /// {
  ///   "coordinates": [
  /// {"latitude": 37.7749, "longitude": -122.4194, "label": "SF", "color":
  /// "#FF0000"},
  /// {"latitude": 34.0522, "longitude": -118.2437, "label": "LA", "color":
  /// "#00FF00"}
  ///   ],
  ///   "zoom": 10,
  ///   "title": "Cities",
  ///   "showAccuracyCircle": true
  /// }
  /// ```
  factory GISCardWidget.fromData(
    Map<String, dynamic> data,
    void Function(String, Map<String, dynamic>)? onEvent,
  ) {
    List<GISCoordinate> coords;

    if (data.containsKey('coordinates') && data['coordinates'] is List) {
      // Multiple coordinates format
      final coordList = data['coordinates'] as List;
      coords = coordList
          .map((c) => GISCoordinate.fromMap(c as Map<String, dynamic>))
          .toList();
    } else {
      // Legacy single coordinate format
      coords = [
        GISCoordinate(
          latitude: parseDouble(data['latitude']) ?? 0.0,
          longitude: parseDouble(data['longitude']) ?? 0.0,
          accuracy: parseDouble(data['accuracy']),
          label: data['label'] as String?,
        ),
      ];
    }

    return GISCardWidget(
      coordinates: coords,
      zoom: parseDouble(data['zoom']) ?? 15.0,
      title: data['title'] as String?,
      showAccuracyCircle: data['showAccuracyCircle'] as bool? ?? true,
      onTap: onEvent != null
          ? () => onEvent('tap', {
              'coordinates': coords
                  .map(
                    (c) => {'latitude': c.latitude, 'longitude': c.longitude},
                  )
                  .toList(),
            })
          : null,
    );
  }
  final List<GISCoordinate> coordinates;
  final double zoom;
  final String? title;
  final bool showAccuracyCircle;
  final VoidCallback? onTap;

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

  /// Get the first coordinate (for backwards compatibility in display).
  GISCoordinate? get _firstCoordinate =>
      coordinates.isNotEmpty ? coordinates.first : null;

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

  void _openMapModal(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (context) => GISMapModal(
        coordinates: coordinates,
        initialZoom: zoom,
        title: title,
        showAccuracyCircle: showAccuracyCircle,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final center = _center;
    final first = _firstCoordinate;
    final pointCount = coordinates.length;

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => _openMapModal(context),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.blue.withAlpha(25),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.map, color: Colors.blue, size: 20),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title ?? (pointCount > 1 ? 'Locations' : 'Location'),
                          style: Theme.of(context).textTheme.titleSmall
                              ?.copyWith(fontWeight: FontWeight.bold),
                        ),
                        Text(
                          pointCount > 1
                              ? '$pointCount points'
                              : first != null
                              // ignore: lines_longer_than_80_chars (auto-documented)
                              ? '${first.latitude.toStringAsFixed(4)}, ${first.longitude.toStringAsFixed(4)}'
                              : 'No coordinates',
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(
                                color: Colors.grey.shade600,
                                fontFamily: 'monospace',
                              ),
                        ),
                      ],
                    ),
                  ),
                  Icon(
                    Icons.open_in_full,
                    size: 18,
                    color: Colors.grey.shade500,
                  ),
                ],
              ),
            ),
            // Static Map
            SizedBox(
              height: 180,
              width: double.infinity,
              child: IgnorePointer(
                child: FlutterMap(
                  options: _bounds != null
                      ? MapOptions(
                          initialCameraFit: CameraFit.bounds(
                            bounds: _bounds!,
                            padding: const EdgeInsets.all(40),
                          ),
                          interactionOptions: const InteractionOptions(
                            flags: InteractiveFlag.none,
                          ),
                        )
                      : MapOptions(
                          initialCenter: center,
                          initialZoom: zoom,
                          interactionOptions: const InteractionOptions(
                            flags: InteractiveFlag.none,
                          ),
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
                          .asMap()
                          .entries
                          .map(
                            (entry) => Marker(
                              point: entry.value.toLatLng(),
                              width: 40,
                              height: 40,
                              child: Icon(
                                Icons.location_on,
                                color: entry.value.color ?? Colors.red,
                                size: 40,
                              ),
                            ),
                          )
                          .toList(),
                    ),
                  ],
                ),
              ),
            ),
            // Footer hint
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.touch_app, size: 14, color: Colors.grey.shade500),
                  const SizedBox(width: 4),
                  Text(
                    'Tap to open interactive map',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.grey.shade500,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
