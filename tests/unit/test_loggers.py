import contextlib
import logging
from unittest import mock

import pytest

from soliplex import installation
from soliplex import loggers

LOGGER_NAME = "test-logger"
CLAIMS = {"email": "phreddy@example.com"}
SCOPE_LIFETIME = loggers.AuditLogScopes.PROCESS_LIFETIME
SCOPE_ROOM_AUTHZ = loggers.AuditLogScopes.ROOM_AUTHZ
SCOPE_ADMIN_USERS = loggers.AuditLogScopes.ADMIN_USERS
SCOPE_INSTALLATION_CONFIG = loggers.AuditLogScopes.INSTALLATION_CONFIG
SCOPE_RAG_ACCESS = loggers.AuditLogScopes.RAG_ACCESS


@pytest.fixture
def the_installation():
    return mock.create_autospec(installation.Installation)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_ctor(lgl, the_installation, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, the_installation, **w_extra)

    assert wrapper.logger is lgl.return_value
    assert wrapper.extra == w_extra

    lgl.assert_called_once_with(LOGGER_NAME)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@pytest.mark.parametrize("w_new_name", [False, True])
@mock.patch("logging.getLogger")
def test_logwrapper_bind(lgl, w_new_name, the_installation, w_extra):
    NEW_LOGGER_NAME = "new-name"
    wrapper = loggers.LogWrapper(LOGGER_NAME, the_installation, spam="qux")
    lgl.reset_mock()

    if w_new_name:
        bound = wrapper.bind(NEW_LOGGER_NAME, **w_extra)
        exp_name = NEW_LOGGER_NAME
    else:
        bound = wrapper.bind(**w_extra)
        exp_name = LOGGER_NAME

    assert bound.logger_name == exp_name
    assert bound.installation is the_installation
    assert bound.extra == wrapper.extra | w_extra

    lgl.assert_called_once_with(exp_name)


@pytest.fixture
def capturing_logger():
    """A real logger whose emitted records are captured in a list.

    Exercises 'LogWrapper' against the genuine stdlib logging machinery
    (not a mock), so a keyword argument that the adapter fails to consume
    -- and would otherwise blow up in 'Logger._log' -- is caught here.
    """
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    logger = logging.getLogger("soliplex.test.capture")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield logger.name, records
    finally:
        logger.removeHandler(handler)


def test_logwrapper_process_merges_extras_and_fields(the_installation):
    wrapper = loggers.LogWrapper(LOGGER_NAME, the_installation, actor="alice")

    msg, kwargs = wrapper.process(
        "unknown room id",
        {"extra": {"reason": "audit"}, "room_id": "faux", "exc_info": True},
    )

    assert msg == "unknown room id"
    assert kwargs == {
        "exc_info": True,
        "extra": {"actor": "alice", "reason": "audit", "room_id": "faux"},
    }


def test_logwrapper_keyword_field_reaches_record(
    the_installation, capturing_logger
):
    logger_name, records = capturing_logger
    wrapper = loggers.LogWrapper(logger_name, the_installation)

    wrapper.error(loggers.ROOM_UNKNOWN_ROOM_ID, room_id="faux")

    assert records[-1].getMessage() == loggers.ROOM_UNKNOWN_ROOM_ID
    assert records[-1].room_id == "faux"


def test_logwrapper_exception_keeps_exc_info_with_fields(
    the_installation, capturing_logger
):
    logger_name, records = capturing_logger
    wrapper = loggers.LogWrapper(logger_name, the_installation)

    try:
        {}["boom"]
    except KeyError:
        wrapper.exception(loggers.QUIZ_UNKNOWN_QUIZ_ID, quiz_id="q1")

    assert records[-1].quiz_id == "q1"
    assert records[-1].exc_info is not None


