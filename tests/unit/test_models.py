import dataclasses
import datetime
import json
import pathlib
import uuid
from unittest import mock

import pydantic
import pytest
from ag_ui import core as agui_core
from haiku.skills import models as hs_models

from soliplex import agui as agui_package
from soliplex import config
from soliplex import models

NOW = datetime.datetime.now(datetime.UTC)

QUIZ_ID = "test_quiz"
QUIZ_TITLE = "Test Quiz"
QUIZ_MAX_QUESTIONS = 14
QUIZ_PATH_OVERRIDE = "/dev/null"
INPUTS = "What color is the sky"
EXPECTED_ANSWER = "Blue"
QA_QUESTION_UUID = "DEADBEEF"
MC_QUESTION_UUID = "FACEDACE"
QUESTION_TYPE_QA = "qa"
QUESTION_TYPE_MC = "multiple-choice"
MC_OPTIONS = ["orange", "blue", "purple"]

FEATURE_NAME = "feature_name"
SKILL_NAME = "skill_name"
SKILL_DESC = "This is a skill"
SKILL_LICENSE = "Foo License v3.14"
SKILL_COMPAT = "Skill compat"
TOOL_ONE = "tool-one"
TOOL_TWO = "tool-two"
SKILL_META = {"foo": "bar"}
SKILL_MODEL_NAME = "test-skill-model"
SKILL_STATE_NAMESPACE = "test-skill-namespace"

ROOM_ID = "test_room"
ROOM_NAME = "Test Room"
ROOM_DESCRIPTION = "This room is made for testing"
ROOM_WELCOME = "Welcome!"
ROOM_SUGGESTION = "Why is the sky blue?"

COMPLETION_ID = "test_room"
COMPLETION_NAME = "Test Room"

AGENT_ID = "test_agent"
AGENT_MODEL = "test_model"
AGENT_PROMPT = "You are a test"
AGENT_RETRIES = 7
AGENT_BASE_URL = "https://provider.example.com/base"
OLLAMA_BASE_URL = "https://ollama.example.com/base"
HAIKU_RAG_CONFIG_FILE = "/path/to/haiku.rag.yaml"
OTHER_AGENT_KIND = "other-agent-kind"

FACTORY_NAME = "some.package.function"

AGUI_FEATURE_NAME = "test-agui-feature"
AGUI_FEATURE_DESCRIPTION = "This is a test AG-UI feature"
AGUI_FEATURE_MODEL_KLASS = "soliplex.agui.features.testing"

INSTALLATION_ID = "test-installation"
INSTALLATION_SECRET = "Seeeeeekrit!"
INSTALLATION_ENVVAR_NAME = "TEST_ENVVAR"
INSTALLATION_ENVVAR_STR_VALUE = "Test Envvar"
INSTALLATION_ENVVAR_INT_VALUE = 54321
INSTALLATION_AGENT_ID = "test-agent"
INSTALLATION_AGENT_MODEL_NAME = "test-agent-model"
INSTALLATION_AGENT_SYSTEM_PROMPT = "You are a test!"
INSTALLATION_OIDC_PATH = pathlib.Path("/path/to/oidc")
INSTALLATION_ROOM_PATH = pathlib.Path("/path/to/rooms")
INSTALLATION_COMPLETION_PATH = pathlib.Path("/path/to/completions")
INSTALLATION_QUIZZES_PATH = pathlib.Path("/path/to/quizzes")

INSTALLATION_OIDC_AUTH_SYSTEM_ID = "oidc-test"
INSTALLATION_OIDC_AUTH_SYSTEM_TITLE = "OIDC Test"
INSTALLATION_OIDC_AUTH_SYSTEM_SERVER_URL = "https://oidc.example.com/"
INSTALLATION_OIDC_AUTH_SYSTEM_TOKEN_VALIDATION_PEM = "PEM GOES HERE"
INSTALLATION_OIDC_AUTH_SYSTEM_CLIENT_ID = "oicd-client-test"
INSTALLATION_OIDC_AUTH_SYSTEM_SCOPE = "oicd-client-scope"
INSTALLATION_OIDC_AUTH_SYSTEM_CONFIG = config.OIDCAuthSystemConfig(
    id=INSTALLATION_OIDC_AUTH_SYSTEM_ID,
    title=INSTALLATION_OIDC_AUTH_SYSTEM_TITLE,
    server_url=INSTALLATION_OIDC_AUTH_SYSTEM_SERVER_URL,
    token_validation_pem=INSTALLATION_OIDC_AUTH_SYSTEM_TOKEN_VALIDATION_PEM,
    client_id=INSTALLATION_OIDC_AUTH_SYSTEM_CLIENT_ID,
    client_secret="SHHHHHHH! DON't SHOW ME",
    scope=INSTALLATION_OIDC_AUTH_SYSTEM_SCOPE,
)
INSTALLATION_TP_DBURI_SYNC = "sqlite:////tmp/test-models.sqlite"
INSTALLATION_TP_DBURI_ASYNC = "sqlite+aiosqlite:////tmp/test-models.sqlite"

