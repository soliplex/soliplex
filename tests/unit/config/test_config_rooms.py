import contextlib
import dataclasses
import warnings
from unittest import mock

import pytest
import yaml
from haiku.rag import config as hr_config
from haiku.rag.skills import rag as hr_skills_rag
from haiku.skills import models as hs_models

from soliplex.config import agents as config_agents
from soliplex.config import exceptions as config_exc
from soliplex.config import quizzes as config_quizzes
from soliplex.config import rooms as config_rooms
from soliplex.config import skills as config_skills
from soliplex.config import tools as config_tools
from tests.unit.config import test_config_agents as test_agents
from tests.unit.config import test_config_quizzes as test_quizzes
from tests.unit.config import test_config_skills as test_skills
from tests.unit.config import test_config_tools as test_tools

NoRaise = contextlib.nullcontext()


ROOM_ID = "test-room"
ROOM_NAME = "Test Room"
ROOM_DESCRIPTION = "This room is for testing"
WELCOME_MESSAGE = "Welcome to this room!"
SUGGESTION = "Try us out for a spin!"
IMAGE_FILENAME = "test_image.jpg"
AGUI_FEATURE_NAME = "test-agui-feature"
TOOL_AGUI_FEATURE_NAME = "test-tool-agui-feature"

BOGUS_ROOM_CONFIG_YAML = ""

BARE_ROOM_CONFIG_KW = {
    "id": ROOM_ID,
    "name": ROOM_NAME,
    "description": ROOM_DESCRIPTION,
    "agent_config": config_agents.AgentConfig(
        id=f"room-{ROOM_ID}",
        model_name=test_agents.MODEL_NAME,
        system_prompt=test_agents.SYSTEM_PROMPT,
    ),
}
BARE_ROOM_CONFIG_YAML = f"""\
id: "{ROOM_ID}"
name: "{ROOM_NAME}"
description: "{ROOM_DESCRIPTION}"
agent:
    model_name: "{test_agents.MODEL_NAME}"
    system_prompt: "{test_agents.SYSTEM_PROMPT}"
"""

W_NON_HR_SKILLS_ROOM_CONFIG_KW = BARE_ROOM_CONFIG_KW | {
    "skills": config_skills.RoomSkillsConfig(
        installation_skill_names=[test_skills.SKILL_NAME],
    ),
}
W_NON_HR_SKILLS_ROOM_CONFIG_YAML = f"""\
{BARE_ROOM_CONFIG_YAML}
skills:
    installation_skill_names:
        - "{test_skills.SKILL_NAME}"
"""

LANCE_DB_OVERRIDE_PATH = "/tmp/rag.lancedb"

W_HR_SKILLS_ROOM_CONFIG_KW = BARE_ROOM_CONFIG_KW | {
    "skills": config_skills.RoomSkillsConfig(
        _skill_configs={
            "rag": config_skills.HR_RAG_SkillConfig(
                rag_lancedb_override_path=LANCE_DB_OVERRIDE_PATH,
            ),
        }
    ),
}
W_HR_SKILLS_ROOM_CONFIG_YAML = f"""\
{BARE_ROOM_CONFIG_YAML}
skills:
    skill_configs:
        - kind: "haiku.rag.skills.rag"
          rag_lancedb_override_path: "{LANCE_DB_OVERRIDE_PATH}"
"""

W_NON_HR_TOOLS_ROOM_CONFIG_KW = BARE_ROOM_CONFIG_KW | {
    "tool_configs": {
        "get_current_datetime": config_tools.ToolConfig(
            tool_name="soliplex.tools.get_current_datetime",
            allow_mcp=True,
            agui_feature_names=(TOOL_AGUI_FEATURE_NAME,),
        ),
    },
}
W_NON_HR_TOOLS_ROOM_CONFIG_YAML = f"""\
{BARE_ROOM_CONFIG_YAML}
tools:
    - tool_name: "soliplex.tools.get_current_datetime"
      allow_mcp: true
      agui_feature_names:
          - "{TOOL_AGUI_FEATURE_NAME}"
"""