@pytest.mark.parametrize(
    "w_levels, expectation",
    [
        ({}, pytest.raises(loggers.UpdateLevelsEmpty)),
        (
            {10: 20, "TRACE": "INFO"},
            pytest.raises(loggers.UpdateLevelsInvalidKeyTypes),
        ),
        ({10: "INFO"}, pytest.raises(loggers.UpdateLevelsInvalidValueTypes)),
        ({10: 20}, contextlib.nullcontext({10: 20})),
        ({"DEBUG": "INFO"}, contextlib.nullcontext({10: 20})),
    ],
)
def test_updatelevels_ctor(w_levels, expectation):
    with expectation as expected:
        found = loggers.UpdateLevels(w_levels)

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found._update_levels == expected


def _make_record(level):
    return logging.LogRecord(
        name="",
        level=level,
        pathname="/",
        lineno=1234,
        msg="testing",
        args=(),
        exc_info=False,
    )


@pytest.mark.parametrize(
    "w_level, exp_level",
    [
        (5, 5),
        (10, 20),
        (15, 15),
        (20, 20),
    ],
)
def test_updatelevels_filter(w_level, exp_level):
    record = _make_record(w_level)
    update_levels = loggers.UpdateLevels({10: 20})

    found = update_levels.filter(record)

    assert found.levelno == exp_level


@pytest.mark.parametrize("scope", loggers.AuditLogScopes)
def test_auditlogwrapper_ctor(scope):
    found = loggers.AuditLogWrapper(scope=scope)

    assert found.name == loggers.SOLIPLEX_AUDIT_LOGGER_NAME
    assert found.extra[loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA] == scope


@pytest.fixture
def audit_records():
    """Capture records emitted to the 'soliplex-audit' logger in a list."""
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    logger = logging.getLogger(loggers.SOLIPLEX_AUDIT_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)


def _assert_audit_record(record, *, message, levelno, outcome, scope, fields):
    """Shared assertions for a single emitted audit record."""
    assert record.getMessage() == message
    assert record.levelno == levelno
    assert record.outcome == outcome
    assert record.__dict__[loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA] == scope
    for key, value in fields.items():
        assert getattr(record, key) == value


# --- ProcessLifetimeAuditLog ----------------------------------------------


def test_processlifetimeauditlog_ctor():
    found = loggers.ProcessLifetimeAuditLog()

    assert found.name == loggers.SOLIPLEX_AUDIT_LOGGER_NAME
    scope = found.extra[loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA]
    assert scope == SCOPE_LIFETIME


def test_server_starting(audit_records):
    wrapper = loggers.ProcessLifetimeAuditLog()

    wrapper.server_starting()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_SERVER_STARTING,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_LIFETIME,
        fields={},
    )


def test_server_started(audit_records):
    wrapper = loggers.ProcessLifetimeAuditLog()

    wrapper.server_started()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_SERVER_STARTED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_LIFETIME,
        fields={},
    )


def test_server_stopping(audit_records):
    wrapper = loggers.ProcessLifetimeAuditLog()

    wrapper.server_stopping()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_SERVER_STOPPING,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_LIFETIME,
        fields={},
    )


# --- RoomAuthzAuditLog ----------------------------------------------------


@pytest.mark.parametrize("w_claims", [{}, CLAIMS])
def test_roomauthzauditlog_ctor(w_claims):
    found = loggers.RoomAuthzAuditLog(claims=w_claims)

    assert found.name == loggers.SOLIPLEX_AUDIT_LOGGER_NAME
    scope = found.extra[loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA]
    assert scope == SCOPE_ROOM_AUTHZ
    assert found.extra["claims"] == w_claims


def test_room_policy_read(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.room_policy_read("r1")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_POLICY_READ,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS, "room_id": "r1"},
    )


def test_room_policies_listed(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.room_policies_listed()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_POLICIES_LISTED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS},
    )


def test_room_policy_updated(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.room_policy_updated("r1")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_POLICY_UPDATED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS, "room_id": "r1"},
    )


def test_room_policy_update_failed(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.room_policy_update_failed("r1", "boom")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_POLICY_UPDATED,
        levelno=logging.ERROR,
        outcome=loggers.AUDIT_OUTCOME_ERROR,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS, "room_id": "r1", "reason": "boom"},
    )


