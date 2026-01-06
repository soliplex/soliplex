/// Pure Dart client for Soliplex backend HTTP and AG-UI APIs.
library soliplex_client;

// AG-UI protocol from ag_ui package.
export 'package:ag_ui/ag_ui.dart';

export 'src/api/api.dart';
export 'src/application/application.dart';
export 'src/auth/auth.dart';
export 'src/domain/domain.dart';
export 'src/errors/errors.dart';
export 'src/http/http.dart';
export 'src/utils/utils.dart' hide CancelToken;
