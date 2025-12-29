import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';

void main() {
  group('NetworkTransportLayer Auth Drift', () {
    test('updateHeaders recreates AgUiClient to prevent stale headers', () {
      final layer = NetworkTransportLayer(
        baseUrl: 'http://test.com',
        defaultHeaders: {'Authorization': 'Bearer old_token'},
      );

      final client1 = layer.agUiClient;

      // Update headers
      layer.updateHeaders({'Authorization': 'Bearer new_token'});

      final client2 = layer.agUiClient;

      // Client should be recreated (different instance)
      expect(client1, isNot(same(client2)));

      // We assume the new client was created with the new headers because
      // NetworkTransportLayer implementation logic does so.
      // We can't easily inspect the internal config of AgUiClient without
      // reflection.
    });
  });
}
