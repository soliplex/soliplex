from __future__ import annotations

import enum
import logging
import typing

# from soliplex import authn

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

UPLOADS_GET_ROOM = "uploads get room"
UPLOADS_GET_ROOM_FILE = "uploads get room file"
UPLOADS_GET_ROOM_THREAD = "uploads get room thread"
UPLOADS_GET_ROOM_THREAD_FILE = "uploads get room thread file"
UPLOADS_POST_ROOM = "uploads post room"
UPLOADS_POST_ROOM_THREAD = "uploads post room thread"

WORKDIRS_GET_ROOM_THREAD_RUN = "workdirs get room thread run"
WORKDIRS_GET_ROOM_THREAD_RUN_FILE = "workdirs get room thread run file"

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
AUTHN_GET_USER_CLAIMS_FAILED = "get user claims failed"

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
INST_GET_INSTALLATION_IDENTITY = "get installation identity"
INST_NO_INSTALLATION_IDENTITY = "installation identity not configured"

LOG_INGEST_INGEST_LOGS = "ingest logs"
LOG_INGEST_PAYLOAD_TOO_BIG = "payload too big"

QUIZ_GET_QUIZ = "get quiz"
QUIZ_UNKNOWN_QUIZ_ID = "unknown quiz id"
QUIZ_POST_QUIZ_QUESTION = "post quiz question"
QUIZ_UNKNOWN_QUESTION_UUID = "unknown question UUID"

ROOM_GET_ROOMS = "get rooms"
ROOM_GET_ROOM = "get room"
ROOM_GET_ROOM_BG_IMAGE = "get room bg image"
ROOM_GET_ROOM_MCP_TOKEN = "get room mcp token"
ROOM_GET_ROOM_DOCUMENTS = "get room documents"
ROOM_GET_CHUNK_VISUALIZATION = "get chunk_visualization"
ROOM_GET_SEARCH = "get search"
ROOM_UNKNOWN_ROOM_ID = "unknown room id"
ROOM_CHUNK_IMAGES_NOT_AVAILALBE = "chunk images not available"
ROOM_UNKNOWN_CHUNK_ID = "unknown chunk id"

STATS_GET_ROOMS_STATS = "get rooms stats"
STATS_GET_ROOM_STATS = "get room stats"

SOLIPLEX_AUDIT_LOGGER_NAME = "soliplex-audit"
SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA = "audit-scope"
SOLIPLEX_AUDIT_LOGGER_OUTCOME_EXTRA = "outcome"

# Outcome values folded into every audit record's 'outcome' field, so a
# reviewer can split successful operations from denied / failed ones.
AUDIT_OUTCOME_SUCCESS = "success"
AUDIT_OUTCOME_DENIED = "denied"
AUDIT_OUTCOME_ERROR = "error"

# admin-users audit events
AUDIT_ADMIN_ACCESS = "admin access"
AUDIT_ADMIN_USERS_LISTED = "admin users listed"
AUDIT_ADMIN_USER_ADDED = "admin user added"
AUDIT_ADMIN_USER_REMOVED = "admin user removed"
AUDIT_ADMIN_USERS_CLEARED = "admin users cleared"

# room-authz audit events
AUDIT_ROOM_POLICY_READ = "room policy read"
AUDIT_ROOM_POLICIES_LISTED = "room policies listed"
AUDIT_ROOM_POLICY_UPDATED = "room policy updated"
AUDIT_ROOM_POLICY_DELETED = "room policy deleted"
AUDIT_ROOM_ACL_ENTRY_ADDED = "room acl entry added"
AUDIT_ROOM_ACL_ENTRY_REMOVED = "room acl entry removed"
AUDIT_ROOM_ACL_CLEARED = "room acl cleared"
AUDIT_ROOM_DEFAULT_SET = "room default set"

# installation-config audit events
AUDIT_INSTALLATION_READ = "installation read"
AUDIT_INSTALLATION_VERSIONS_READ = "installation versions read"
AUDIT_INSTALLATION_PROVIDERS_READ = "installation providers read"
AUDIT_INSTALLATION_GIT_METADATA_READ = "installation git metadata read"

# server-lifecycle audit events
AUDIT_SERVER_STARTING = "server starting"
AUDIT_SERVER_STARTED = "server started"
AUDIT_SERVER_STOPPING = "server stopping"

# rag-access audit events
AUDIT_RAG_ACCESS = "rag access"