LOGGING_CONFIG_FILE = "./logging.yaml"
LOGGING_HEADERS_MAP = {"request_id": "X-Request-ID"}
LOGGING_CLAIMS_MAP = {"user_id": "email"}

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

AUTH_USER_CLAIMS = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}

UNKNOWN_USER_PROFILE_KW = {
    "preferred_username": "<unknown>",
    "given_name": "<unknown>",
    "family_name": "<unknown>",
    "email": "<unknown>",
}

CONVO_UUID = uuid.uuid4()
USER_TEXT = "Why is the sky blue?"
CONVO_NAME = USER_TEXT
CONVO_ROOM_ID = "test-room"
TIMESTAMP = "2025-09-30T18:18:27Z"

AGUI_THREAD_ID = "test-thread"
AGUI_RUN_ID = "test-run"
AGUI_PARENT_RUN_ID = "test-parent-run"

EMPTY_AGUI_RUN_INPUT = agui_core.RunAgentInput(
    thread_id=AGUI_THREAD_ID,
    run_id=AGUI_RUN_ID,
    state={},
    messages=[],
    tools=[],
    context=[],
    forwarded_props=None,
)

E_RUN_STARTED = agui_core.RunStartedEvent(
    thread_id=AGUI_THREAD_ID,
    run_id=AGUI_RUN_ID,
)
E_RUN_FINISHED = agui_core.RunFinishedEvent(
    thread_id=AGUI_THREAD_ID,
    run_id=AGUI_RUN_ID,
)
AGUI_EVENTS = [
    E_RUN_STARTED,
    E_RUN_FINISHED,
]


def _make_run(**kw):
    return mock.create_autospec(agui_package.Run, **kw)


AGUI_RUNS = {
    AGUI_RUN_ID: _make_run(
        thread_id=AGUI_THREAD_ID,
        run_id=AGUI_RUN_ID,
        created=NOW,
        finished=None,
        parent_run_id=None,
        run_metadata=None,
        run_input=EMPTY_AGUI_RUN_INPUT.model_copy(deep=True),
        _events=AGUI_EVENTS,
    ),
}


RUN_LABEL = "run-label"
AGUI_RUN_METADATA = mock.create_autospec(
    agui_package.RunMetadata,
    label=RUN_LABEL,
)


THREAD_NAME = "thread-name"
THREAD_DESC = "Thread description"


def _make_thread_meta(name, description=None):
    class TestThreadMeta:
        def __init__(self, name, description):
            self.name = name
            self.description = description

    return TestThreadMeta(name, description)


WO_DESC_AGUI_THREAD_METADATA = _make_thread_meta(name=THREAD_NAME)

FULL_AGUI_THREAD_METADATA = _make_thread_meta(
    name=THREAD_NAME,
    description=THREAD_DESC,
)


def _make_thread(**kw):
    return mock.create_autospec(agui_package.Thread, **kw)


def _from_param(request, key):
    kw = {}
    if request.param is not None:
        kw[key] = request.param
    return kw


@pytest.fixture
def run_input():
    return EMPTY_AGUI_RUN_INPUT.model_copy(deep=True)


@pytest.fixture
def qa_question():
    return config.QuizQuestion(
        inputs=INPUTS,
        expected_output=EXPECTED_ANSWER,
        metadata=config.QuizQuestionMetadata(
            uuid=QA_QUESTION_UUID,
            type=QUESTION_TYPE_QA,
            options=None,
        ),
    )


@pytest.fixture
def mc_question():
    return config.QuizQuestion(
        inputs=INPUTS,
        expected_output=EXPECTED_ANSWER,
        metadata=config.QuizQuestionMetadata(
            uuid=MC_QUESTION_UUID,
            type=QUESTION_TYPE_MC,
            options=MC_OPTIONS,
        ),
    )


@pytest.fixture
def quiz_questions(qa_question, mc_question):
    return [qa_question, mc_question]


@pytest.fixture
def quiz_json(quiz_questions):
    return {
        "cases": [dataclasses.asdict(question) for question in quiz_questions]
    }


@pytest.fixture
def quiz_path(temp_dir, quiz_json):
    quizzes_path = temp_dir / "quizzes"
    quizzes_path.mkdir()
    populated_quiz = quizzes_path / f"{QUIZ_ID}.json"
    populated_quiz.write_text(json.dumps(quiz_json))
    return populated_quiz


@pytest.fixture(params=[None, False, True])
def quiz_randomize(request):
    return _from_param(request, "randomize")


@pytest.fixture(params=[None, QUIZ_MAX_QUESTIONS])
def quiz_max_questions(request):
    return _from_param(request, "max_questions")


def test_quizquestion_from_config():
    question_config = config.QuizQuestion(
        inputs="What color is the sky?",
        expected_output="Blue",
        metadata=config.QuizQuestionMetadata(
            type=config.QuizQuestionType.QA,
            uuid=QA_QUESTION_UUID,
            options=[],
        ),
    )

    question_model = models.QuizQuestion.from_config(question_config)

    assert question_model.inputs == question_config.inputs
    assert question_model.expected_output == question_config.expected_output
    assert question_model.metadata.type == str(config.QuizQuestionType.QA)
    assert question_model.metadata.uuid == QA_QUESTION_UUID
    assert question_model.metadata.options == []


