from __future__ import annotations

import pathlib
from unittest import mock

import pytest

from soliplex.cli.audit import non_local_paths as audit_non_local
from soliplex.config import agents as config_agents
from soliplex.config import completions as config_completions
from soliplex.config import exceptions as config_exc
from soliplex.config import rooms as config_rooms

CONFIG_DIR = pathlib.Path("rooms/foo")


def _agent_config(w_not_local):
    agent_config = mock.create_autospec(config_agents.AgentConfig, id="bar")

    if w_not_local:
        agent_config.get_system_prompt_path.side_effect = (
            config_exc.PathNotLocal(CONFIG_DIR, "./../prompt.txt")
        )

    return agent_config


def _room_config(room_id, agent_config, w_logo_not_local=False):
    room_config = mock.create_autospec(
        config_rooms.RoomConfig,
        id=room_id,
        agent_config=agent_config,
    )

    if w_logo_not_local:
        room_config.get_logo_image.side_effect = config_exc.PathNotLocal(
            CONFIG_DIR,
            "../logo.png",
        )

    return room_config


def test__non_local_path_finding():
    exc = config_exc.PathNotLocal(CONFIG_DIR, "../bar.png")

    found = audit_non_local._non_local_path_finding(exc)

    assert found == {"config_dir": str(CONFIG_DIR), "path": "../bar.png"}


@pytest.mark.parametrize(
    "w_not_local, exp_findings",
    [
        (False, {}),
        (
            True,
            {
                "system_prompt": {
                    "config_dir": str(CONFIG_DIR),
                    "path": "./../prompt.txt",
                },
            },
        ),
    ],
)
def test__agent_config_findings(w_not_local, exp_findings):
    agent_config = _agent_config(w_not_local)

    found = audit_non_local._agent_config_findings(agent_config)

    assert found == exp_findings
    agent_config.get_system_prompt_path.assert_called_once_with()


def test__agent_config_findings_w_factory_agent():
    agent_config = mock.create_autospec(config_agents.FactoryAgentConfig)

    found = audit_non_local._agent_config_findings(agent_config)

    assert found == {}


@pytest.mark.parametrize(
    "w_not_local, exp_reports",
    [
        (False, {}),
        (
            True,
            {
                "bar": {
                    "system_prompt": {
                        "config_dir": str(CONFIG_DIR),
                        "path": "./../prompt.txt",
                    },
                },
            },
        ),
    ],
)
def test__installation_reports(the_installation, w_not_local, exp_reports):
    i_config = the_installation._config
    i_config.agent_configs = [_agent_config(w_not_local)]

    found = audit_non_local._installation_reports(i_config)

    assert found == exp_reports


@pytest.mark.parametrize(
    "w_logo_not_local, w_prompt_not_local, exp_reports",
    [
        (False, False, {}),
        (
            True,
            False,
            {
                "foo": {
                    "logo_image": {
                        "config_dir": str(CONFIG_DIR),
                        "path": "../logo.png",
                    },
                },
            },
        ),
        (
            False,
            True,
            {
                "foo": {
                    "system_prompt": {
                        "config_dir": str(CONFIG_DIR),
                        "path": "./../prompt.txt",
                    },
                },
            },
        ),
        (
            True,
            True,
            {
                "foo": {
                    "logo_image": {
                        "config_dir": str(CONFIG_DIR),
                        "path": "../logo.png",
                    },
                    "system_prompt": {
                        "config_dir": str(CONFIG_DIR),
                        "path": "./../prompt.txt",
                    },
                },
            },
        ),
    ],
)
def test__room_reports(
    the_installation,
    w_logo_not_local,
    w_prompt_not_local,
    exp_reports,
):
    room_config = _room_config(
        "foo",
        _agent_config(w_prompt_not_local),
        w_logo_not_local=w_logo_not_local,
    )
    i_config = the_installation._config
    i_config.room_configs = {"foo": room_config}

    found = audit_non_local._room_reports(i_config)

    assert found == exp_reports
    room_config.get_logo_image.assert_called_once_with()


@pytest.mark.parametrize(
    "w_not_local, exp_reports",
    [
        (False, {}),
        (
            True,
            {
                "baz": {
                    "system_prompt": {
                        "config_dir": str(CONFIG_DIR),
                        "path": "./../prompt.txt",
                    },
                },
            },
        ),
    ],
)
def test__completion_reports(the_installation, w_not_local, exp_reports):
    compl_config = mock.create_autospec(
        config_completions.CompletionConfig,
        id="baz",
        agent_config=_agent_config(w_not_local),
    )
    i_config = the_installation._config
    i_config.completion_configs = {"baz": compl_config}

    found = audit_non_local._completion_reports(i_config)

    assert found == exp_reports


def test__non_local_path_reports(ctx, the_installation):
    room_config = _room_config("foo", _agent_config(True))
    i_config = the_installation._config
    i_config.agent_configs = [_agent_config(False)]
    i_config.room_configs = {"foo": room_config}
    i_config.completion_configs = {}

    found = audit_non_local._non_local_path_reports(ctx, the_installation)

    assert found == {
        audit_non_local.INSTALLATION: {},
        audit_non_local.ROOMS: {
            "foo": {
                "system_prompt": {
                    "config_dir": str(CONFIG_DIR),
                    "path": "./../prompt.txt",
                },
            },
        },
        audit_non_local.COMPLETIONS: {},
    }
    assert ctx.obj["non_local_path_reports"] is found


def test__non_local_path_reports_returns_the_cached_reports(
    ctx,
    the_installation,
):
    cached = ctx.obj["non_local_path_reports"] = {}

    found = audit_non_local._non_local_path_reports(ctx, the_installation)

    assert found is cached


@pytest.mark.parametrize(
    "reports, exp_findings",
    [
        ({audit_non_local.ROOMS: {}}, {}),
        (
            {audit_non_local.ROOMS: {"foo": {"logo_image": {}}}},
            {"rooms_non_local_paths": {"foo": {"logo_image": {}}}},
        ),
    ],
)
def test__non_local_path_findings(reports, exp_findings):
    found = audit_non_local._non_local_path_findings(
        reports,
        audit_non_local.ROOMS,
    )

    assert found == exp_findings


def test__non_local_prompt_ids():
    reports = {
        audit_non_local.ROOMS: {
            "logo_only": {"logo_image": {}},
            "prompt": {"system_prompt": {}},
            "both": {"logo_image": {}, "system_prompt": {}},
        },
    }

    found = audit_non_local._non_local_prompt_ids(
        reports,
        audit_non_local.ROOMS,
    )

    assert found == {"prompt", "both"}