HR_CONFIG = hr_config.AppConfig(environment="testing")
W_HR_TOOLS_ROOM_CONFIG_KW = BARE_ROOM_CONFIG_KW | {
    "tool_configs": {
        "hr_tool": mock.create_autospec(
            config_tools.ToolConfig,
            rag_lancedb_path=LANCE_DB_OVERRIDE_PATH,
            haiku_rag_config=HR_CONFIG,
        ),
    },
}

EXTRA_AGUI_FEATURE_NAME = "extra-agui-feature"
FULL_ROOM_CONFIG_KW = {
    "id": ROOM_ID,
    "name": ROOM_NAME,
    "description": ROOM_DESCRIPTION,
    "welcome_message": WELCOME_MESSAGE,
    "suggestions": [
        SUGGESTION,
    ],
    "enable_attachments": True,
    "logo_image": f"./{IMAGE_FILENAME}",
    "agent_config": config_agents.AgentConfig(
        id=f"room-{ROOM_ID}",
        model_name=test_agents.MODEL_NAME,
        system_prompt=test_agents.SYSTEM_PROMPT,
        agui_feature_names=(AGUI_FEATURE_NAME,),
    ),
    "quizzes": [
        config_quizzes.QuizConfig(
            id=test_quizzes.TEST_QUIZ_ID,
            question_file=test_quizzes.TEST_QUIZ_OVR,
            judge_agent=config_agents.AgentConfig(
                id="test-quiz-judge",
                model_name=test_quizzes.TEST_QUIZ_MODEL_EXPLICIT,
                provider_base_url=test_quizzes.TEST_QUIZ_PROVIDER_BASE_URL,
            ),
        ),
    ],
    "_agui_feature_names": [
        EXTRA_AGUI_FEATURE_NAME,
    ],
    "allow_mcp": True,
    "tool_configs": {
        "get_current_datetime": config_tools.ToolConfig(
            tool_name="soliplex.tools.get_current_datetime",
            allow_mcp=True,
        ),
    },
    "mcp_client_toolset_configs": {
        "stdio_test": config_tools.Stdio_MCP_ClientToolsetConfig(
            command="cat",
            args=[
                "-",
            ],
            env={
                "foo": "bar",
            },
        ),
        "http_test": config_tools.HTTP_MCP_ClientToolsetConfig(
            url=test_tools.HTTP_MCP_URL,
            headers={
                "Authorization": "Bearer secret:BEARER_TOKEN",
            },
            query_params=test_tools.HTTP_MCP_QUERY_PARAMS,
        ),
        "sse_test": config_tools.SSE_MCP_ClientToolsetConfig(
            url=test_tools.HTTP_MCP_URL,
            headers={
                "Authorization": "Bearer secret:BEARER_TOKEN",
            },
            query_params=test_tools.HTTP_MCP_QUERY_PARAMS,
        ),
    },
    "skills": config_skills.RoomSkillsConfig(
        model_name=test_skills.SKILL_MODEL_NAME,
        installation_skill_names=[test_skills.SKILL_NAME],
    ),
}
FULL_ROOM_CONFIG_YAML = f"""\
id: "{ROOM_ID}"
name: "{ROOM_NAME}"
description: "{ROOM_DESCRIPTION}"
welcome_message: "{WELCOME_MESSAGE}"
suggestions:
  - "{SUGGESTION}"
enable_attachments: true
logo_image: "./{IMAGE_FILENAME}"
agent:
    model_name: "{test_agents.MODEL_NAME}"
    system_prompt: "{test_agents.SYSTEM_PROMPT}"
    agui_feature_names:
      - "{AGUI_FEATURE_NAME}"
tools:
    - tool_name: "soliplex.tools.get_current_datetime"
      allow_mcp: true
mcp_client_toolsets:
    stdio_test:
      kind: "stdio"
      command: "cat"
      args:
        - "-"
      env:
        foo: "bar"
    http_test:
      kind: "http"
      url: "{test_tools.HTTP_MCP_URL}"
      headers:
        Authorization: "Bearer secret:BEARER_TOKEN"
      query_params:
        {test_tools.HTTP_MCP_QP_KEY}: "{test_tools.HTTP_MCP_QP_VALUE}"
    sse_test:
      kind: "sse"
      url: "{test_tools.HTTP_MCP_URL}"
      headers:
        Authorization: "Bearer secret:BEARER_TOKEN"
      query_params:
        {test_tools.HTTP_MCP_QP_KEY}: "{test_tools.HTTP_MCP_QP_VALUE}"
skills:
    model_name: {test_skills.SKILL_MODEL_NAME}
    installation_skill_names:
        - "{test_skills.SKILL_NAME}"
quizzes:
  - id: "{test_quizzes.TEST_QUIZ_ID}"
    question_file: "{test_quizzes.TEST_QUIZ_OVR}"
    judge_agent:
        id: "test-quiz-judge"
        model_name: {test_quizzes.TEST_QUIZ_MODEL_EXPLICIT}
        provider_base_url: {test_quizzes.TEST_QUIZ_PROVIDER_BASE_URL}
agui_feature_names:
  - {EXTRA_AGUI_FEATURE_NAME}
allow_mcp: true
"""