def test_quiz_from_config(
    quiz_path,
    quiz_json,
    quiz_questions,
    quiz_randomize,
    quiz_max_questions,
):
    quiz_config = config.QuizConfig(
        id=QUIZ_ID,
        title=QUIZ_TITLE,
        _question_file_path_override=str(quiz_path),
        **quiz_randomize,
        **quiz_max_questions,
    )

    quiz_model = models.Quiz.from_config(quiz_config)

    assert quiz_model.id == QUIZ_ID
    assert quiz_model.title == QUIZ_TITLE

    if quiz_randomize:
        assert quiz_model.randomize == quiz_randomize["randomize"]
    else:
        assert quiz_model.randomize is False

    if quiz_max_questions:
        assert quiz_model.max_questions == quiz_max_questions["max_questions"]
    else:
        assert quiz_model.max_questions is None

    exp_questions = [
        models.QuizQuestion.from_config(quiz_question)
        for quiz_question in quiz_questions
    ]
    if quiz_randomize:
        for expected in exp_questions:
            assert expected in quiz_model.questions
    else:
        assert quiz_model.questions == exp_questions


def test_tool_from_config_w_toolconfig():
    def test_tool():
        """This is a test tool"""

    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        tool_model = models.Tool.from_config(tool_config)

    assert tool_model.kind == "test_tool"
    assert tool_model.tool_name == "soliplex.tools.test_tool"
    assert tool_model.tool_description == test_tool.__doc__.strip()
    assert tool_model.tool_requires == config.ToolRequires.BARE
    assert tool_model.allow_mcp is False
    assert tool_model.agui_feature_names == []
    assert tool_model.extra_parameters == {}


def test_mcp_client_toolset_from_config_w_toolconfig():
    def test_tool():
        """This is a test tool"""

    mcp_ct_config = config.Stdio_MCP_ClientToolsetConfig(
        command="cat",
        args=["-"],
        env={"foo": "env:not_in_my_environment_really"},
    )

    toolset_model = models.MCPClientToolset.from_config(mcp_ct_config)

    assert toolset_model.kind == mcp_ct_config.kind
    assert toolset_model.allowed_tools == mcp_ct_config.allowed_tools

    params = toolset_model.toolset_params
    assert params["command"] == mcp_ct_config.command
    assert params["args"] == mcp_ct_config.args
    # No interpolation!
    assert params["env"] == mcp_ct_config.env


def test_mcp_client_toolset_from_config_w_sdtc():
    mcp_ct_config = config.HTTP_MCP_ClientToolsetConfig(
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer env:{BEARER_TOKEN}"},
        query_params={"foo": "env:not_in_my_environment_really"},
    )

    toolset_model = models.MCPClientToolset.from_config(mcp_ct_config)

    assert toolset_model.kind == mcp_ct_config.kind
    assert toolset_model.allowed_tools == mcp_ct_config.allowed_tools

    params = toolset_model.toolset_params
    assert params["url"] == mcp_ct_config.url
    # No interpolation on either of these!
    assert params["headers"] == mcp_ct_config.headers
    assert params["query_params"] == mcp_ct_config.query_params


@pytest.fixture(params=[None, SKILL_META])
def w_metadata(request):
    return request.param


@pytest.fixture(params=[[], [TOOL_ONE, TOOL_TWO]])
def w_allowed_tools(request):
    return request.param


class StateModelTest(pydantic.BaseModel):
    pass


@pytest.fixture(
    params=[
        {},
        {
            "state_type": StateModelTest,
            "state_namespace": SKILL_STATE_NAMESPACE,
        },
    ]
)
def w_state_model_and_ns(request):
    return request.param


@pytest.fixture
def filesystem_skill_config(
    temp_dir,
    w_metadata,
    w_allowed_tools,
    w_state_model_and_ns,
):
    skill_path = temp_dir / "skills" / SKILL_NAME
    skill_metadata = mock.create_autospec(
        hs_models.SkillMetadata,
        description=SKILL_DESC,
        license=SKILL_LICENSE,
        compatibility=SKILL_COMPAT,
        allowed_tools=w_allowed_tools,
        metadata=w_metadata,
    )
    skill_metadata.name = SKILL_NAME  # mock quirk
    return config.FilesystemSkillConfig(
        skill_name=SKILL_NAME,
        _skill_metadata=skill_metadata,
        _skill_path=skill_path,
        model_name=SKILL_MODEL_NAME,
        **w_state_model_and_ns,
    )


def test_skill_from_config_w_fssc(filesystem_skill_config):
    found = models.Skill.from_config(filesystem_skill_config)

    assert found.source == hs_models.SkillSource.FILESYSTEM
    assert found.skill_name == filesystem_skill_config.skill_name
    assert found.description == filesystem_skill_config.description
    assert found.license == filesystem_skill_config.license
    assert found.compatibility == filesystem_skill_config.compatibility
    assert found.allowed_tools == " ".join(
        filesystem_skill_config.allowed_tools,
    )
    assert found.metadata == filesystem_skill_config.metadata

    if filesystem_skill_config.state_type is not None:
        assert found.state_type_schema == StateModelTest.model_json_schema()
    else:
        assert found.state_type_schema is None

    assert found.state_namespace == filesystem_skill_config.state_namespace


