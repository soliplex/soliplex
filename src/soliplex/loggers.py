from __future__ import annotations

import logging

SOLIPLEX_LOGGER_NAME = "soliplex"

AGUI_GET_ROOM = "get room agui"
AGUI_GET_ROOM_THREAD = "get room agui thread"
AGUI_GET_ROOM_THREAD_RUN = "get room agui thread run"
AGUI_POST_ROOM = "post room agui"
AGUI_POST_ROOM_THREAD = "post room agui thread"
AGUI_POST_ROOM_THREAD_META = "post room agui thread meta"
AGUI_DELETE_ROOM_THREAD = "delete room agui thread"
AGUI_POST_ROOM_THREAD_RUN = "post room agui thread run"
AGUI_POST_ROOM_THREAD_RUN_META = "post room agui thread run meta"
AGUI_GET_ROOM_THREAD_RUN_FEEDBACK = "get room agui thread run feedback"
AGUI_POST_ROOM_THREAD_RUN_FEEDBACK = "post room agui thread run feedback"
AGUI_POST_RECENT_FEEDBACK = "post recent agui feedback"
AGUI_POST_RECENT_ROOM_FEEDBACK = "post recent room agui feedback"
AGUI_POST_RECENT_USER_FEEDBACK = "post recent room user feedback"
AGUI_POST_REVIEW_RECENT_FEEDBACK = "post review recent agui feedback"
AGUI_POST_RESOLVE_RECENT_FEEDBACK = "post resolve recent agui feedback"

UPLOADS_POST_ROOM = "uploads post room"
UPLOADS_POST_ROOM_THREAD = "uploads post room thread"

AUTHN_LOGGER_NAME = "soliplex.authn"
AUTHN_NO_AUTH_MODE = "soliplex server in no-auth mode"
AUTHN_JWT_INVALID = "JWT validation failed"
AUTHN_JWT_VALID = "JWT validation succeeded"
AUTHN_NO_AUTH_MODE = "system in no-auth mode"
AUTHN_GET_LOGIN = "get login"
AUTHN_GET_LOGIN_SYSTEM = "get login system"
AUTHN_GET_AUTH_SYSTEM = "get auth system"
AUTHN_GET_USER_INFO = "get user info"
AUTHN_GET_USER_CLAIMS = "get user claims"
AUTHN_GET_USER_CLAIMS_FAILED = "get user claims failed: %s"

AUTHZ_LOGGER_NAME = "soliplex.authz"
AUTHZ_FILTERING_ROOMS = "filtering rooms for user"
AUTHZ_NOT_FILTERING_ROOMS = "no authz policy, not filtering rooms"
AUTHZ_ROOM_AUTHORIZED = "room authorized"
AUTHZ_ROOM_NOT_AUTHORIZED = "room not authorized"
AUTHZ_ADMIN_ACCESS_REQUIRED = "Admin access required"
AUTHZ_GET_ROOM_POLICY = "get room policy"
AUTHZ_POST_ROOM_POLICY = "post room policy"
AUTHZ_DELETE_ROOM_POLICY = "delete room policy"
AUTHZ_GET_INSTALLATION_AUTHZ = "get installation authz"

INST_GET_INSTALLATION = "get installation"
INST_GET_INSTALLATION_VERSIONS = "get installation versions"
INST_SUBPROCESS_PIP = "subprocess pip failed"
INST_GET_INSTALLATION_PROVIDERS = "get installation providers"
INST_GET_INSTALLATION_GIT_METADATA = "get installation git metadata"

LOG_INGEST_INGEST_LOGS = "ingest logs"
LOG_INGEST_PAYLOAD_TOO_BIG = "payload too big"

QUIZ_GET_QUIZ = "get quiz"
QUIZ_UNKNOWN_QUIZ_ID = "unknown quiz id: %s"
QUIZ_POST_QUIZ_QUESTION = "post quiz question"
QUIZ_UNKNOWN_QUESTION_UUID = "unknown question UUID: %s"

ROOM_GET_ROOMS = "get rooms"
ROOM_GET_ROOM = "get room"
ROOM_GET_ROOM_BG_IMAGE = "get room bg image"
ROOM_GET_ROOM_MCP_TOKEN = "get room mcp token"
ROOM_GET_ROOM_DOCUMENTS = "get room documents"
ROOM_GET_CHUNK_VISUALIZATION = "get chunk_visualization"
ROOM_UNKNOWN_ROOM_ID = "unknown room id: %s"
ROOM_CHUNK_IMAGES_NOT_AVAILALBE = "chunk images not available: %s"
ROOM_UNKNOWN_CHUNK_ID = "unknown chunk id: %s"


class LogWrapper(logging.LoggerAdapter):
    """Context wrapper for capturing extra logging values"""

    def __init__(self, logger_name, the_installation, **extra):
        self.logger_name = logger_name
        self.installation = the_installation
        logger = logging.getLogger(logger_name)
        try:
            super().__init__(logger, extra=extra, merge_extra=True)
        except TypeError:  # pragma: NO COVER Python < 3.13
            super().__init__(logger, extra=extra)

    def bind(self, logger_name=None, **extra) -> LogWrapper:
        if logger_name is None:
            logger_name = self.logger_name

        extras = self.extra | extra

        return LogWrapper(logger_name, self.installation, **extras)


class UpdateLevelsEmpty(ValueError):
    def __init__(self):
        super().__init__("'update_levels' is empty")


class UpdateLevelsInvalidKeyTypes(ValueError):
    def __init__(self, key_types: set[type]):
        self.key_types = key_types
        super().__init__(
            f"Key types: ({key_types}) must be only 'str' or only 'int'"
        )


class UpdateLevelsInvalidValueTypes(ValueError):
    def __init__(self, key_types: set[type], value_types: set[type]):
        self.key_types = key_types
        self.value_types = value_types
        super().__init__(
            f"Value types ({value_types}) must match key types ({key_types})"
        )


class UpdateLevels(logging.Filter):
    """Map log records from a given level a new level

    Args:
        'update_levels' is a map from integer log levels to new levels

    Returns:
        Existing log record, mutated in place if level is remapped.
    """

    def __init__(self, update_levels: dict[int, int] | dict[str, str]):
        super().__init__()

        if not update_levels:
            raise UpdateLevelsEmpty()

        key_types = set(type(key) for key in update_levels.keys())

        if key_types not in ({str}, {int}):
            raise UpdateLevelsInvalidKeyTypes(key_types)

        value_types = set(type(value) for value in update_levels.values())

        if key_types != value_types:
            raise UpdateLevelsInvalidValueTypes(key_types, value_types)

        if key_types == {int}:
            self._update_levels = update_levels

        else:  # key_types == {str}:
            self._update_levels = {
                logging.getLevelName(key): logging.getLevelName(value)
                for key, value in update_levels.items()
            }

    def filter(self, log_record: logging.LogRecord) -> logging.LogRecord:
        before = log_record.levelno
        after = self._update_levels.get(before, before)

        if after != before:
            log_record.levelno = after
            log_record.levelname = logging.getLevelName(after)

        return log_record