def test_room_default_set(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.room_default_set("r1", "DENY")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_DEFAULT_SET,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS, "room_id": "r1", "allow_deny": "DENY"},
    )


def test_room_policy_deleted(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.room_policy_deleted("r1")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_POLICY_DELETED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS, "room_id": "r1"},
    )


def test_room_policy_delete_failed(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.room_policy_delete_failed("r1", "boom")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_POLICY_DELETED,
        levelno=logging.ERROR,
        outcome=loggers.AUDIT_OUTCOME_ERROR,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS, "room_id": "r1", "reason": "boom"},
    )


def test_acl_entry_added(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.acl_entry_added("r1", "alice")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_ACL_ENTRY_ADDED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS, "room_id": "r1", "entry": "alice"},
    )


def test_acl_entry_add_failed(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.acl_entry_add_failed("r1", "alice", "dup")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_ACL_ENTRY_ADDED,
        levelno=logging.ERROR,
        outcome=loggers.AUDIT_OUTCOME_ERROR,
        scope=SCOPE_ROOM_AUTHZ,
        fields={
            "claims": CLAIMS,
            "room_id": "r1",
            "entry": "alice",
            "reason": "dup",
        },
    )


def test_acl_entry_removed(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.acl_entry_removed("r1", "alice")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_ACL_ENTRY_REMOVED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS, "room_id": "r1", "entry": "alice"},
    )


def test_acl_entry_remove_failed(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.acl_entry_remove_failed("r1", "alice", "miss")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_ACL_ENTRY_REMOVED,
        levelno=logging.ERROR,
        outcome=loggers.AUDIT_OUTCOME_ERROR,
        scope=SCOPE_ROOM_AUTHZ,
        fields={
            "claims": CLAIMS,
            "room_id": "r1",
            "entry": "alice",
            "reason": "miss",
        },
    )


def test_acl_cleared(audit_records):
    wrapper = loggers.RoomAuthzAuditLog(claims=CLAIMS)

    wrapper.acl_cleared("r1")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ROOM_ACL_CLEARED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ROOM_AUTHZ,
        fields={"claims": CLAIMS, "room_id": "r1"},
    )


# --- AdminUsersAuditLog ---------------------------------------------------


@pytest.mark.parametrize("w_claims", [{}, CLAIMS])
def test_adminusersauditlog_ctor(w_claims):
    found = loggers.AdminUsersAuditLog(claims=w_claims)

    assert found.name == loggers.SOLIPLEX_AUDIT_LOGGER_NAME
    scope = found.extra[loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA]
    assert scope == SCOPE_ADMIN_USERS
    assert found.extra["claims"] == w_claims


def test_admin_access_allowed(audit_records):
    wrapper = loggers.AdminUsersAuditLog(claims=CLAIMS)

    wrapper.admin_access_allowed()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ADMIN_ACCESS,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ADMIN_USERS,
        fields={"claims": CLAIMS},
    )


def test_admin_access_denied(audit_records):
    wrapper = loggers.AdminUsersAuditLog(claims=CLAIMS)

    wrapper.admin_access_denied()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ADMIN_ACCESS,
        levelno=logging.ERROR,
        outcome=loggers.AUDIT_OUTCOME_DENIED,
        scope=SCOPE_ADMIN_USERS,
        fields={"claims": CLAIMS},
    )


def test_admin_users_listed(audit_records):
    wrapper = loggers.AdminUsersAuditLog(claims=CLAIMS)

    wrapper.admin_users_listed()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ADMIN_USERS_LISTED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ADMIN_USERS,
        fields={"claims": CLAIMS},
    )


def test_admin_user_added(audit_records):
    wrapper = loggers.AdminUsersAuditLog(claims=CLAIMS)

    wrapper.admin_user_added("alice")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ADMIN_USER_ADDED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ADMIN_USERS,
        fields={"claims": CLAIMS, "discriminator": "alice"},
    )