@pytest.fixture
def entrypoint_skill_config(
    w_metadata,
    w_allowed_tools,
):
    skill_metadata = mock.create_autospec(
        hs_models.SkillMetadata,
        description=SKILL_DESC,
        license=SKILL_LICENSE,
        compatibility=SKILL_COMPAT,
        allowed_tools=w_allowed_tools,
        metadata=w_metadata,
    )
    skill_metadata.name = SKILL_NAME  # mock quirk
    return config.EntrypointSkillConfig(
        skill_name=SKILL_NAME,
        _skill_metadata=skill_metadata,
        model_name=SKILL_MODEL_NAME,
        state_type=StateModelTest,
        state_namespace=SKILL_STATE_NAMESPACE,
    )


def test_skill_from_config_w_epsc(entrypoint_skill_config):
    found = models.Skill.from_config(entrypoint_skill_config)

    assert found.source == hs_models.SkillSource.ENTRYPOINT
    assert found.skill_name == entrypoint_skill_config.skill_name
    assert found.description == entrypoint_skill_config.description
    assert found.license == entrypoint_skill_config.license
    assert found.compatibility == entrypoint_skill_config.compatibility
    assert found.allowed_tools == " ".join(
        entrypoint_skill_config.allowed_tools,
    )
    assert found.metadata == entrypoint_skill_config.metadata
    assert found.state_type_schema == StateModelTest.model_json_schema()
    assert found.state_namespace == SKILL_STATE_NAMESPACE


@pytest.fixture(params=[None, AGENT_RETRIES])
def agent_retries(request):
    return _from_param(request, "retries")


@pytest.fixture
def installation_config():
    environ = {"OLLAMA_BASE_URL": OLLAMA_BASE_URL}
    installation = mock.create_autospec(config.InstallationConfig)
    installation.get_environment = environ.get
    return installation


@pytest.mark.parametrize(
    "agent_provider_kw, exp_base",
    [
        (  # Ollama, default URL
            {
                "provider_type": config.LLMProviderType.OLLAMA,
            },
            f"{OLLAMA_BASE_URL}/v1",
        ),
        (  # Ollama, explicit URL
            {
                "provider_type": config.LLMProviderType.OLLAMA,
                "provider_base_url": AGENT_BASE_URL,
            },
            f"{AGENT_BASE_URL}/v1",
        ),
        (  # OpenAI, no URL
            {
                "provider_type": config.LLMProviderType.OPENAI,
            },
            None,
        ),
        (  # OpenAI, explicit URL
            {
                "provider_type": config.LLMProviderType.OPENAI,
                "provider_base_url": AGENT_BASE_URL,
            },
            f"{AGENT_BASE_URL}/v1",
        ),
        (  # Google, no URL
            {
                "provider_type": config.LLMProviderType.GOOGLE,
            },
            None,
        ),
    ],
)
def test_defaultagent_from_config(
    agent_retries,
    installation_config,
    agent_provider_kw,
    exp_base,
):
    agent_config = config.AgentConfig(
        id=AGENT_ID,
        model_name=AGENT_MODEL,
        system_prompt=AGENT_PROMPT,
        _installation_config=installation_config,
        **agent_retries,
        **agent_provider_kw,
    )

    if not agent_retries:
        exp_retries = 3
    else:
        exp_retries = AGENT_RETRIES

    agent_model = models.DefaultAgent.from_config(agent_config)

    assert agent_model.id == AGENT_ID
    assert agent_model.model_name == AGENT_MODEL
    assert agent_model.retries == exp_retries
    assert agent_model.system_prompt == AGENT_PROMPT
    assert agent_model.provider_base_url == exp_base


class FeatureModel(pydantic.BaseModel):
    """Feature model for testing"""

    foo: str
    bar: str | None = None

    @classmethod
    def model_json_schema(cls):
        return {
            "type": "object",
            "title": cls.__name__,
            "description": cls.__doc__,
            "properties": {
                "foo": {
                    "title": "Foo",
                    "type": "string",
                },
                "bar": {
                    "title": "Bar",
                    "anyOf:": [
                        {"type": "string"},
                        {"type": "null"},
                    ],
                    "default": None,
                },
            },
        }


@pytest.fixture
def the_agui_feature():
    return config.AGUI_Feature(
        name=AGUI_FEATURE_NAME,
        model_klass=FeatureModel,
        source=config.AGUI_FeatureSource.CLIENT,
    )


def test_aguifeature_from_config(the_agui_feature):
    feature_model = models.AGUI_Feature.from_config(the_agui_feature)

    assert feature_model.name == AGUI_FEATURE_NAME
    assert feature_model.description == the_agui_feature.description
    assert feature_model.source == the_agui_feature.source
    assert feature_model.json_schema == FeatureModel.model_json_schema()


@pytest.fixture(params=[False, True])
def with_agent_config(request):
    return _from_param(request, "with_agent_config")


@pytest.fixture(params=[None, {"foo": "Bar"}])
def extra_config(request):
    return _from_param(request, "extra_config")