@pytest.mark.parametrize(
    "config_yaml, expectation, w_depr",
    [
        (
            BOGUS_ROOM_CONFIG_YAML,
            pytest.raises(config_exc.FromYamlException),
            None,
        ),
        (
            BARE_ROOM_CONFIG_YAML,
            contextlib.nullcontext(BARE_ROOM_CONFIG_KW),
            False,
        ),
        (
            W_NON_HR_SKILLS_ROOM_CONFIG_YAML,
            contextlib.nullcontext(W_NON_HR_SKILLS_ROOM_CONFIG_KW),
            False,
        ),
        (
            W_HR_SKILLS_ROOM_CONFIG_YAML,
            contextlib.nullcontext(W_HR_SKILLS_ROOM_CONFIG_KW),
            False,
        ),
        (
            W_NON_HR_TOOLS_ROOM_CONFIG_YAML,
            contextlib.nullcontext(W_NON_HR_TOOLS_ROOM_CONFIG_KW),
            False,
        ),
        (
            FULL_ROOM_CONFIG_YAML,
            contextlib.nullcontext(FULL_ROOM_CONFIG_KW),
            False,
        ),
    ],
)
def test_roomconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expectation,
    w_depr,
):
    skill = mock.create_autospec(hs_models.Skill)
    skill_config = mock.create_autospec(
        config_skills._SkillConfigModelBase,
        skill=skill,
    )

    installation_config.skill_configs = {
        test_skills.SKILL_NAME: skill_config,
        "other_skill": object(),
    }

    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    with (
        warnings.catch_warnings(record=True) as warned,
        expectation as expected,
    ):
        found = config_rooms.RoomConfig.from_yaml(
            installation_config,
            yaml_file,
            config_dict,
        )

    if isinstance(expected, pytest.ExceptionInfo):
        assert expected.value._config_path == yaml_file

    else:
        expected = config_rooms.RoomConfig(**expected)
        expected = dataclasses.replace(
            expected,
            _installation_config=installation_config,
            _config_path=yaml_file,
        )

        expected.agent_config = dataclasses.replace(
            expected.agent_config,
            _installation_config=installation_config,
            _config_path=yaml_file,
        )

        for exp_quiz in expected.quizzes:
            exp_quiz.judge_agent = dataclasses.replace(
                exp_quiz.judge_agent,
                _installation_config=installation_config,
                _config_path=yaml_file,
            )

        for tool_config in expected.tool_configs.values():
            tool_config._installation_config = installation_config
            tool_config._config_path = yaml_file

        for mcts_config in expected.mcp_client_toolset_configs.values():
            mcts_config._installation_config = installation_config
            mcts_config._config_path = yaml_file

        if "skills" in config_yaml:
            replaced_skill_configs = {}
            for key, skill_config in expected.skills._skill_configs.items():
                replaced_skill_configs[key] = dataclasses.replace(
                    skill_config,
                    _installation_config=installation_config_w_skill,
                    _config_path=yaml_file,
                )
            expected.skills = dataclasses.replace(
                expected.skills,
                _installation_config=installation_config,
                _config_path=yaml_file,
                _skill_configs=replaced_skill_configs,
            )

        if "quizzes" in config_yaml:
            expected.quizzes = [
                dataclasses.replace(
                    qc,
                    _installation_config=installation_config,
                    _config_path=yaml_file,
                )
                for qc in expected.quizzes
            ]

        assert found == expected

        if w_depr:  # pragma: NO COVER
            (depr,) = warned
            assert depr.category is DeprecationWarning
        else:
            assert len(warned) == 0


