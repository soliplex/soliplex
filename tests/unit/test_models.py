import pathlib
from unittest import mock

import pytest

from soliplex import config
from soliplex import models
from soliplex import tools

QUIZ_ID = "test_quiz"
QUIZ_TITLE = "Test Quiz"
QUIZ_MAX_QUESTIONS = 14
QUIZ_PATH_OVERRIDE = "/dev/null"

SDTC_RAG_LANCE_DB_PATH = "/path/to/db/rag"

ROOM_ID = "test_room"
ROOM_NAME = "Test Room"
ROOM_DESCRIPTION = "This room is made for testing"
ROOM_WELCOME = "Welcome!"
ROOM_SUGGESTION = "Why is the sky blue?"

AGENT_ID = "test_agent"
AGENT_MODEL = "test_model"
AGENT_PROMPT = "You are a test"

INSTALLATION_ID = "test-installation"
INSTALLATION_SECRET = "Seeeeeekrit!"
INSTALLATION_ENVVAR_NAME = "TEST_ENVVAR"
INSTALLATION_ENVVAR_VALUE = "Test Envvar"
INSTALLATION_OIDC_PATH = pathlib.Path("/path/to/oidc")
INSTALLATION_ROOM_PATH = pathlib.Path("/path/to/rooms")
INSTALLATION_COMPLETIONS_PATH = pathlib.Path("/path/to/completions")
INSTALLATION_QUIZZES_PATH = pathlib.Path("/path/to/quizzes")


def _from_param(request, key):
    kw = {}
    if request.param is not None:
        kw[key] = request.param
    return kw


@pytest.fixture(scope="module", params=[None, False, True])
def quiz_randomize(request):
    return _from_param(request, "randomize")


@pytest.fixture(scope="module", params=[None, QUIZ_MAX_QUESTIONS])
def quiz_max_questions(request):
    return _from_param(request, "max_questions")