# rag-access 'action' values: the kind of protected-data read, carried as a
# field so both access paths share one vocabulary. The run-mediated path
# records 'rag-retrieval'; the direct helper endpoints record 'search' /
# 'chunk-viz' / 'doc-list'.
AUDIT_RAG_ACTION_RETRIEVAL = "rag-retrieval"
AUDIT_RAG_ACTION_SEARCH = "search"
AUDIT_RAG_ACTION_CHUNK_VIZ = "chunk-viz"
AUDIT_RAG_ACTION_DOC_LIST = "doc-list"

# sandbox-exec audit events (data change): the room agent's sandbox skill
# executes code against a per-run, writable working directory.
AUDIT_SANDBOX_EXEC = "sandbox exec"

# sandbox-exec 'action' values: which tool drove the execution.
AUDIT_SANDBOX_ACTION_RUN = "run"
AUDIT_SANDBOX_ACTION_RUN_PYTHON = "run-python"


class _StructuredFieldsAdapter(logging.LoggerAdapter):
    """LoggerAdapter that folds caller keyword fields into 'extra'."""

    # Keyword arguments the stdlib logging machinery consumes itself; any
    # other keyword passed to a log call is a structured field destined for
    # the record's 'extra' rather than the logger.
    _LOG_KWARGS = frozenset({"exc_info", "stack_info", "stacklevel", "extra"})

    def process(self, msg, kwargs):
        """Fold caller-supplied keyword fields into the record's 'extra'.

        A plain 'LoggerAdapter' forwards unrecognized keyword arguments
        straight to 'Logger._log', which rejects them. Capturing them here
        instead lets call sites pass structured audit fields by keyword --
        'the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id=...)'
        attaches 'room_id' to the record rather than crashing. The adapter's
        own bound extras form the base; explicit 'extra=' and keyword fields
        layer over them (matching the 'merge_extra=True' ctor semantics).
        """
        fields = {
            key: kwargs.pop(key)
            for key in list(kwargs)
            if key not in self._LOG_KWARGS
        }
        kwargs["extra"] = {**self.extra, **kwargs.get("extra", {}), **fields}
        return msg, kwargs


class LogWrapper(_StructuredFieldsAdapter):
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


class AuditLogScopes(enum.StrEnum):
    PROCESS_LIFETIME = "process-lifetime"
    ROOM_AUTHZ = "room-authz"
    ADMIN_USERS = "admin-users"
    INSTALLATION_CONFIG = "installation-config"
    RAG_ACCESS = "rag-access"
    SANDBOX_EXEC = "sandbox-exec"


class AuditLogWrapper(_StructuredFieldsAdapter):
    """Context wrapper for capturing audit-related logging values.

    Subclasses bind a fixed 'AuditLogScopes' and expose one named method per
    auditable action (the API that "spells out required / optional values").
    Each action records its 'outcome' so a reviewer can split successful
    operations from denied (authorization refused) or failed (validation /
    not-found) ones. Successes log at INFO; denials and failures at ERROR.
    """

    def __init__(self, *, scope: AuditLogScopes | None = None, **extra):
        extra_w_scope = {
            SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA: scope,
        } | extra

        logger = logging.getLogger(SOLIPLEX_AUDIT_LOGGER_NAME)
        try:
            super().__init__(logger, extra=extra_w_scope, merge_extra=True)
        except TypeError:  # pragma: NO COVER Python < 3.13
            super().__init__(logger, extra=extra_w_scope)

    def _succeeded(self, message: str, **fields):
        self.info(message, outcome=AUDIT_OUTCOME_SUCCESS, **fields)

    def _denied(self, message: str, **fields):
        self.error(message, outcome=AUDIT_OUTCOME_DENIED, **fields)

    def _failed(self, message: str, **fields):
        self.error(message, outcome=AUDIT_OUTCOME_ERROR, **fields)


class ProcessLifetimeAuditLog(AuditLogWrapper):
    """Record process lifetime audit events

    Each method corresponds to an event type.
    """

    def __init__(self, **extra):
        super().__init__(scope=AuditLogScopes.PROCESS_LIFETIME, **extra)

    def server_starting(self):
        self._succeeded(AUDIT_SERVER_STARTING)

    def server_started(self):
        self._succeeded(AUDIT_SERVER_STARTED)

    def server_stopping(self):
        self._succeeded(AUDIT_SERVER_STOPPING)