@pytest.mark.parametrize("w_order", [False, True])
def test_roomconfig_sort_key(w_order):
    _ORDER = "explicitly_ordered"

    room_config_kw = BARE_ROOM_CONFIG_KW.copy()

    if w_order:
        room_config_kw["_order"] = _ORDER

    room_config = config_rooms.RoomConfig(**room_config_kw)

    found = room_config.sort_key

    if w_order:
        assert found == _ORDER
    else:
        assert found == ROOM_ID


def test_roomconfig_skill_configs_bare(installation_config):
    installation_config.skill_configs = {}

    room_config_kw = BARE_ROOM_CONFIG_KW.copy()
    room_config = config_rooms.RoomConfig(
        **room_config_kw,
        _installation_config=installation_config,
    )

    found = room_config.skill_configs

    assert found == {}


def test_roomconfig_skill_configs_w_hit(installation_config):
    skill_config = mock.create_autospec(config_skills._SkillConfigModelBase)
    installation_config.skill_configs = {
        test_skills.SKILL_NAME: skill_config,
        "other_skill": object(),
    }

    room_config_kw = FULL_ROOM_CONFIG_KW.copy()
    room_config_kw["skills"].entrypoint_skills = []
    room_config_kw["skills"]._installation_config = installation_config
    room_config = config_rooms.RoomConfig(
        **room_config_kw,
        _installation_config=installation_config,
    )

    found = room_config.skill_configs

    assert found == {test_skills.SKILL_NAME: skill_config}


@pytest.fixture
def installation_config_w_skill(installation_config):
    skill_config = mock.create_autospec(
        config_skills._SkillConfigModelBase,
        agui_feature_names=[test_skills.SKILL_STATE_NAMESPACE],
    )
    installation_config.skill_configs = {
        test_skills.SKILL_NAME: skill_config,
    }
    return installation_config


@pytest.mark.parametrize(
    "room_config_kwargs, expected",
    [
        (BARE_ROOM_CONFIG_KW.copy(), ()),
        (
            W_NON_HR_SKILLS_ROOM_CONFIG_KW.copy(),
            [
                # from 'skills' via installation_config
                test_skills.SKILL_STATE_NAMESPACE,
            ],
        ),
        (
            W_HR_SKILLS_ROOM_CONFIG_KW.copy(),
            [
                # from 'skills' via local config
                hr_skills_rag.STATE_NAMESPACE,
            ],
        ),
        (
            W_NON_HR_TOOLS_ROOM_CONFIG_KW.copy(),
            [
                # from 'tool_configs'
                TOOL_AGUI_FEATURE_NAME,
            ],
        ),
        (
            FULL_ROOM_CONFIG_KW.copy(),
            [
                # from 'agent_config'
                AGUI_FEATURE_NAME,
                # from 'skills' via installation_config
                test_skills.SKILL_STATE_NAMESPACE,
                # from 'room_config'
                EXTRA_AGUI_FEATURE_NAME,
            ],
        ),
    ],
)
def test_roomconfig_agui_feature_names(
    installation_config_w_skill,
    room_config_kwargs,
    expected,
):
    skills = room_config_kwargs.pop("skills", None)
    if skills is not None:
        room_config_kwargs["skills"] = dataclasses.replace(
            skills,
            _installation_config=installation_config_w_skill,
        )

    room_config = config_rooms.RoomConfig(
        _installation_config=installation_config_w_skill,
        **room_config_kwargs,
    )

    found = room_config.agui_feature_names

    assert set(found) == set(expected)