def test_quiz_from_config(quiz_randomize, quiz_max_questions):
    quiz_config = config.QuizConfig(
        id=QUIZ_ID,
        title=QUIZ_TITLE,
        _question_file_path_override="/dev/null",
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



def test_tool_from_toolconfig():
    def test_tool():
        """This is a test tool"""

    tool_config = config.ToolConfig(
        kind="testing",
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        tool_model = models.Tool.from_config(tool_config)

    assert tool_model.kind == "testing"
    assert tool_model.tool_name == "soliplex.tools.test_tool"
    assert tool_model.tool_description == test_tool.__doc__.strip()
    assert tool_model.tool_requires == config.ToolRequires.BARE
    assert tool_model.allow_mcp is False
    assert tool_model.extra_parameters == {}



def test_tool_from_sdtc():

    tool_config = config.SearchDocumentsToolConfig(
        rag_lancedb_override_path=SDTC_RAG_LANCE_DB_PATH,
        expand_context_radius=3,
        search_documents_limit=7,
        return_citations=True,
        allow_mcp=True,
    )

    tool_model = models.Tool.from_config(tool_config)

    assert tool_model.kind == "search_documents"
    assert tool_model.tool_name == "soliplex.tools.search_documents"
    assert (
        tool_model.tool_description == tools.search_documents.__doc__.strip()
    )
    assert tool_model.tool_requires == config.ToolRequires.TOOL_CONFIG
    assert tool_model.allow_mcp is True
    assert tool_model.extra_parameters == dict(
        rag_lancedb_path=pathlib.Path(SDTC_RAG_LANCE_DB_PATH),
        expand_context_radius=3,
        search_documents_limit=7,
        return_citations=True,
    )

@pytest.fixture(scope="module", params=[None, ROOM_WELCOME])
def room_welcome(request):
    return _from_param(request, "welcome_message")


@pytest.fixture(scope="module", params=[None, [ROOM_SUGGESTION]])
def room_suggestions(request):
    return _from_param(request, "suggestions")


@pytest.fixture(scope="module", params=[False, True])
def room_tools(request):
    kw = {}
    if request.param:
        kw["tool_configs"] = {
            "get_current_datetime":
                config.ToolConfig(
                    kind="testing",
                    tool_name="soliplex.tools.get_current_datetime",
                ),
        }
    return kw


@pytest.fixture(scope="module", params=[False, True])
def room_quizzes(request):
    kw = {}
    if request.param:
        kw["quizzes"] = [
            config.QuizConfig(
                id=QUIZ_ID,
                title=QUIZ_TITLE,
                _question_file_path_override=QUIZ_PATH_OVERRIDE,
            )
        ]
    return kw

@pytest.fixture
def room_agent():
    return config.AgentConfig(
        id=AGENT_ID,
        model_name=AGENT_MODEL,
        system_prompt=AGENT_PROMPT,
    )

def test_room_from_config(
    room_agent, room_welcome, room_suggestions, room_tools, room_quizzes,
):
    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=room_agent,
        **room_welcome,
        **room_suggestions,
        **room_tools,
        **room_quizzes,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.id == ROOM_ID
    assert room_model.name == ROOM_NAME
    assert room_model.description == ROOM_DESCRIPTION

    if room_welcome:
        assert room_model.welcome_message == room_welcome["welcome_message"]
    else:
        assert room_model.welcome_message == ROOM_DESCRIPTION

    if room_suggestions:
        assert room_model.suggestions == room_suggestions["suggestions"]
    else:
        assert room_model.suggestions == []

    if room_quizzes:
        assert room_model.quizzes == {
            quiz.id: models.Quiz.from_config(quiz)
            for quiz in room_quizzes["quizzes"]
        }
    else:
        assert room_model.quizzes == {}


@pytest.fixture(scope="module", params=[None, [INSTALLATION_SECRET]])
def installation_secrets(request):
    return _from_param(request, "secrets")


@pytest.fixture(
    scope="module",
    params=[
        None,
        {INSTALLATION_ENVVAR_NAME: INSTALLATION_ENVVAR_VALUE},
    ],
)
def installation_environment(request):
    return _from_param(request, "environment")


@pytest.fixture(scope="module", params=[None, [INSTALLATION_OIDC_PATH]])
def installation_oidc_paths(request):
    return _from_param(request, "oidc_paths")


@pytest.fixture(scope="module", params=[None, [INSTALLATION_ROOM_PATH]])
def installation_room_paths(request):
    return _from_param(request, "room_paths")


@pytest.fixture(scope="module", params=[None, [INSTALLATION_COMPLETIONS_PATH]])
def installation_completions_paths(request):
    return _from_param(request, "completions_paths")


@pytest.fixture(scope="module", params=[None, [INSTALLATION_QUIZZES_PATH]])
def installation_quizzes_paths(request):
    return _from_param(request, "quizzes_paths")


def test_installation_from_config(
    installation_secrets,
    installation_environment,
    installation_oidc_paths,
    installation_room_paths,
    installation_completions_paths,
    installation_quizzes_paths,
):
    installation_config = config.InstallationConfig(
        id=INSTALLATION_ID,
        **installation_secrets,
        **installation_environment,
        **installation_oidc_paths,
        **installation_room_paths,
        **installation_completions_paths,
        **installation_quizzes_paths,
    )

    installation_model = models.Installation.from_config(installation_config)

    assert installation_model.id == INSTALLATION_ID

    if installation_secrets:
        assert installation_model.secrets == installation_secrets["secrets"]
    else:
        assert installation_model.secrets == []

    if installation_environment:
        assert (
            installation_model.environment ==
            installation_environment["environment"]
        )
    else:
        assert installation_model.environment == {}

    if installation_oidc_paths:
        assert (
            installation_model.oidc_paths ==
            installation_oidc_paths["oidc_paths"]
        )
    else:
        assert installation_model.oidc_paths == [pathlib.Path("oidc")]

    if installation_room_paths:
        assert (
            installation_model.room_paths ==
            installation_room_paths["room_paths"]
        )
    else:
        assert installation_model.room_paths == [pathlib.Path("rooms")]

    if installation_completions_paths:
        assert (
            installation_model.completions_paths ==
            installation_completions_paths["completions_paths"]
        )
    else:
        assert (
            installation_model.completions_paths ==
            [pathlib.Path("completions")]
        )

    if installation_quizzes_paths:
        assert (
            installation_model.quizzes_paths ==
            installation_quizzes_paths["quizzes_paths"]
        )
    else:
        assert installation_model.quizzes_paths == [pathlib.Path("quizzes")]