class RoomAuthzAuditLog(AuditLogWrapper):
    """Record room authorization audit events

    Each method corresponds to an event type, with variants for outcomes.
    """

    def __init__(self, claims: dict[str, typing.Any], **extra):
        extra_with_claims = {"claims": claims} | extra
        super().__init__(scope=AuditLogScopes.ROOM_AUTHZ, **extra_with_claims)

    # security-object reads
    def room_policy_read(self, room_id: str):
        self._succeeded(AUDIT_ROOM_POLICY_READ, room_id=room_id)

    def room_policies_listed(self):
        self._succeeded(AUDIT_ROOM_POLICIES_LISTED)

    # policy modification
    def room_policy_updated(self, room_id: str):
        self._succeeded(AUDIT_ROOM_POLICY_UPDATED, room_id=room_id)

    def room_policy_update_failed(self, room_id: str, reason: str):
        self._failed(AUDIT_ROOM_POLICY_UPDATED, room_id=room_id, reason=reason)

    def room_default_set(self, room_id: str, allow_deny: str):
        self._succeeded(
            AUDIT_ROOM_DEFAULT_SET, room_id=room_id, allow_deny=allow_deny
        )

    # policy / security-object deletion
    def room_policy_deleted(self, room_id: str):
        self._succeeded(AUDIT_ROOM_POLICY_DELETED, room_id=room_id)

    def room_policy_delete_failed(self, room_id: str, reason: str):
        self._failed(AUDIT_ROOM_POLICY_DELETED, room_id=room_id, reason=reason)

    # room-access grant
    def acl_entry_added(self, room_id: str, entry: str):
        self._succeeded(
            AUDIT_ROOM_ACL_ENTRY_ADDED, room_id=room_id, entry=entry
        )

    def acl_entry_add_failed(self, room_id: str, entry: str, reason: str):
        self._failed(
            AUDIT_ROOM_ACL_ENTRY_ADDED,
            room_id=room_id,
            entry=entry,
            reason=reason,
        )

    # room-access revoke
    def acl_entry_removed(self, room_id: str, entry: str):
        self._succeeded(
            AUDIT_ROOM_ACL_ENTRY_REMOVED, room_id=room_id, entry=entry
        )

    def acl_entry_remove_failed(self, room_id: str, entry: str, reason: str):
        self._failed(
            AUDIT_ROOM_ACL_ENTRY_REMOVED,
            room_id=room_id,
            entry=entry,
            reason=reason,
        )

    # policy / security-object deletion
    def acl_cleared(self, room_id: str):
        self._succeeded(AUDIT_ROOM_ACL_CLEARED, room_id=room_id)


class AdminUsersAuditLog(AuditLogWrapper):
    """Record admin users audit events

    Each method corresponds to an event type, with variants for outcomes.
    """

    def __init__(self, claims: dict[str, typing.Any], **extra):
        extra_with_claims = {"claims": claims} | extra
        super().__init__(scope=AuditLogScopes.ADMIN_USERS, **extra_with_claims)

    # privilege gate
    def admin_access_allowed(self):
        self._succeeded(AUDIT_ADMIN_ACCESS)

    def admin_access_denied(self):
        self._denied(AUDIT_ADMIN_ACCESS)

    # security-object read
    def admin_users_listed(self):
        self._succeeded(AUDIT_ADMIN_USERS_LISTED)

    # privilege grant
    def admin_user_added(self, discriminator: str):
        self._succeeded(AUDIT_ADMIN_USER_ADDED, discriminator=discriminator)

    def admin_user_add_failed(self, discriminator: str, reason: str):
        self._failed(
            AUDIT_ADMIN_USER_ADDED, discriminator=discriminator, reason=reason
        )

    # privilege revoke
    def admin_user_removed(self, discriminator: str):
        self._succeeded(AUDIT_ADMIN_USER_REMOVED, discriminator=discriminator)

    def admin_user_remove_failed(self, discriminator: str, reason: str):
        self._failed(
            AUDIT_ADMIN_USER_REMOVED,
            discriminator=discriminator,
            reason=reason,
        )

    def admin_users_cleared(self):
        self._succeeded(AUDIT_ADMIN_USERS_CLEARED)


class InstallationConfigAuditLog(AuditLogWrapper):
    """Record installation configuratino audit events

    Each method corresponds to an access type.
    """

    def __init__(self, claims: dict[str, typing.Any], **extra):
        extra_with_claims = {"claims": claims} | extra
        super().__init__(
            scope=AuditLogScopes.INSTALLATION_CONFIG, **extra_with_claims
        )

    # privileged-config reads
    def installation_read(self):
        self._succeeded(AUDIT_INSTALLATION_READ)

    def installation_versions_read(self):
        self._succeeded(AUDIT_INSTALLATION_VERSIONS_READ)

    def installation_providers_read(self):
        self._succeeded(AUDIT_INSTALLATION_PROVIDERS_READ)

    def installation_git_metadata_read(self):
        self._succeeded(AUDIT_INSTALLATION_GIT_METADATA_READ)