@pytest.mark.parametrize("w_existing", [False, True])
def test_roomconfig_quiz_map(w_existing):
    NUM_QUIZZES = 3
    quizzes = [
        mock.create_autospec(
            config_quizzes.QuizConfig,
            id=f"quiz-{iq}",
            question_file=f"ignored-{iq}.json",
        )
        for iq in range(NUM_QUIZZES)
    ]

    existing = object()
    room_config = config_rooms.RoomConfig(**BARE_ROOM_CONFIG_KW)

    if w_existing:
        room_config._quiz_map = existing
    else:
        room_config.quizzes = quizzes

    found = room_config.quiz_map

    if w_existing:
        assert found is existing

    else:
        for (_f_id, f_quiz), e_quiz in zip(
            found.items(),
            quizzes,
            strict=True,
        ):
            assert f_quiz is e_quiz


@pytest.mark.parametrize("w_config_path", [False, True])
@pytest.mark.parametrize(
    "room_config_kw",
    [BARE_ROOM_CONFIG_KW, FULL_ROOM_CONFIG_KW],
)
def test_roomconfig_get_logo_image(temp_dir, room_config_kw, w_config_path):
    room_config_kw = room_config_kw.copy()

    if w_config_path:
        room_config_kw["_config_path"] = temp_dir / "room_config.yaml"

    room_config = config_rooms.RoomConfig(**room_config_kw)

    if room_config._config_path:
        if room_config._logo_image is not None:
            expected = temp_dir / room_config._logo_image
        else:
            expected = None

        found = room_config.get_logo_image()

        assert found == expected

    else:
        if room_config._logo_image is not None:
            with pytest.raises(config_exc.NoConfigPath):
                room_config.get_logo_image()

        else:
            assert room_config.get_logo_image() is None


@pytest.mark.anyio
@pytest.mark.parametrize("incl_source_kwargs", [{}, {"include_source": True}])
@pytest.mark.parametrize(
    "room_config_kwargs, expected",
    [
        (BARE_ROOM_CONFIG_KW, []),
        (W_NON_HR_SKILLS_ROOM_CONFIG_KW, []),
        (
            W_HR_SKILLS_ROOM_CONFIG_KW,
            [
                {
                    "db_path": LANCE_DB_OVERRIDE_PATH,
                    "config": HR_CONFIG,
                    "read_only": True,
                    "source": "skill:rag",
                },
            ],
        ),
        (W_NON_HR_TOOLS_ROOM_CONFIG_KW, []),
        (
            W_HR_TOOLS_ROOM_CONFIG_KW,
            [
                {
                    "db_path": LANCE_DB_OVERRIDE_PATH,
                    "config": HR_CONFIG,
                    "read_only": True,
                    "source": "tool:hr_tool",
                },
            ],
        ),
        (FULL_ROOM_CONFIG_KW, []),
    ],
)
async def test_roomconfig_list_haiku_rag_client_kws(
    temp_dir,
    installation_config_w_skill,
    room_config_kwargs,
    incl_source_kwargs,
    expected,
):
    db_path = temp_dir / "rag.lancedb"
    db_path.mkdir()

    expected = [
        exp_kw | {"db_path": db_path} if "db_path" in exp_kw else exp_kw
        for exp_kw in expected
    ]

    if not incl_source_kwargs.get("include_source"):
        expected = [
            {key: value for key, value in exp_kw.items() if key != "source"}
            for exp_kw in expected
        ]

    skills = room_config_kwargs.pop("skills", None)
    if skills is not None:
        replaced_skill_configs = {}
        for key, skill_config in skills._skill_configs.items():
            replaced_skill_configs[key] = dataclasses.replace(
                skill_config,
                _installation_config=installation_config_w_skill,
                rag_lancedb_override_path=db_path,
                _haiku_rag_config=HR_CONFIG,
            )

        room_config_kwargs["skills"] = dataclasses.replace(
            skills,
            _installation_config=installation_config_w_skill,
            _skill_configs=replaced_skill_configs,
        )

    tool_configs = room_config_kwargs.get("tool_configs")
    if tool_configs is not None:
        for value in tool_configs.values():
            rldbp = getattr(value, "rag_lancedb_path", None)
            if rldbp is not None:
                value.rag_lancedb_path = db_path

    room_config = config_rooms.RoomConfig(
        _installation_config=installation_config_w_skill,
        **room_config_kwargs,
    )

    found = list(room_config.list_haiku_rag_client_kw(**incl_source_kwargs))

    assert found == expected
