from __future__ import annotations

import logging

SOLIPLEX_LOGGER_NAME = "soliplex"

AUTHN_LOGGER_NAME = "soliplex.authn"
AUTHN_NO_AUTH_MODE = "soliplex server in no-auth mode"
AUTHN_JWT_INVALID = "JWT validation failed"
AUTHN_JWT_VALID = "JWT validation succeeded"
AUTHN_NO_AUTH_MODE = "system in no-auth mode"
AUTHN_GET_LOGIN = "get login"
AUTHN_GET_LOGIN_SYSTEM = "get login system"
AUTHN_GET_AUTH_SYSTEM = "get auth system"
AUTHN_GET_USER_INFO = "get user info"

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


class LogWrapper:
    """Context wrapper for capturing extra logging values"""

    def __init__(self, logger_name, **extra):
        self.logger_name = logger_name
        self.extra = extra
        self.logger = logging.getLogger(logger_name)

    def log(self, level, message, *args):
        self.logger.log(level, message, *args, extra=self.extra)

    def critical(self, message, *args):
        self.logger.critical(message, *args, extra=self.extra)

    def exception(self, message, *args):
        self.logger.exception(message, *args, extra=self.extra)

    def error(self, message, *args):
        self.logger.error(message, *args, extra=self.extra)

    def warning(self, message, *args):
        self.logger.warning(message, *args, extra=self.extra)

    def info(self, message, *args):
        self.logger.info(message, *args, extra=self.extra)

    def debug(self, message, *args):
        self.logger.debug(message, *args, extra=self.extra)

    def bind(self, logger_name=None, **extra) -> LogWrapper:
        if logger_name is None:
            logger_name = self.logger_name

        extras = self.extra | extra

        return LogWrapper(logger_name, **extras)
