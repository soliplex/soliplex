import 'package:soliplex_client/secure_url_storage.dart';

class ServiceUrlController {
  ServiceUrlController(this._secureUrlStorage);

  final SecureUrlStorage _secureUrlStorage;

  Future<void> addServiceUrl(String service) async {
    await _secureUrlStorage.addNewServiceUrl(service);
  }

  Future<Set<String>> getAllServiceUrl() async {
    final urls = await _secureUrlStorage.getServiceUrls();

    return urls;
  }

  Future<void> deleteServiceUrl(String url) async {
    await _secureUrlStorage.deleteUrl(url);
  }

  Future<void> deleteAllServiceUrls() async {
    await _secureUrlStorage.deleteAllUrls();
  }
}