def test_factoryagent_from_config(
    installation_config,
    with_agent_config,
    extra_config,
):
    agent_config = config.FactoryAgentConfig(
        id=AGENT_ID,
        factory_name=FACTORY_NAME,
        _installation_config=installation_config,
        **with_agent_config,
        **extra_config,
    )

    exp_with_agent_config = with_agent_config["with_agent_config"]
    if not extra_config:
        exp_extra = {}
    else:
        exp_extra = extra_config["extra_config"]

    agent_model = models.FactoryAgent.from_config(agent_config)

    assert agent_model.id == AGENT_ID
    assert agent_model.factory_name == FACTORY_NAME
    assert agent_model.with_agent_config == exp_with_agent_config
    assert agent_model.extra_config == exp_extra


def test_otheragent_from_config(
    installation_config,
):
    agent_config = mock.Mock(
        spec_set=["id", "kind"],
        id=AGENT_ID,
        kind=OTHER_AGENT_KIND,
    )

    agent_model = models.OtherAgent.from_config(agent_config)

    assert agent_model.id == AGENT_ID
    assert agent_model.kind == OTHER_AGENT_KIND


@pytest.fixture
def gcd_tool_config():
    return config.ToolConfig(
        tool_name="soliplex.tools.get_current_datetime",
        agui_feature_names=(FEATURE_NAME,),
    )


@pytest.fixture
def a_quiz(quiz_path):
    return config.QuizConfig(
        id=QUIZ_ID,
        title=QUIZ_TITLE,
        _question_file_path_override=str(quiz_path),
    )


@pytest.fixture(params=[None, False, True])
def room_allow_mcp(request):
    return _from_param(request, "allow_mcp")


@pytest.fixture
def default_agent(installation_config):
    return config.AgentConfig(
        id=AGENT_ID,
        model_name=AGENT_MODEL,
        system_prompt=AGENT_PROMPT,
        _installation_config=installation_config,
    )


@pytest.fixture
def factory_agent(installation_config):
    return config.FactoryAgentConfig(
        id=AGENT_ID,
        factory_name=FACTORY_NAME,
        with_agent_config=False,
        _installation_config=installation_config,
    )


@pytest.fixture
def w_agui_features_agent(installation_config):
    return mock.Mock(
        spec_set=["id", "kind", "agui_feature_names"],
        id=AGENT_ID,
        kind=OTHER_AGENT_KIND,
        agui_feature_names=(AGUI_FEATURE_NAME,),
    )


@pytest.fixture(params=["default", "factory", "other"])
def which_agent(
    request,
    default_agent,
    factory_agent,
    w_agui_features_agent,
):
    if request.param == "default":
        return default_agent
    elif request.param == "factory":
        return factory_agent
    else:
        return w_agui_features_agent


@pytest.fixture
def room_ic():
    return config.InstallationConfig(
        id=INSTALLATION_ID,
        oidc_paths=[],
        room_paths=[],
        completion_paths=[],
        quizzes_paths=[],
        _available_filesystem_skill_configs={},
        _available_entrypoint_skill_configs={},
        _skill_configs={},
    )


def test_room_from_config_bare(room_ic, which_agent):
    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=which_agent,
        _installation_config=room_ic,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.id == ROOM_ID
    assert room_model.name == ROOM_NAME
    assert room_model.description == ROOM_DESCRIPTION
    assert room_model.suggestions == []
    assert room_model.tools == {}
    assert room_model.skills == {}

    agent_model = room_model.agent

    assert agent_model.id == AGENT_ID

    if which_agent.kind == "default":
        assert agent_model.model_name == AGENT_MODEL
        assert agent_model.system_prompt == AGENT_PROMPT
        assert agent_model.agui_feature_names == []
    elif which_agent.kind == "factory":
        assert agent_model.factory_name == FACTORY_NAME
        assert agent_model.with_agent_config is False
        assert agent_model.extra_config == {}
        assert agent_model.agui_feature_names == []
    else:
        assert agent_model.kind == OTHER_AGENT_KIND
        assert agent_model.agui_feature_names == list(
            which_agent.agui_feature_names
        )

    assert room_model.welcome_message == ROOM_DESCRIPTION


def test_room_from_config_w_welcome(room_ic, default_agent):
    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=default_agent,
        welcome_message=ROOM_WELCOME,
        _installation_config=room_ic,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.welcome_message == ROOM_WELCOME


def test_room_from_config_w_suggestions(room_ic, default_agent):
    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=default_agent,
        suggestions=[ROOM_SUGGESTION],
        _installation_config=room_ic,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.suggestions == [ROOM_SUGGESTION]


def test_room_from_config_w_tools(room_ic, default_agent, gcd_tool_config):
    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=default_agent,
        tool_configs={"get_current_datetime": gcd_tool_config},
        _installation_config=room_ic,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.tools == {
        "get_current_datetime": models.Tool.from_config(gcd_tool_config),
    }

    assert room_model.agui_feature_names == [FEATURE_NAME]


