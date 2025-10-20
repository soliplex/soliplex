import 'package:flutter/material.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/controllers/app_state_controller.dart';
import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'package:soliplex_client/controllers/pydantic_provider_controller.dart';

class StatusView extends ConsumerWidget {
  const StatusView({super.key});

  Future<AppInfo> _getAppInfo(
    PydanticProviderController pydanticProvider,
    CurrentChatroomController chatroomController,
    AppStateController appStateController,
  ) async {
    final destinationUri = Uri.parse(pydanticProvider.destinationUrl);
    final serverUrl = destinationUri.origin;

    final packageInfo = await PackageInfo.fromPlatform();
    final appVersion = '${packageInfo.version}+${packageInfo.buildNumber}';
    Map<String, dynamic> userInfo = {};
    try {
      userInfo = await chatroomController.retrieveUserInfo();
    } catch (e) {
      debugPrint('Could not retrieve user info. $e.');
    }
    Position? currentPosition;
    try {
      currentPosition = await appStateController.currentPosition();
    } catch (e) {
      debugPrint('$e');
    }

    return AppInfo(
      appName: packageInfo.appName,
      version: appVersion,
      server: serverUrl,
      userInfo: userInfo,
      currentPosition: currentPosition,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pydanticProvider = ref.read(pydanticProviderController);
    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );
    final appState = ref.read(appStateController.notifier);

    return SingleChildScrollView(
      child: FutureBuilder(
        future: _getAppInfo(pydanticProvider, chatroomController, appState),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return Center(
              child: CircularProgressIndicator(),
            ); // Show loading indicator
          } else if (snapshot.hasError) {
            final errorText = 'Error: ${snapshot.error}';
            debugPrint(errorText);
            return Center(child: Text(errorText)); // Show error
          } else if (snapshot.hasData) {
            final appInfo = snapshot.data!;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                UserInfoDisplay(userInfo: appInfo.userInfo),
                StatusInfoItem(label: 'App Name', contents: appInfo.appName),
                StatusInfoItem(label: 'Version', contents: appInfo.version),
                StatusInfoItem(label: 'Server', contents: appInfo.server),
                if (appInfo.currentPosition != null) ...[
                  SizedBox(height: 20),
                  GeoLocationItem(appInfo.currentPosition),
                ],
              ],
            );
          } else {
            return Text('Finished loading About information');
          }
        },
      ),
    );
  }
}

class UserInfoDisplay extends StatelessWidget {
  const UserInfoDisplay({required this.userInfo, super.key});

  final Map<String, dynamic> userInfo;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,

      children: (userInfo.isEmpty)
          ? []
          : [
              Text(
                'Current User',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              ...userInfo.entries.map(
                (e) => Row(
                  children: [
                    SizedBox(width: 16.0),
                    Expanded(
                      child: StatusInfoItem(
                        label: e.key,
                        contents: '${e.value}',
                      ),
                    ),
                  ],
                ),
              ),
            ],
    );
  }
}

class GeoLocationItem extends StatelessWidget {
  const GeoLocationItem(this._position, {super.key});

  final Position? _position;

  @override
  Widget build(BuildContext context) {
    if (_position == null) {
      return Container();
    }
    final positionData = {
      'Latitude': _position.latitude,
      'Longitude': _position.longitude,
    };

    return ElevatedButton(
      onPressed: () {
        context.pop();
        context.go('/map', extra: [_position]);
      },
      style: ElevatedButton.styleFrom(
        backgroundColor: Colors.blueGrey[300],
        elevation: 4,
      ),
      child: Padding(
        padding: const EdgeInsets.all(8.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Current Position',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            ...positionData.entries.map(
              (e) => Row(
                children: [
                  SizedBox(width: 16.0),
                  Expanded(
                    child: StatusInfoItem(label: e.key, contents: '${e.value}'),
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

class StatusInfoItem extends StatelessWidget {
  const StatusInfoItem({
    required this.label,
    required this.contents,
    super.key,
  });

  final String label;
  final String contents;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      children: [
        Text('$label: ', style: TextStyle(fontWeight: FontWeight.bold)),
        Text(contents),
      ],
    );
  }
}

class AppInfo {
  final String appName;
  final String version;
  final String server;
  final Map<String, dynamic> userInfo;
  final Position? currentPosition;

  AppInfo({
    required this.appName,
    required this.version,
    required this.server,
    this.userInfo = const {},
    this.currentPosition,
  });
}
