from unittest import mock

import fastapi
import pytest

from soliplex import agui
from soliplex import authz
from soliplex import loggers
from soliplex import models
from soliplex.views import labels as labels_views

THE_USER_CLAIMS = {"email": "phreddy@example.com"}


def _label(label_id, label_name, color="#123456"):
    """Build a stand-in label.

    A plain instance rather than a mock: 'name' is reserved in 'Mock's
    constructor -- it names the mock instead of setting an attribute --
    so an autospec'd label has no readable name at all.
    """

    class TestLabel(agui.Label):
        def __init__(self):
            self.id_ = label_id
            self.name = label_name
            self.name_key = label_name.lower()
            self.color = color

    return TestLabel()


URGENT = _label(1, "Urgent")
BLOCKED = _label(2, "Blocked", color="#ABCDEF")


@pytest.fixture
def the_threads():
    return mock.create_autospec(agui.ThreadStorage)


@pytest.fixture
def the_admin_users():
    return mock.create_autospec(authz.AdminUserPolicy)


@pytest.fixture
def the_labels_logger():
    return mock.create_autospec(loggers.LogWrapper)


def test_get_the_labels_logger():
    the_logger = mock.create_autospec(loggers.LogWrapper)

    found = labels_views.get_the_labels_logger(the_logger=the_logger)

    assert found is the_logger.bind.return_value

    the_logger.bind.assert_called_once_with(loggers.LABELS_LOGGER_NAME)


