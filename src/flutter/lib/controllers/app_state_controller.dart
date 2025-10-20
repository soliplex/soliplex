import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

class AppStateController extends StateNotifier<AppState> {
  AppStateController(super.state);

  @override
  bool updateShouldNotify(AppState old, AppState current) {
    // Check nav state
    return (old.title == current.title ||
        old.canNavigate == current.canNavigate);
  }

  Future<String> getVariable(String variable) async {
    switch (variable) {
      case 'CURRENT_GEOLOCATION':
        final position = await currentPosition();
        return position.toString();
      default:
        return Future.error('No variable named `$variable`');
    }
  }

  Future<Position> currentPosition() async {
    bool serviceEnabled;
    LocationPermission permission;

    // Test if location services are enabled.
    serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      // Location services are not enabled don't continue
      // accessing the position and request users of the
      // App to enable the location services.
      return Future.error('Location services are disabled.');
    }

    permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        // Permissions are denied, next time you could try
        // requesting permissions again (this is also where
        // Android's shouldShowRequestPermissionRationale
        // returned true. According to Android guidelines
        // your App should show an explanatory UI now.
        return Future.error('Location permissions are denied');
      }
    }

    if (permission == LocationPermission.deniedForever) {
      // Permissions are denied forever, handle appropriately.
      return Future.error(
        'Location permissions are permanently denied, we cannot request permissions.',
      );
    }

    // When we reach here, permissions are granted and we can
    // continue accessing the position of the device.
    return await Geolocator.getCurrentPosition();
  }
}

class AppState {
  String? _title;
  var canNavigate = false;

  String get title => _title ?? 'Soliplex Client';

  set title(String? newTitle) => _title = newTitle;
}