def test_room_from_config_w_fs_skills(
    room_ic,
    default_agent,
    filesystem_skill_config,
):
    room_ic._skill_configs[SKILL_NAME] = filesystem_skill_config

    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=default_agent,
        skills=config.RoomSkillsConfig(
            skill_names=[SKILL_NAME],
            _installation_config=room_ic,
        ),
        _installation_config=room_ic,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.skills == {
        SKILL_NAME: models.Skill.from_config(filesystem_skill_config),
    }


def test_room_from_config_w_ep_skills(
    room_ic,
    default_agent,
    entrypoint_skill_config,
):
    room_ic._skill_configs[SKILL_NAME] = entrypoint_skill_config

    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=default_agent,
        skills=config.RoomSkillsConfig(
            skill_names=[SKILL_NAME],
            _installation_config=room_ic,
        ),
        _installation_config=room_ic,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.skills == {
        SKILL_NAME: models.Skill.from_config(entrypoint_skill_config),
    }


def test_room_from_config_w_quizzes(room_ic, default_agent, a_quiz):
    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=default_agent,
        quizzes=[a_quiz],
        _installation_config=room_ic,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.quizzes == {a_quiz.id: models.Quiz.from_config(a_quiz)}


def test_room_from_config_w_allow_mcp(room_ic, default_agent, room_allow_mcp):
    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=default_agent,
        **room_allow_mcp,
        _installation_config=room_ic,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.allow_mcp == room_config.allow_mcp


def test_completion_from_config_bare(which_agent):
    completion_config = config.CompletionConfig(
        id=COMPLETION_ID,
        name=COMPLETION_NAME,
        agent_config=which_agent,
    )

    completion_model = models.Completion.from_config(completion_config)

    assert completion_model.id == ROOM_ID
    assert completion_model.name == ROOM_NAME

    agent_model = completion_model.agent
    assert agent_model.id == AGENT_ID

    if which_agent.kind == "default":
        assert agent_model.model_name == AGENT_MODEL
        assert agent_model.system_prompt == AGENT_PROMPT
    elif which_agent.kind == "factory":
        assert agent_model.factory_name == FACTORY_NAME
        assert agent_model.with_agent_config is False
        assert agent_model.extra_config == {}
    else:
        assert agent_model.kind == OTHER_AGENT_KIND
        assert agent_model.agui_feature_names == list(
            which_agent.agui_feature_names
        )

    assert completion_model.tools == {}


def test_completion_from_config_w_tools(default_agent, gcd_tool_config):
    completion_config = config.CompletionConfig(
        id=COMPLETION_ID,
        name=COMPLETION_NAME,
        agent_config=default_agent,
        tool_configs={"get_current_datetime": gcd_tool_config},
    )

    completion_model = models.Completion.from_config(completion_config)

    assert completion_model.tools == {
        "get_current_datetime": models.Tool.from_config(gcd_tool_config)
    }


@pytest.fixture
def bare_installation_config():
    return config.InstallationConfig(
        id=INSTALLATION_ID,
        oidc_paths=[],
        room_paths=[],
        completion_paths=[],
        quizzes_paths=[],
    )


def test_installation_from_config_bare(bare_installation_config):
    installation_model = models.Installation.from_config(
        bare_installation_config,
    )

    assert installation_model.id == INSTALLATION_ID
    assert installation_model.secrets == []
    assert installation_model.environment == {}
    assert installation_model.haiku_rag_config_file is None
    assert installation_model.agents == []
    assert installation_model.oidc_paths == []
    assert installation_model.room_paths == []
    assert installation_model.completion_paths == []
    assert installation_model.quizzes_paths == []
    assert installation_model.oidc_auth_systems == []
    assert (
        installation_model.thread_persistence_dburi_sync
        == config.SYNC_MEMORY_ENGINE_URL
    )
    assert (
        installation_model.thread_persistence_dburi_async
        == config.ASYNC_MEMORY_ENGINE_URL
    )
    assert installation_model.logging_config_file is None
    assert installation_model.logging_headers_map == {}
    assert installation_model.logging_claims_map == {}


@pytest.fixture
def a_secret():
    return config.SecretConfig(secret_name=INSTALLATION_SECRET)


def test_installation_from_config_w_secrets(
    bare_installation_config,
    a_secret,
):
    installation_config = bare_installation_config
    installation_config.secrets = [a_secret]

    installation_model = models.Installation.from_config(
        installation_config,
    )

    for m_secret, c_secret in zip(
        installation_model.secrets,
        installation_config.secrets,
        strict=True,
    ):
        assert m_secret.secret_name == c_secret.secret_name


@pytest.fixture
def an_environment_str():
    return {INSTALLATION_ENVVAR_NAME: INSTALLATION_ENVVAR_STR_VALUE}


@pytest.fixture
def an_environment_int():
    return {INSTALLATION_ENVVAR_NAME: INSTALLATION_ENVVAR_INT_VALUE}


def test_installation_from_config_w_environment_str(
    bare_installation_config,
    an_environment_str,
):
    installation_config = bare_installation_config
    installation_config.environment = an_environment_str

    installation_model = models.Installation.from_config(
        installation_config,
    )

    assert installation_model.environment == an_environment_str