@pytest.mark.anyio
async def test_get_agui_labels_hides_counts_from_non_admins(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = False
    the_threads.list_labels.return_value = [URGENT, BLOCKED]

    found = await labels_views.get_agui_labels(
        the_threads=the_threads,
        the_admin_users=the_admin_users,
        the_user_claims=THE_USER_CLAIMS,
        the_labels_logger=the_labels_logger,
    )

    # The catalogue itself is readable by anyone -- a user has to know it
    # to attach anything from it.
    assert [label.name for label in found.labels] == ["Urgent", "Blocked"]

    # Counts span every user's threads, so a name beside a volume would
    # leak how much work exists that this caller cannot see. Omitted
    # outright, never sent as zero.
    assert [label.usage_count for label in found.labels] == [None, None]

    the_threads.get_label_usage_counts.assert_not_awaited()
    the_labels_logger.debug.assert_called_once_with(loggers.LABELS_GET)


@pytest.mark.anyio
async def test_get_agui_labels_gives_admins_global_counts(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = True
    the_threads.list_labels.return_value = [URGENT, BLOCKED]
    the_threads.get_label_usage_counts.return_value = {URGENT.id_: 7}

    found = await labels_views.get_agui_labels(
        the_threads=the_threads,
        the_admin_users=the_admin_users,
        the_user_claims=THE_USER_CLAIMS,
        the_labels_logger=the_labels_logger,
    )

    # A label nothing carries reports zero rather than being omitted:
    # for an admin, "unused" is exactly the answer they asked for.
    assert [label.usage_count for label in found.labels] == [7, 0]

    the_admin_users.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
        resource=loggers.AUDIT_RESOURCE_THREAD_LABEL,
        action=loggers.AUDIT_ACTION_READ,
    )


@pytest.mark.anyio
async def test_post_agui_labels_creates(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = True
    the_threads.create_label.return_value = URGENT

    found = await labels_views.post_agui_labels(
        new_label=models.AGUI_NewLabelRequest(name="Urgent"),
        the_threads=the_threads,
        the_admin_users=the_admin_users,
        the_user_claims=THE_USER_CLAIMS,
        the_labels_logger=the_labels_logger,
    )

    assert found.id == URGENT.id_
    assert found.name == "Urgent"
    # A freshly created label reports no count: it cannot have one yet,
    # and the create response is not the place to go and look.
    assert found.usage_count is None

    the_threads.create_label.assert_awaited_once_with(
        name="Urgent",
        color=None,
    )


@pytest.mark.anyio
async def test_post_agui_labels_refuses_non_admins(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = False

    with pytest.raises(fastapi.HTTPException) as exc:
        await labels_views.post_agui_labels(
            new_label=models.AGUI_NewLabelRequest(name="Urgent"),
            the_threads=the_threads,
            the_admin_users=the_admin_users,
            the_user_claims=THE_USER_CLAIMS,
            the_labels_logger=the_labels_logger,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

    # Gated before the write, not after it.
    the_threads.create_label.assert_not_awaited()


@pytest.mark.anyio
async def test_post_agui_labels_reports_a_duplicate_name(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = True
    the_threads.create_label.side_effect = agui.DuplicateLabel("Urgent")

    with pytest.raises(fastapi.HTTPException) as exc:
        await labels_views.post_agui_labels(
            new_label=models.AGUI_NewLabelRequest(name="urgent"),
            the_threads=the_threads,
            the_admin_users=the_admin_users,
            the_user_claims=THE_USER_CLAIMS,
            the_labels_logger=the_labels_logger,
        )

    # 409, not 500: the client can rename and retry.
    assert exc.value.status_code == 409


@pytest.mark.anyio
async def test_post_agui_label_id_updates(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = True
    the_threads.update_label.return_value = BLOCKED

    found = await labels_views.post_agui_label_id(
        label_id=2,
        updated_label=models.AGUI_UpdateLabelRequest(color="#ABCDEF"),
        the_threads=the_threads,
        the_admin_users=the_admin_users,
        the_user_claims=THE_USER_CLAIMS,
        the_labels_logger=the_labels_logger,
    )

    assert found.color == "#ABCDEF"

    # Omitted fields travel as None, which the storage layer reads as
    # "leave alone" -- recoloring must not blank the name.
    the_threads.update_label.assert_awaited_once_with(
        label_id=2,
        name=None,
        color="#ABCDEF",
    )
    the_labels_logger.debug.assert_called_once_with(loggers.LABELS_POST_LABEL)


@pytest.mark.anyio
async def test_post_agui_label_id_refuses_non_admins(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = False

    with pytest.raises(fastapi.HTTPException) as exc:
        await labels_views.post_agui_label_id(
            label_id=2,
            updated_label=models.AGUI_UpdateLabelRequest(name="Blocked"),
            the_threads=the_threads,
            the_admin_users=the_admin_users,
            the_user_claims=THE_USER_CLAIMS,
            the_labels_logger=the_labels_logger,
        )

    assert exc.value.status_code == 403

    the_threads.update_label.assert_not_awaited()


@pytest.mark.anyio
async def test_post_agui_label_id_reports_an_unknown_label(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = True
    the_threads.update_label.side_effect = agui.UnknownLabel(404)

    with pytest.raises(fastapi.HTTPException) as exc:
        await labels_views.post_agui_label_id(
            label_id=404,
            updated_label=models.AGUI_UpdateLabelRequest(name="Blocked"),
            the_threads=the_threads,
            the_admin_users=the_admin_users,
            the_user_claims=THE_USER_CLAIMS,
            the_labels_logger=the_labels_logger,
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_delete_agui_label_id_deletes(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = True

    found = await labels_views.delete_agui_label_id(
        label_id=1,
        the_threads=the_threads,
        the_admin_users=the_admin_users,
        the_user_claims=THE_USER_CLAIMS,
        the_labels_logger=the_labels_logger,
    )

    assert found.status_code == 205

    the_threads.delete_label.assert_awaited_once_with(label_id=1)
    the_admin_users.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
        resource=loggers.AUDIT_RESOURCE_THREAD_LABEL,
        action=loggers.AUDIT_ACTION_DELETE,
    )


@pytest.mark.anyio
async def test_delete_agui_label_id_refuses_non_admins(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = False

    with pytest.raises(fastapi.HTTPException) as exc:
        await labels_views.delete_agui_label_id(
            label_id=1,
            the_threads=the_threads,
            the_admin_users=the_admin_users,
            the_user_claims=THE_USER_CLAIMS,
            the_labels_logger=the_labels_logger,
        )

    assert exc.value.status_code == 403

    the_threads.delete_label.assert_not_awaited()


@pytest.mark.anyio
async def test_delete_agui_label_id_reports_an_unknown_label(
    the_threads,
    the_admin_users,
    the_labels_logger,
):
    the_admin_users.check_admin_access.return_value = True
    the_threads.delete_label.side_effect = agui.UnknownLabel(404)

    with pytest.raises(fastapi.HTTPException) as exc:
        await labels_views.delete_agui_label_id(
            label_id=404,
            the_threads=the_threads,
            the_admin_users=the_admin_users,
            the_user_claims=THE_USER_CLAIMS,
            the_labels_logger=the_labels_logger,
        )

    assert exc.value.status_code == 404