class RAGAccessAuditLog(AuditLogWrapper):
    """Record knowledge-base accesses made while answering a request

    Each method corresponds to an access type (the 'action' field).

    The 'retrieval' acation covers the run-mediated path: Soliplex sees only
    the rendered tool result, not a tool-error signal, so every observed
    skill access is recorded as a success.

    The direct helper API endpoints (`views.rooms`) have their own action
    methods ('search' / 'chunk-viz' / 'doc-list') with failure variants, where
    the HTTP outcome authoritatively distinguishes a refused or absent access.

    Room-level agent tool access will use the same action methods, but log
    failure variants based on exceptions raised.

    Action method parameters:

    - 'db_path' names the LanceDB the access targeted
    - 'selector' is the query / document reference / chunk ids used
    - 'result_refs' are the identifiers returned (not their content);
      empty when the read matched nothing.
    """

    def __init__(self, claims: dict[str, typing.Any], **extra):
        extra_with_claims = {"claims": claims} | extra
        super().__init__(scope=AuditLogScopes.RAG_ACCESS, **extra_with_claims)

    def retrieval(
        self,
        db_path: str,
        tool: str,
        selector: typing.Any,
        result_refs: typing.Any,
    ):
        self._succeeded(
            AUDIT_RAG_ACCESS,
            action=AUDIT_RAG_ACTION_RETRIEVAL,
            db_path=db_path,
            tool=tool,
            selector=selector,
            result_refs=result_refs,
        )

    def search(
        self, db_path: str, selector: typing.Any, result_refs: typing.Any
    ):
        self._succeeded(
            AUDIT_RAG_ACCESS,
            action=AUDIT_RAG_ACTION_SEARCH,
            db_path=db_path,
            selector=selector,
            result_refs=result_refs,
        )

    def search_failed(
        self, db_path: str | None, selector: typing.Any, reason: str
    ):
        self._failed(
            AUDIT_RAG_ACCESS,
            action=AUDIT_RAG_ACTION_SEARCH,
            db_path=db_path,
            selector=selector,
            reason=reason,
        )

    def doc_list(self, db_path: str, result_refs: typing.Any):
        self._succeeded(
            AUDIT_RAG_ACCESS,
            action=AUDIT_RAG_ACTION_DOC_LIST,
            db_path=db_path,
            result_refs=result_refs,
        )

    def chunk_viz(
        self, db_path: str, selector: typing.Any, result_refs: typing.Any
    ):
        self._succeeded(
            AUDIT_RAG_ACCESS,
            action=AUDIT_RAG_ACTION_CHUNK_VIZ,
            db_path=db_path,
            selector=selector,
            result_refs=result_refs,
        )

    def chunk_viz_failed(
        self, db_path: str | None, selector: typing.Any, reason: str
    ):
        self._failed(
            AUDIT_RAG_ACCESS,
            action=AUDIT_RAG_ACTION_CHUNK_VIZ,
            db_path=db_path,
            selector=selector,
            reason=reason,
        )


class SandboxExecAuditLog(AuditLogWrapper):
    """Record sandbox executions that may change run-workdir data.

    Each ``run`` / ``run_python`` invocation is one data-change event: the
    room agent's sandbox skill executes code against the run's writable
    working directory. The command and script bodies are deliberately not
    recorded inline (size / content leakage); the record captures the
    'action' (which tool ran), the 'workdir' whose data the execution may
    have changed, the 'environment' it ran in, and 'refs' -- the host paths
    of the saved command / script transcripts (empty when transcripts are
    not configured).
    """

    def __init__(self, claims: dict[str, typing.Any], **extra):
        extra_with_claims = {"claims": claims} | extra
        super().__init__(
            scope=AuditLogScopes.SANDBOX_EXEC, **extra_with_claims
        )

    def executed(
        self,
        action: str,
        workdir: str | None,
        environment: str | None,
        refs: typing.Any,
    ):
        self._succeeded(
            AUDIT_SANDBOX_EXEC,
            action=action,
            workdir=workdir,
            environment=environment,
            refs=refs,
        )

    def execute_failed(
        self,
        action: str,
        workdir: str | None,
        environment: str | None,
        refs: typing.Any,
        reason: str,
    ):
        self._failed(
            AUDIT_SANDBOX_EXEC,
            action=action,
            workdir=workdir,
            environment=environment,
            refs=refs,
            reason=reason,
        )