def test_installation_from_config_w_environment_int(
    bare_installation_config,
    an_environment_int,
):
    installation_config = bare_installation_config
    installation_config.environment = an_environment_int

    installation_model = models.Installation.from_config(
        installation_config,
    )

    assert installation_model.environment == an_environment_int


def test_installation_from_config_w_haiku_rag_config_file(
    bare_installation_config,
):
    hr_config_file = pathlib.Path(HAIKU_RAG_CONFIG_FILE)
    installation_config = bare_installation_config
    installation_config._haiku_rag_config_file = hr_config_file

    installation_model = models.Installation.from_config(
        installation_config,
    )

    assert installation_model.haiku_rag_config_file == hr_config_file


@pytest.fixture(
    params=[
        config.AgentConfig(
            id=INSTALLATION_AGENT_ID,
            model_name=INSTALLATION_AGENT_MODEL_NAME,
            system_prompt=INSTALLATION_AGENT_SYSTEM_PROMPT,
            provider_type=config.LLMProviderType.OLLAMA,
            provider_base_url=AGENT_BASE_URL,
        ),
        config.FactoryAgentConfig(
            id=INSTALLATION_AGENT_ID,
            factory_name=FACTORY_NAME,
            with_agent_config=False,
        ),
    ]
)
def installation_agent(request):
    return request.param


def test_installation_from_config_w_agent(
    bare_installation_config,
    installation_agent,
):
    installation_config = bare_installation_config
    installation_config.agent_configs = [installation_agent]

    installation_model = models.Installation.from_config(
        installation_config,
    )

    (m_agent,) = installation_model.agents

    if isinstance(installation_agent, config.FactoryAgentConfig):
        assert m_agent.factory_name == installation_agent.factory_name
    else:
        assert m_agent.model_name == installation_agent.model_name


def test_installation_from_config_w_oidc_path_and_system(
    bare_installation_config,
):
    oidc_config = INSTALLATION_OIDC_AUTH_SYSTEM_CONFIG
    installation_config = bare_installation_config
    installation_config.oidc_paths = [INSTALLATION_OIDC_PATH]
    installation_config._oidc_auth_system_configs = [oidc_config]

    installation_model = models.Installation.from_config(
        installation_config,
    )

    assert installation_model.oidc_paths == [INSTALLATION_OIDC_PATH]
    assert installation_model.oidc_auth_systems == [
        models.OIDCAuthSystem.from_config(oidc_config),
    ]


def test_installation_from_config_w_room_path(bare_installation_config):
    installation_config = bare_installation_config
    installation_config.room_paths = [INSTALLATION_ROOM_PATH]

    installation_model = models.Installation.from_config(
        installation_config,
    )

    assert installation_model.room_paths == [INSTALLATION_ROOM_PATH]


def test_installation_from_config_w_completion_path(bare_installation_config):
    installation_config = bare_installation_config
    installation_config.completion_paths = [INSTALLATION_COMPLETION_PATH]

    installation_model = models.Installation.from_config(
        installation_config,
    )

    assert installation_model.completion_paths == [
        INSTALLATION_COMPLETION_PATH,
    ]


def test_installation_from_config_w_quizzes_path(bare_installation_config):
    installation_config = bare_installation_config
    installation_config.quizzes_paths = [INSTALLATION_QUIZZES_PATH]

    installation_model = models.Installation.from_config(
        installation_config,
    )

    assert installation_model.quizzes_paths == [INSTALLATION_QUIZZES_PATH]


def test_installation_from_config_w_tp_dburi(bare_installation_config):
    installation_config = bare_installation_config
    installation_config._thread_persistence_dburi_sync = (
        INSTALLATION_TP_DBURI_SYNC
    )
    installation_config._thread_persistence_dburi_async = (
        INSTALLATION_TP_DBURI_ASYNC
    )

    installation_model = models.Installation.from_config(
        installation_config,
    )

    assert installation_model.thread_persistence_dburi_sync == (
        INSTALLATION_TP_DBURI_SYNC
    )
    assert installation_model.thread_persistence_dburi_async == (
        INSTALLATION_TP_DBURI_ASYNC
    )


def test_installation_from_config_w_logging_config_file(
    temp_dir,
    bare_installation_config,
):
    logging_config_file = temp_dir / "logging_config.yaml"
    installation_config = bare_installation_config
    installation_config._logging_config_file = logging_config_file

    installation_model = models.Installation.from_config(
        installation_config,
    )

    assert installation_model.logging_config_file == logging_config_file


def test_installation_from_config_w_agui_feature(
    bare_installation_config,
    the_agui_feature,
):
    # Ensure that the registry has only a  single, known feature.
    with mock.patch.dict(
        "soliplex.config.AGUI_FEATURES_BY_NAME",
        clear=True,
        the_agui_feature=the_agui_feature,
    ):
        installation_model = models.Installation.from_config(
            bare_installation_config,
        )

    for m_feature, c_feature in zip(
        installation_model.agui_features,
        [the_agui_feature],
        strict=True,
    ):
        assert m_feature.name == c_feature.name
        assert m_feature.description == c_feature.description
        assert m_feature.source == c_feature.source


