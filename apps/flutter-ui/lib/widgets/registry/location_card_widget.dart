import 'package:flutter/material.dart';

import 'package:soliplex/widgets/registry/widget_utils.dart';

/// LocationCard widget for displaying GPS location data.
class LocationCardWidget extends StatelessWidget {
  const LocationCardWidget({
    super.key,
    this.latitude,
    this.longitude,
    this.accuracy,
    this.altitude,
    this.address,
    this.city,
    this.country,
    this.timestamp,
    this.color,
  });

  /// Create from JSON data.
  ///
  /// Expected data format:
  /// ```json
  /// {
  ///   "latitude": 37.7749,
  ///   "longitude": -122.4194,
  ///   "accuracy": 10.0,
  ///   "altitude": 15.0,
  ///   "address": "123 Main St",
  ///   "city": "San Francisco",
  ///   "country": "USA",
  ///   "timestamp": "2024-01-15T10:30:00Z",
  ///   "color": 4280391411
  /// }
  /// ```
  factory LocationCardWidget.fromData(
    Map<String, dynamic> data,
  ) {
    return LocationCardWidget(
      latitude: parseDouble(data['latitude']),
      longitude: parseDouble(data['longitude']),
      accuracy: parseDouble(data['accuracy']),
      altitude: parseDouble(data['altitude']),
      address: data['address'] as String?,
      city: data['city'] as String?,
      country: data['country'] as String?,
      timestamp: data['timestamp'] as String?,
      color: parseColor(data['color']),
    );
  }
  final double? latitude;
  final double? longitude;
  final double? accuracy;
  final double? altitude;
  final String? address;
  final String? city;
  final String? country;
  final String? timestamp;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final baseColor = color ?? Colors.blue;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header with icon
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: baseColor.withAlpha(25),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(Icons.location_on, color: baseColor, size: 24),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Your Location',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      if (city != null || country != null)
                        Text(
                          [city, country].whereType<String>().join(', '),
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(color: Colors.grey.shade600),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Coordinates
            if (latitude != null && longitude != null) ...[
              _buildInfoRow(
                context,
                Icons.my_location,
                'Coordinates',
                // ignore: lines_longer_than_80_chars (auto-documented)
                '${latitude!.toStringAsFixed(6)}, ${longitude!.toStringAsFixed(6)}',
              ),
              const SizedBox(height: 8),
            ],
            // Accuracy
            if (accuracy != null) ...[
              _buildInfoRow(
                context,
                Icons.gps_fixed,
                'Accuracy',
                '±${accuracy!.toStringAsFixed(1)} meters',
              ),
              const SizedBox(height: 8),
            ],
            // Altitude
            if (altitude != null) ...[
              _buildInfoRow(
                context,
                Icons.terrain,
                'Altitude',
                '${altitude!.toStringAsFixed(1)} meters',
              ),
              const SizedBox(height: 8),
            ],
            // Address
            if (address != null) ...[
              _buildInfoRow(context, Icons.home, 'Address', address!),
              const SizedBox(height: 8),
            ],
            // Timestamp
            if (timestamp != null)
              _buildInfoRow(
                context,
                Icons.access_time,
                'Time',
                _formatTimestamp(timestamp!),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(
    BuildContext context,
    IconData icon,
    String label,
    String value,
  ) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: Colors.grey.shade600),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: Theme.of(
                  context,
                ).textTheme.bodySmall?.copyWith(color: Colors.grey.shade600),
              ),
              Text(
                value,
                style: Theme.of(context).textTheme.bodyMedium,
                overflow: TextOverflow.ellipsis,
                maxLines: 2,
              ),
            ],
          ),
        ),
      ],
    );
  }

  String _formatTimestamp(String timestamp) {
    try {
      final dt = DateTime.parse(timestamp);
      // ignore: lines_longer_than_80_chars (auto-documented)
      return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}:${dt.second.toString().padLeft(2, '0')}';
    } on Object catch (_) {
      return timestamp;
    }
  }
}
