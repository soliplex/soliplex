import 'package:flutter/material.dart';

import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart';
import 'package:http/retry.dart';

import 'package:latlong2/latlong.dart';

class MapPage extends StatelessWidget {
  MapPage(List<Position> positions, {super.key})
    : _coordinates = positions
          .map((e) => LatLng(e.latitude, e.longitude))
          .toList();

  final List<LatLng> _coordinates;

  @override
  Widget build(BuildContext context) {
    return FlutterMap(
      options: MapOptions(
        initialCenter: _coordinates.isNotEmpty
            ? _coordinates.first
            :
              // Center of the USA
              const LatLng(39.816667, -98.583333),
        initialCameraFit: _coordinates.length > 1
            ? CameraFit.bounds(
                bounds: LatLngBounds.fromPoints(
                  _coordinates,
                  drawInSingleWorld: true,
                ),
                padding: EdgeInsets.all(36),
              )
            : null,
        initialZoom: _coordinates.isNotEmpty ? 13 : 1,
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'dev.fleaflet.flutter_map.example',
          tileProvider: NetworkTileProvider(httpClient: RetryClient(Client())),
        ),
        MarkerLayer(
          markers: _coordinates
              .map(
                (e) => Marker(
                  point: e,
                  child: GestureDetector(
                    onTap: () => ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          'Latitude: ${e.latitude}, '
                          'Longitude: ${e.longitude}',
                        ),
                        duration: const Duration(seconds: 3),
                        showCloseIcon: true,
                      ),
                    ),
                    child: const Icon(Icons.location_pin),
                  ),
                ),
              )
              .toList(),
        ),
        const Scalebar(
          textStyle: TextStyle(color: Colors.black, fontSize: 14),
          padding: EdgeInsets.only(right: 10, left: 10, bottom: 40),
          alignment: Alignment.bottomLeft,
        ),
      ],
    );
  }
}