@pytest.mark.parametrize(
    "user_claims, exp_profile_kw",
    [
        ({}, UNKNOWN_USER_PROFILE_KW),
        (AUTH_USER_CLAIMS, AUTH_USER_CLAIMS),
    ],
)
def test_userprofile_from_user_claims(user_claims, exp_profile_kw):
    expected = models.UserProfile(**exp_profile_kw)

    found = models.UserProfile.from_user_claims(user_claims)

    assert found == expected


@pytest.mark.parametrize(
    "run_metadata, exp_label",
    [
        (None, None),
        (AGUI_RUN_METADATA, RUN_LABEL),
    ],
)
def test_aguirunmetadata_from_run_metadata(run_metadata, exp_label):
    found = models.AGUI_RunMetadata.from_run_meta(run_metadata)

    if exp_label is None:
        assert found is None
    else:
        assert found.label == exp_label


def test_aguirunusage_from_tuple():
    ru_stats = agui_package.RunUsageStats(
        input_tokens=13,
        output_tokens=17,
        requests=23,
        tool_calls=29,
    )
    ru_model = models.AGUI_RunUsage.from_tuple(ru_stats)

    assert ru_model.input_tokens == 13
    assert ru_model.output_tokens == 17
    assert ru_model.requests == 23
    assert ru_model.tool_calls == 29


@pytest.mark.parametrize(
    "run_metadata, exp_label",
    [
        (None, None),
        (AGUI_RUN_METADATA, RUN_LABEL),
    ],
)
@pytest.mark.parametrize("w_finished", [False, True])
@pytest.mark.parametrize("w_events", [False, True])
@pytest.mark.parametrize("w_parent", [False, True])
def test_aguirun_from_run(
    run_input,
    w_parent,
    w_events,
    w_finished,
    run_metadata,
    exp_label,
):
    a_run = _make_run(
        thread_id=AGUI_THREAD_ID,
        run_id=AGUI_RUN_ID,
        created=NOW,
        finished=NOW if w_finished else None,
        parent_run_id=AGUI_PARENT_RUN_ID if w_parent else None,
        run_input=run_input,
    )

    found = models.AGUI_Run.from_run(
        a_run=a_run,
        a_run_input=run_input,
        a_run_meta=run_metadata,
        a_run_events=AGUI_EVENTS if w_events else [],
    )

    assert found.thread_id == AGUI_THREAD_ID
    assert found.run_id == AGUI_RUN_ID
    assert found.created == NOW
    assert found.parent_run_id == (AGUI_PARENT_RUN_ID if w_parent else None)
    assert found.run_input is run_input

    if w_events:
        assert found.events == AGUI_EVENTS
    else:
        assert found.events == []

    if exp_label is None:
        assert found.metadata is None
    else:
        assert found.metadata.label == exp_label


@pytest.mark.parametrize(
    "thread_metadata, exp_name_desc",
    [
        (None, None),
        (WO_DESC_AGUI_THREAD_METADATA, (THREAD_NAME, None)),
        (FULL_AGUI_THREAD_METADATA, (THREAD_NAME, THREAD_DESC)),
    ],
)
def test_aguithreadmetadata_from_thr_metadata(thread_metadata, exp_name_desc):
    found = models.AGUI_ThreadMetadata.from_thread_meta(thread_metadata)

    if exp_name_desc is None:
        assert found is None
    else:
        exp_name, exp_desc = exp_name_desc
        assert found.name == exp_name
        assert found.description == exp_desc


@pytest.mark.parametrize(
    "thread_metadata, exp_name_desc",
    [
        (None, None),
        (WO_DESC_AGUI_THREAD_METADATA, (THREAD_NAME, None)),
        (FULL_AGUI_THREAD_METADATA, (THREAD_NAME, THREAD_DESC)),
    ],
)
@pytest.mark.parametrize("w_runs", [False, True])
def test_aguithread_from_thread(
    run_input,
    w_runs,
    thread_metadata,
    exp_name_desc,
):
    a_thread = _make_thread(
        room_id=ROOM_ID,
        thread_id=AGUI_THREAD_ID,
        created=NOW,
    )

    a_thread_meta = (
        models.AGUI_ThreadMetadata.from_thread_meta(
            thread_metadata,
        )
        if thread_metadata is not None
        else None
    )

    if w_runs:
        a_thread_runs = {
            agui_run.run_id: models.AGUI_Run.from_run(
                a_run=agui_run,
                a_run_input=agui_run.run_input,
                a_run_meta=agui_run.run_metadata,
                a_run_events=[],
            )
            for agui_run in AGUI_RUNS.values()
        }
    else:
        a_thread_runs = None

    found = models.AGUI_Thread.from_thread(
        a_thread=a_thread,
        a_thread_meta=a_thread_meta,
        a_thread_runs=a_thread_runs,
    )

    assert found.room_id == ROOM_ID
    assert found.thread_id == AGUI_THREAD_ID
    assert found.created == a_thread.created
    assert found.runs == (a_thread_runs if w_runs else None)

    if exp_name_desc is None:
        assert found.metadata is None
    else:
        exp_name, exp_desc = exp_name_desc
        assert found.metadata.name == exp_name
        assert found.metadata.description == exp_desc