def test_admin_user_add_failed(audit_records):
    wrapper = loggers.AdminUsersAuditLog(claims=CLAIMS)

    wrapper.admin_user_add_failed("alice", "dup")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ADMIN_USER_ADDED,
        levelno=logging.ERROR,
        outcome=loggers.AUDIT_OUTCOME_ERROR,
        scope=SCOPE_ADMIN_USERS,
        fields={"claims": CLAIMS, "discriminator": "alice", "reason": "dup"},
    )


def test_admin_user_removed(audit_records):
    wrapper = loggers.AdminUsersAuditLog(claims=CLAIMS)

    wrapper.admin_user_removed("alice")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ADMIN_USER_REMOVED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ADMIN_USERS,
        fields={"claims": CLAIMS, "discriminator": "alice"},
    )


def test_admin_user_remove_failed(audit_records):
    wrapper = loggers.AdminUsersAuditLog(claims=CLAIMS)

    wrapper.admin_user_remove_failed("alice", "miss")

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ADMIN_USER_REMOVED,
        levelno=logging.ERROR,
        outcome=loggers.AUDIT_OUTCOME_ERROR,
        scope=SCOPE_ADMIN_USERS,
        fields={"claims": CLAIMS, "discriminator": "alice", "reason": "miss"},
    )


def test_admin_users_cleared(audit_records):
    wrapper = loggers.AdminUsersAuditLog(claims=CLAIMS)

    wrapper.admin_users_cleared()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_ADMIN_USERS_CLEARED,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_ADMIN_USERS,
        fields={"claims": CLAIMS},
    )


# --- InstallationConfigAuditLog -------------------------------------------


@pytest.mark.parametrize("w_claims", [{}, CLAIMS])
def test_installationconfigauditlog_ctor(w_claims):
    found = loggers.InstallationConfigAuditLog(claims=w_claims)

    assert found.name == loggers.SOLIPLEX_AUDIT_LOGGER_NAME
    scope = found.extra[loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA]
    assert scope == SCOPE_INSTALLATION_CONFIG
    assert found.extra["claims"] == w_claims


def test_installation_read(audit_records):
    wrapper = loggers.InstallationConfigAuditLog(claims=CLAIMS)

    wrapper.installation_read()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_INSTALLATION_READ,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_INSTALLATION_CONFIG,
        fields={"claims": CLAIMS},
    )


def test_installation_versions_read(audit_records):
    wrapper = loggers.InstallationConfigAuditLog(claims=CLAIMS)

    wrapper.installation_versions_read()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_INSTALLATION_VERSIONS_READ,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_INSTALLATION_CONFIG,
        fields={"claims": CLAIMS},
    )


def test_installation_providers_read(audit_records):
    wrapper = loggers.InstallationConfigAuditLog(claims=CLAIMS)

    wrapper.installation_providers_read()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_INSTALLATION_PROVIDERS_READ,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_INSTALLATION_CONFIG,
        fields={"claims": CLAIMS},
    )


def test_installation_git_metadata_read(audit_records):
    wrapper = loggers.InstallationConfigAuditLog(claims=CLAIMS)

    wrapper.installation_git_metadata_read()

    _assert_audit_record(
        audit_records[-1],
        message=loggers.AUDIT_INSTALLATION_GIT_METADATA_READ,
        levelno=logging.INFO,
        outcome=loggers.AUDIT_OUTCOME_SUCCESS,
        scope=SCOPE_INSTALLATION_CONFIG,
        fields={"claims": CLAIMS},
    )


# --- RAGAccessAuditLog ---------------------------------------------------


@pytest.mark.parametrize("w_claims", [{}, CLAIMS])
def test_ragaccessauditlog_ctor(w_claims):
    found = loggers.RAGAccessAuditLog(claims=w_claims)

    assert found.name == loggers.SOLIPLEX_AUDIT_LOGGER_NAME
    scope = found.extra[loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA]
    assert scope == SCOPE_RAG_ACCESS
    assert found.extra["claims"] == w_claims
