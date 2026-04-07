import contextlib
import copy
import dataclasses
import pathlib
from unittest import mock

import pytest
import yaml
from haiku.rag import config as hr_config_module
from haiku.skills import models as hs_models

from soliplex import secrets
from soliplex.agui import features as agui_features
from soliplex.config import agents as config_agents
from soliplex.config import authsystem as config_authsystem
from soliplex.config import exceptions as config_exc
from soliplex.config import installation as config_installation
from soliplex.config import logfire as config_logfire
from soliplex.config import meta as config_meta
from soliplex.config import routing as config_routing
from soliplex.config import secrets as config_secrets
from soliplex.config import skills as config_skills
from soliplex.config import tools as config_tools
from tests.unit.config import test_config_agents as test_agents
from tests.unit.config import test_config_authsystem as test_authsystem
from tests.unit.config import test_config_completions as test_completions
from tests.unit.config import test_config_logfire as test_logfire
from tests.unit.config import test_config_meta as test_meta
from tests.unit.config import test_config_rooms as test_rooms
from tests.unit.config import test_config_skills as test_skills

NoRaise = contextlib.nullcontext()


class FauxToolConfig:
    tool_name = "faux"


BARE_INSTALLATION_CONFIG_ENVIRONMENT = {
    "OLLAMA_BASE_URL": test_agents.PROVIDER_BASE_URL,
}
OLLAMA_BASE_URL = "https://example.com:12345"


INSTALLATION_ID = "test-installation"

BOGUS_INSTALLATION_CONFIG_YAML = ""

BARE_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
}
BARE_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
"""

W_BARE_META_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "meta": copy.deepcopy(test_meta.BARE_ICMETA_KW),
}
W_BARE_META_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
meta:
"""

W_FULL_META_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "meta": {
        "agui_features": [
            config_meta.AGUI_FeatureConfigMeta(
                name=test_meta.AGUI_FEATURE_NAME_FOR_META,
                model_klass=agui_features.EmptyFeatureModel,
                source="server",
            ),
        ],
        "tool_configs": [
            config_meta.ConfigMeta(config_klass=FauxToolConfig),
        ],
        "mcp_toolset_configs": [
            config_meta.ConfigMeta(
                config_klass=config_tools.Stdio_MCP_ClientToolsetConfig
            ),
            config_meta.ConfigMeta(
                config_klass=config_tools.HTTP_MCP_ClientToolsetConfig
            ),
        ],
        "mcp_server_tool_wrappers": [
            config_meta.ConfigMeta(
                config_klass=FauxToolConfig,
                wrapper_klass=config_tools.NoArgsMCPWrapper,
            ),
        ],
        "skill_configs": [
            config_meta.ConfigMeta(
                config_klass=config_skills.HR_RAG_SkillConfig
            ),
            config_meta.ConfigMeta(
                config_klass=config_skills.HR_RLM_SkillConfig
            ),
        ],
        "agent_configs": [
            config_meta.ConfigMeta(config_klass=config_agents.AgentConfig),
            config_meta.ConfigMeta(
                config_klass=config_agents.FactoryAgentConfig
            ),
        ],
        "secret_sources": [
            config_meta.ConfigMeta(
                config_klass=config_secrets.EnvVarSecretSource,
                registered_func=test_meta.SECRET_SOURCE_FUNC,
            ),
        ],
    },
}
W_FULL_META_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
meta:
  agui_features:
      - name: "{test_meta.AGUI_FEATURE_NAME_FOR_META}"
        model_klass: "soliplex.agui.features.EmptyFeatureModel"
        source: "server"
  tool_configs:
    - "test_config_installation.FauxToolConfig"
  mcp_toolset_configs:
      - "soliplex.config.tools.Stdio_MCP_ClientToolsetConfig"
      - "soliplex.config.tools.HTTP_MCP_ClientToolsetConfig"
  mcp_server_tool_wrappers:
    - config_klass: "test_config_installation.FauxToolConfig"
      wrapper_klass: "soliplex.config.tools.NoArgsMCPWrapper"
  skill_configs:
      - "soliplex.config.skills.HR_RAG_SkillConfig"
      - "soliplex.config.skills.HR_RLM_SkillConfig"
  agent_configs:
      - "soliplex.config.agents.AgentConfig"
      - "soliplex.config.agents.FactoryAgentConfig"
  secret_sources:
    - "config_klass": "soliplex.config.secrets.EnvVarSecretSource"
      "registered_func": "soliplex.config.test_secret_func"
"""

W_APP_ROUTER_OPERATIONS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "app_router_operations": [
        config_routing.ClearAppRouters(),
        config_routing.AddAppRouter(
            group_name="streaming",
            router_name="soliplex.views.streaming.router",
            prefix="/api",
        ),
    ],
}
W_APP_ROUTER_OPERATIONS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
app_router_operations:
    - kind: "clear"
    - kind: "add"
      group_name: "streaming"
      router_name: "soliplex.views.streaming.router"
      prefix: "/api"
"""

SECRET_NAME_1 = "TEST_SECRET_ONE"
SECRET_NAME_2 = "TEST_SECRET_TWO"
DB_SECRET_NAME = "DBSECRET"
DB_SECRET_VALUE = "R34ll7#S33KR1T"

SECRET_CONFIG_1 = config_secrets.SecretConfig(secret_name=SECRET_NAME_1)
SECRET_CONFIG_2 = config_secrets.SecretConfig(secret_name=SECRET_NAME_2)
DB_SECRET_CONFIG = config_secrets.SecretConfig(
    secret_name=DB_SECRET_NAME,
    _resolved=DB_SECRET_VALUE,
)

SECRET_ENV_VAR = "OTHER_ENV_VAR"
SECRET_FILE_PATH = "./very_seekrit"
SECRET_COMAND = "cat"
SECRET_ARGS = ["-"]
SECRET_NCHARS = 37

W_SECRETS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "secrets": [
        config_secrets.SecretConfig(secret_name=SECRET_NAME_1),
        config_secrets.SecretConfig(
            secret_name=SECRET_NAME_2,
            sources=[
                config_secrets.EnvVarSecretSource(
                    secret_name=SECRET_NAME_2,
                    env_var_name=SECRET_ENV_VAR,
                ),
                config_secrets.FilePathSecretSource(
                    secret_name=SECRET_NAME_2,
                    file_path=SECRET_FILE_PATH,
                ),
                config_secrets.SubprocessSecretSource(
                    secret_name=SECRET_NAME_2,
                    command=SECRET_COMAND,
                    args=SECRET_ARGS,
                ),
                config_secrets.RandomCharsSecretSource(
                    secret_name=SECRET_NAME_2,
                    n_chars=SECRET_NCHARS,
                ),
            ],
        ),
    ],
}
W_SECRETS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
secrets:
    - "{SECRET_NAME_1}"
    - secret_name: "{SECRET_NAME_2}"
      sources:
          - kind: "env_var"
            env_var_name: "{SECRET_ENV_VAR}"
          - kind: "file_path"
            file_path: "{SECRET_FILE_PATH}"
          - kind: "subprocess"
            command: "{SECRET_COMAND}"
            args:
            - "-"
          - kind: "random_chars"
            n_chars: {SECRET_NCHARS}
"""

CONFIG_KEY_0 = "INSTALLATION_PATH"
CONFIG_VAL_0 = "file:."
CONFIG_KEY_1 = "key_1"
CONFIG_VAL_1 = "val_1"
CONFIG_KEY_2 = "key_2"
CONFIG_VAL_2 = "val_2"
W_ENVIRONMENT_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "environment": {
        CONFIG_KEY_0: CONFIG_VAL_0,
        CONFIG_KEY_1: CONFIG_VAL_1,
        CONFIG_KEY_2: CONFIG_VAL_2,
    },
}
W_ENVIRONMENT_LIST_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
environment:
    - name: "{CONFIG_KEY_0}"
      value: "{CONFIG_VAL_0}"
    - name: "{CONFIG_KEY_1}"
      value: "{CONFIG_VAL_1}"
    - name: "{CONFIG_KEY_2}"
      value: "{CONFIG_VAL_2}"
"""
W_ENVIRONMENT_MAPPING_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
environment:
    {CONFIG_KEY_0}: "{CONFIG_VAL_0}"
    {CONFIG_KEY_1}: "{CONFIG_VAL_1}"
    {CONFIG_KEY_2}: "{CONFIG_VAL_2}"
"""

HAIKU_RAG_CONFIG_FILE = "/path/to/haiku.rag.yaml"
W_HR_CONFIG_FILE_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "_haiku_rag_config_file": pathlib.Path(HAIKU_RAG_CONFIG_FILE),
}
W_HR_CONFIG_FILE_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
haiku_rag_config_file: "{HAIKU_RAG_CONFIG_FILE}"
"""

AGENT_CONFIG_ID = "agent-config-1"

W_AGENT_CONFIG_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "agent_configs": [
        config_agents.AgentConfig(
            id=AGENT_CONFIG_ID,
            model_name=test_agents.MODEL_NAME,
            system_prompt=test_agents.SYSTEM_PROMPT,
        ),
    ],
}
W_AGENT_CONFIG_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
agent_configs:
    - id: "{AGENT_CONFIG_ID}"
      model_name: "{test_agents.MODEL_NAME}"
      system_prompt: "{test_agents.SYSTEM_PROMPT}"
"""

W_FACTORY_AGENT_CONFIG_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "meta": {
        "agent_configs": [
            config_meta.ConfigMeta(
                config_klass=config_agents.FactoryAgentConfig,
            ),
        ],
    },
    "agent_configs": [
        config_agents.FactoryAgentConfig(
            id=AGENT_CONFIG_ID,
            factory_name="soliplex.haiku_chat.chat_agent_factory",
        ),
    ],
}
W_FACTORY_AGENT_CONFIG_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
meta:
    agent_configs:
        - "soliplex.config.agents.FactoryAgentConfig"
agent_configs:
    - id: "{AGENT_CONFIG_ID}"
      kind: "factory"
      factory_name: "soliplex.haiku_chat.chat_agent_factory"
"""

UPLOAD_PATH = "uploads"

W_UPLOAD_PATH_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "upload_path": UPLOAD_PATH,
}
W_UPLOAD_PATH_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
upload_path: "{UPLOAD_PATH}"
"""

OIDC_PATH_1 = "./oidc"
OIDC_PATH_2 = "/path/to/other/oidc"

W_OIDC_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "oidc_paths": [
        OIDC_PATH_1,
        OIDC_PATH_2,
    ],
}
W_OIDC_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
oidc_paths:
    - "{OIDC_PATH_1}"
    - "{OIDC_PATH_2}"
"""

W_OIDC_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "oidc_paths": [],
}
W_OIDC_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
oidc_paths:
    -
"""

ROOM_PATH_1 = "./rooms"
ROOM_PATH_2 = "/path/to/other/rooms"

W_ROOM_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "room_paths": [
        ROOM_PATH_1,
        ROOM_PATH_2,
    ],
}
W_ROOM_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
room_paths:
    - "{ROOM_PATH_1}"
    - "{ROOM_PATH_2}"
"""

W_ROOM_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "room_paths": [],
}
W_ROOM_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
room_paths:
    -
"""

COMPLETION_PATH_1 = "./completions"
COMPLETION_PATH_2 = "/path/to/other/completions"

W_COMPLETION_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "completion_paths": [
        COMPLETION_PATH_1,
        COMPLETION_PATH_2,
    ],
}
W_COMPLETION_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
completion_paths:
    - "{COMPLETION_PATH_1}"
    - "{COMPLETION_PATH_2}"
"""

W_COMPLETION_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "completion_paths": [],
}
W_COMPLETION_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
completion_paths:
    -
"""

QUIZZES_PATH_1 = "./quizzes"
QUIZZES_PATH_2 = "/path/to/other/quizzes"

W_QUIZZES_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "quizzes_paths": [
        QUIZZES_PATH_1,
        QUIZZES_PATH_2,
    ],
}
W_QUIZZES_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
quizzes_paths:
    - "{QUIZZES_PATH_1}"
    - "{QUIZZES_PATH_2}"
"""

W_QUIZZES_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "quizzes_paths": [],
}
W_QUIZZES_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
quizzes_paths:
    -
"""

LOGGING_CONFIG_FILE = "/path/to/logging.yaml"
LOGGING_HEADER_ID_KEY = "test-header"
LOGGING_USER_ID_KEY = "test-claim-key"
W_LOGGING_CONFIG_FILE_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "_logging_config_file": pathlib.Path(LOGGING_CONFIG_FILE),
    "_logging_headers_map": {
        "request_id": LOGGING_HEADER_ID_KEY,
    },
    "_logging_claims_map": {
        "user_id": LOGGING_USER_ID_KEY,
    },
}
W_LOGGING_CONFIG_FILE_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
logging_config_file: "{LOGGING_CONFIG_FILE}"
logging_headers_map:
    request_id: "{LOGGING_HEADER_ID_KEY}"
logging_claims_map:
    user_id: "{LOGGING_USER_ID_KEY}"
"""

SKILLS_PATH_1 = "./skills"
SKILLS_PATH_2 = "/path/to/other/skills"

W_SKILLS_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "filesystem_skills_paths": [
        SKILLS_PATH_1,
        SKILLS_PATH_2,
    ],
    "_skill_configs": [
        {
            "kind": "filesystem",
            "skill_name": test_skills.FILESYSTEM_SKILL_NAME,
        },
        {
            "kind": "entrypoint",
            "skill_name": test_skills.ENTRYPOINT_SKILL_NAME,
        },
    ],
}
W_SKILLS_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
filesystem_skills_paths:
    - "{SKILLS_PATH_1}"
    - "{SKILLS_PATH_2}"
skill_configs:
    - kind: "filesystem"
      skill_name: "{test_skills.FILESYSTEM_SKILL_NAME}"
    - kind: "entrypoint"
      skill_name: "{test_skills.ENTRYPOINT_SKILL_NAME}"
"""

W_SKILLS_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "filesystem_skills_paths": [],
}
W_SKILLS_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
filesystem_skills_paths:
    -
"""

W_LOGFIRE_CONFIG_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "logfire_config": config_logfire.LogfireConfig(
        token=test_logfire.TEST_LOGFIRE_TOKEN
    ),
}
W_LOGFIRE_CONFIG_INSTALLATION_CONFIG_YAML = f"""
id: "{INSTALLATION_ID}"
logfire_config:
    token: "{test_logfire.TEST_LOGFIRE_TOKEN}"
"""

DB_USER_NAME = "db_user"

ENVVAR_NAME_1 = "TEST_SECRET_ONE"
ENVVAR_NAME_2 = "TEST_SECRET_TWO"
ENVVAR_VALUE_1 = "<envvar1>"
ENVVAR_VALUE_2 = "<envvar2>"

TP_DBURI_SYNC = "sqlite+pysqlite:////tmp/tp_testing.sqlite"
TP_DBURI_SYNC_W_SECRET_AND_ENV = (
    f"sqlite+pysqlcipher://env:DB_USER_NAME@"
    f"secret:{DB_SECRET_NAME}//tmp/tp_testing.sqlite"
)
TP_DBURI_SYNC_W_SECRET_AND_ENV_RESOLVED = (
    f"sqlite+pysqlcipher://{DB_USER_NAME}@"
    f"{DB_SECRET_VALUE}//tmp/tp_testing.sqlite"
)
TP_DBURI_ASYNC = "sqlite+aiosqlite:////tmp/tp_testing.sqlite"

W_TP_DBURI_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "_thread_persistence_dburi_sync": TP_DBURI_SYNC,
    "_thread_persistence_dburi_async": TP_DBURI_ASYNC,
}
W_TP_DBURI_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
thread_persistence_dburi:
    sync: {TP_DBURI_SYNC}
    async: {TP_DBURI_ASYNC}
"""

W_TP_DBURI_W_SECRET_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "_thread_persistence_dburi_sync": TP_DBURI_SYNC_W_SECRET_AND_ENV,
    # aiosqlite doesn't support secrets
    "_thread_persistence_dburi_async": TP_DBURI_ASYNC,
}
W_TP_DBURI_W_SECRET_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
thread_persistence_dburi:
    sync: {TP_DBURI_SYNC_W_SECRET_AND_ENV}
    async: {TP_DBURI_ASYNC}
"""

RA_DB_USER_NAME = "ra_db_user"
RA_DBURI_SYNC = "sqlite+pysqlite:////tmp/ra_testing.sqlite"
RA_DBURI_SYNC_W_SECRET_AND_ENV = (
    f"sqlite+pysqlcipher://env:DB_USER_NAME@"
    f"secret:{DB_SECRET_NAME}//tmp/ra_testing.sqlite"
)
RA_DBURI_SYNC_W_SECRET_AND_ENV_RESOLVED = (
    f"sqlite+pysqlcipher://{DB_USER_NAME}@"
    f"{DB_SECRET_VALUE}//tmp/ra_testing.sqlite"
)
RA_DBURI_ASYNC = "sqlite+aiosqlite:////tmp/ra_testing.sqlite"

W_RA_DBURI_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "_authorization_dburi_sync": RA_DBURI_SYNC,
    "_authorization_dburi_async": RA_DBURI_ASYNC,
}
W_RA_DBURI_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
authorization_dburi:
    sync: {RA_DBURI_SYNC}
    async: {RA_DBURI_ASYNC}
"""

W_RA_DBURI_W_SECRET_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "_authorization_dburi_sync": RA_DBURI_SYNC_W_SECRET_AND_ENV,
    # aiosqlite doesn't support secrets
    "_authorization_dburi_async": RA_DBURI_ASYNC,
}
W_RA_DBURI_W_SECRET_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
authorization_dburi:
    sync: {RA_DBURI_SYNC_W_SECRET_AND_ENV}
    async: {RA_DBURI_ASYNC}
"""


@pytest.mark.parametrize("w_disable_dotenv", [False, True])
def test_installationconfig_from_dotenv_already(w_disable_dotenv):
    already = {"KEY": "value"}

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        disable_dotenv=w_disable_dotenv,
        _from_dotenv=already,
    )

    found = i_config.from_dotenv

    if w_disable_dotenv:
        assert found == {}

    else:
        assert found == already


@pytest.mark.parametrize("w_cwd_dotenv", [None, "KEY=from_cwd_dotenv"])
@pytest.mark.parametrize("w_inst_dotenv", [None, "KEY=from_inst_dotenv"])
@pytest.mark.parametrize("w_disable_dotenv", [False, True])
@mock.patch("pathlib.Path")
def test_installationconfig_from_dotenv(
    p_path,
    temp_dir,
    w_disable_dotenv,
    w_inst_dotenv,
    w_cwd_dotenv,
):
    inst_dir = temp_dir / "installation"
    inst_dir.mkdir()
    inst_config_file = inst_dir / "test.yaml"
    inst_dot_env = inst_dir / ".env"
    expected = {}

    if w_inst_dotenv is not None:
        inst_dot_env.write_text(w_inst_dotenv)
        expected["KEY"] = "from_inst_dotenv"

    cwd = temp_dir / "cwd"
    cwd.mkdir()
    p_path.cwd.return_value = cwd
    cwd_dot_env = cwd / ".env"

    if w_cwd_dotenv is not None:
        cwd_dot_env.write_text(w_cwd_dotenv)
        if "KEY" not in expected:  # inst dir wins over cwd
            expected["KEY"] = "from_cwd_dotenv"

    if w_disable_dotenv:
        expected = {}

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        disable_dotenv=w_disable_dotenv,
        _config_path=inst_config_file,
    )

    found = i_config.from_dotenv

    assert found == expected


def test_installationconfig_secrets_map_wo_existing():
    secrets = [
        config_secrets.SecretConfig(secret_name=f"secret-{i_secret}")
        for i_secret in range(5)
    ]

    i_config = config_installation.InstallationConfig(
        id="test-ic", secrets=secrets
    )

    found = i_config.secrets_map

    for (_f_key, f_val), secret in zip(
        sorted(found.items()),
        secrets,
        strict=True,
    ):
        assert f_val.secret_name == secret.secret_name
        assert f_val._installation_config is i_config


def test_installationconfig_secrets_map_w_existing():
    already = object()
    i_config = config_installation.InstallationConfig(
        id="test-ic", _secrets_map=already
    )

    found = i_config.secrets_map

    assert found is already


RaiseUnknownSecret = pytest.raises(secrets.UnknownSecret)


@pytest.mark.parametrize(
    "secret_map, expectation",
    [
        ({}, RaiseUnknownSecret),
        ({SECRET_NAME_1: SECRET_CONFIG_1}, NoRaise),
    ],
)
@mock.patch("soliplex.secrets.get_secret")
def test_installationconfig_get_secret(gs, secret_map, expectation):
    i_config = config_installation.InstallationConfig(
        id="test-ic",
        _secrets_map=secret_map,
    )

    with expectation as expected:
        found = i_config.get_secret(f"secret:{SECRET_NAME_1}")

    if expected is None:
        assert found is gs.return_value
        gs.assert_called_once_with(SECRET_CONFIG_1)
    else:
        gs.assert_not_called()


@pytest.mark.parametrize(
    "value, secret_map, expectation, exp_value, exp_gs_configs",
    [
        ("No secret here", {}, NoRaise, "No secret here", ()),
        (f"Foo secret:{SECRET_NAME_1}", {}, RaiseUnknownSecret, None, ()),
        (
            f"Foo secret:{SECRET_NAME_1}",
            {SECRET_NAME_1: SECRET_CONFIG_1},
            NoRaise,
            "Foo <secret1>",
            [SECRET_CONFIG_1],
        ),
        (
            f"PRE|secret:{SECRET_NAME_1}|INTER|secret:{SECRET_NAME_2}|POST",
            {
                SECRET_NAME_1: SECRET_CONFIG_1,
                SECRET_NAME_2: SECRET_CONFIG_2,
            },
            NoRaise,
            "PRE|<secret1>|INTER|<secret2>|POST",
            [SECRET_CONFIG_1, SECRET_CONFIG_2],
        ),
    ],
)
@mock.patch("soliplex.secrets.get_secret")
def test_installationconfig_interpolate_secret(
    gs,
    value,
    secret_map,
    expectation,
    exp_value,
    exp_gs_configs,
):
    gs.side_effect = ["<secret1>", "<secret2>"]

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        _secrets_map=secret_map,
    )

    with expectation:
        found = i_config.interpolate_secrets(value)

    if exp_value is not None:
        assert found == exp_value
        if exp_value == value:
            gs.assert_not_called()
        else:
            for f_call, gs_config in zip(
                gs.call_args_list,
                exp_gs_configs,
                strict=True,
            ):
                assert f_call == mock.call(gs_config)
    else:
        gs.assert_not_called()


EST = config_installation.EnvironmentSourceType


@pytest.mark.parametrize(
    "w_yaml, w_dotenv, w_osenv, exp_first",
    [
        (None, None, None, None),
        ("YAML", None, None, EST.CONFIG_YAML),
        ("YAML", "DOTENV", None, EST.CONFIG_YAML),
        ("YAML", None, "OSENV", EST.CONFIG_YAML),
        (None, "DOTENV", None, EST.DOT_ENV),
        (None, "DOTENV", "OSENV", EST.DOT_ENV),
        (None, None, "OSENV", EST.OS_ENV),
    ],
)
@mock.patch("os.getenv")
def test_installationconfig_get_environment_sources(
    os_getenv,
    w_yaml,
    w_dotenv,
    w_osenv,
    exp_first,
):
    KEY = "TEST_KEY"
    kwargs = {"id": "test-ic"}
    candidates = []

    if w_yaml is not None:
        kwargs["_environment_from_config"] = {KEY: w_yaml}
        candidates.append(EST.CONFIG_YAML)
    else:
        kwargs["_environment_from_config"] = {}

    if w_dotenv is not None:
        kwargs["_from_dotenv"] = {KEY: w_dotenv}
        candidates.append(EST.DOT_ENV)

    if w_osenv is not None:
        os_getenv.return_value = "OSENV"
        candidates.append(EST.OS_ENV)
    else:
        os_getenv.return_value = None

    i_config = config_installation.InstallationConfig(**kwargs)

    found = i_config.get_environment_sources(KEY)

    for f_item, candidate in zip(found, candidates, strict=True):
        assert f_item.source_type == candidate


@pytest.mark.parametrize("w_default", [False, True])
@pytest.mark.parametrize("w_hit", [False, True])
def test_installationconfig_get_environment(w_hit, w_default):
    KEY = "test-key"
    VALUE = "test-value"
    DEFAULT = "test-default"

    kwargs = {}

    if w_default:
        kwargs["default"] = DEFAULT

    i_config = config_installation.InstallationConfig(id="test-ic")

    if w_hit:
        i_config.environment[KEY] = VALUE

    found = i_config.get_environment(KEY, **kwargs)

    if w_hit:
        assert found == VALUE
    elif w_default:
        assert found == DEFAULT
    else:
        assert found is None


UNRESOLVED = {"name": "UNRESOLVED"}
UNRESOLVED_MOAR = {"name": "UNRESOLVED_MOAR"}
RESOLVED = {"name": "RESOLVED", "value": "resolved"}


@pytest.mark.parametrize(
    "env_entries, dotenv_opt, expectation, exp_missing, exp_env",
    [
        (
            [],
            (None, False),
            contextlib.nullcontext(None),
            None,
            {},
        ),
        (
            [RESOLVED],
            (None, False),
            contextlib.nullcontext(None),
            None,
            {"RESOLVED": "resolved"},
        ),
        (
            [UNRESOLVED],
            (None, False),
            pytest.raises(config_installation.MissingEnvVars),
            "UNRESOLVED",
            None,
        ),
        (
            [UNRESOLVED, UNRESOLVED_MOAR],
            (None, False),
            pytest.raises(config_installation.MissingEnvVars),
            "UNRESOLVED,UNRESOLVED_MOAR",
            None,
        ),
        (
            [UNRESOLVED, UNRESOLVED_MOAR],
            ({"UNRESOLVED": "via_dotenv"}, False),
            pytest.raises(config_installation.MissingEnvVars),
            "UNRESOLVED_MOAR",
            None,
        ),
        (
            [UNRESOLVED],
            ({"UNRESOLVED": "via_dotenv"}, False),
            contextlib.nullcontext(None),
            None,
            {"UNRESOLVED": "via_dotenv"},
        ),
        (
            [UNRESOLVED],
            ({"UNRESOLVED": "via_dotenv"}, True),
            pytest.raises(config_installation.MissingEnvVars),
            "UNRESOLVED",
            None,
        ),
        (
            [RESOLVED],
            ({"RESOLVED": "via_dotenv"}, False),
            contextlib.nullcontext(None),
            None,
            {"RESOLVED": "resolved"},
        ),
        (
            [RESOLVED],
            ({"RESOLVED": "via_dotenv"}, True),
            contextlib.nullcontext(None),
            None,
            {"RESOLVED": "resolved"},
        ),
    ],
)
def test_installationconfig_resolve_environment(
    temp_dir,
    env_entries,
    dotenv_opt,
    expectation,
    exp_missing,
    exp_env,
):
    environment = {entry["name"]: entry.get("value") for entry in env_entries}

    from_dotenv, disable_dotenv = dotenv_opt

    dotenv_kwargs = {"disable_dotenv": disable_dotenv}

    if from_dotenv is not None:
        dotenv_kwargs["_from_dotenv"] = from_dotenv

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        _config_path=temp_dir / "installation.yaml",
        environment=environment,
        **dotenv_kwargs,
    )

    with expectation as expected:
        i_config.resolve_environment()

    if expected is not None:
        assert expected.value.env_vars == exp_missing
    else:
        assert i_config.environment == exp_env


RaiseUnknownEnvVar = pytest.raises(
    config_installation.UnknownEnvironmentVariable,
)


@pytest.mark.parametrize(
    "value, environment, expectation, exp_value",
    [
        ("No env var here", {}, NoRaise, "No env var here"),
        ("Foo env:UNKNOWN", {}, RaiseUnknownEnvVar, None),
        (
            f"Foo env:{ENVVAR_NAME_1}",
            {ENVVAR_NAME_1: ENVVAR_VALUE_1},
            NoRaise,
            "Foo <envvar1>",
        ),
        (
            f"PRE|env:{ENVVAR_NAME_1}|INTER|env:{ENVVAR_NAME_2}|POST",
            {
                ENVVAR_NAME_1: ENVVAR_VALUE_1,
                ENVVAR_NAME_2: ENVVAR_VALUE_2,
            },
            NoRaise,
            "PRE|<envvar1>|INTER|<envvar2>|POST",
        ),
    ],
)
def test_installationconfig_interpolate_environment(
    value,
    environment,
    expectation,
    exp_value,
):
    i_config = config_installation.InstallationConfig(
        id="test-ic",
        environment=environment,
    )

    with expectation:
        found = i_config.interpolate_environment(value)

    if exp_value is not None:
        assert found == exp_value


@pytest.mark.parametrize("w_obu", [False, True])
def test_installationconfig_haiku_rag_config(temp_dir, w_obu):
    hr_config_file = temp_dir / "haiku.rag.yaml"
    hr_config_file.write_text("""\
environment: production
""")

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        _config_path=temp_dir / "installation.yaml",
        _haiku_rag_config_file=hr_config_file,
    )

    if w_obu:
        exp_obu = i_config.environment["OLLAMA_BASE_URL"] = OLLAMA_BASE_URL
    else:
        exp_obu = "http://localhost:11434"

    import os

    home_vars = {
        k: v
        for k, v in os.environ.items()
        if k in ("HOME", "HOMEDRIVE", "HOMEPATH", "USERPROFILE")
    }
    with mock.patch.dict("os.environ", home_vars, clear=True):
        hr_config = i_config.haiku_rag_config

    assert isinstance(hr_config, hr_config_module.AppConfig)
    assert hr_config.providers.ollama.base_url == exp_obu


def test_installationconfig_agent_configs_map_wo_existing():
    agent_configs = [
        config_agents.AgentConfig(
            id=f"agent-config-{i_agent_config}",
        )
        for i_agent_config in range(5)
    ]

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        agent_configs=agent_configs,
    )

    found = i_config.agent_configs_map

    for (_f_key, f_val), agent_config in zip(
        sorted(found.items()),
        agent_configs,
        strict=True,
    ):
        exp_agent_config = dataclasses.replace(
            agent_config,
            _installation_config=i_config,
        )
        assert f_val == exp_agent_config


def test_installationconfig_agent_configs_map_w_existing():
    already = object()
    i_config = config_installation.InstallationConfig(
        id="test-ic",
        _agent_configs_map=already,
    )

    found = i_config.agent_configs_map

    assert found is already


@pytest.mark.parametrize("w_filename", [False, True])
def test_installationconfig_logging_config_file(temp_dir, w_filename):
    logging_config_file = temp_dir / "logging.yaml"
    logging_config_file.write_text("""\
version: 1
""")
    kw = {}

    if w_filename:
        kw["_logging_config_file"] = logging_config_file

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        _config_path=temp_dir / "installation.yaml",
        **kw,
    )

    found = i_config.logging_config_file

    if w_filename:
        assert found == logging_config_file
    else:
        assert found is None


@pytest.mark.parametrize("w_filename", [False, True])
def test_installationconfig_logging_config(temp_dir, w_filename):
    logging_config_file = temp_dir / "logging.yaml"
    logging_config_file.write_text("""\
version: 1
""")
    kw = {}

    if w_filename:
        kw["_logging_config_file"] = logging_config_file

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        _config_path=temp_dir / "installation.yaml",
        **kw,
    )

    with mock.patch.dict("os.environ", clear=True):
        logging_config = i_config.logging_config

    if w_filename:
        assert isinstance(logging_config, dict)
        assert logging_config["version"] == 1
    else:
        assert logging_config is None


@pytest.mark.parametrize("w_map", [False, True])
def test_installationconfig_logging_headers_map(temp_dir, w_map):
    kw = {}

    if w_map:
        kw["_logging_headers_map"] = {"foo": "bar"}

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        _config_path=temp_dir / "installation.yaml",
        **kw,
    )

    logging_headers_map = i_config.logging_headers_map

    if w_map:
        assert logging_headers_map == {"foo": "bar"}
    else:
        assert logging_headers_map == {}


@pytest.mark.parametrize("w_map", [False, True])
def test_installationconfig_logging_claims_map(temp_dir, w_map):
    kw = {}

    if w_map:
        kw["_logging_claims_map"] = {"foo": "bar"}

    i_config = config_installation.InstallationConfig(
        id="test-ic",
        _config_path=temp_dir / "installation.yaml",
        **kw,
    )

    logging_claims_map = i_config.logging_claims_map

    if w_map:
        assert logging_claims_map == {"foo": "bar"}
    else:
        assert logging_claims_map == {}


@pytest.mark.parametrize("w_aro", [False, True])
@mock.patch("soliplex.config.routing.register_default_routers")
def test_installationconfig_resolve_app_routers(rdr, w_aro):
    i_config = config_installation.InstallationConfig(id="test-ic")
    add_op = mock.create_autospec(config_routing.AddAppRouter)

    if w_aro:
        i_config.app_router_operations.append(add_op)

    i_config.resolve_app_routers()

    rdr.assert_called_once_with()

    if w_aro:
        add_op.apply.assert_called_once_with()
    else:
        add_op.apply.assert_not_called()


def test_installationconfig_agui_features(
    patched_agui_features,
    the_agui_feature,
):
    patched_agui_features[the_agui_feature.name] = the_agui_feature

    i_config = config_installation.InstallationConfig(id="test-ic")

    found = i_config.agui_features

    assert found == [the_agui_feature]


@pytest.mark.parametrize(
    "w_kw, expected",
    [
        (
            BARE_INSTALLATION_CONFIG_KW.copy(),
            config_installation.SYNC_MEMORY_ENGINE_URL,
        ),
        (W_TP_DBURI_INSTALLATION_CONFIG_KW.copy(), TP_DBURI_SYNC),
        (
            (
                W_TP_DBURI_W_SECRET_INSTALLATION_CONFIG_KW
                | {"secrets": [DB_SECRET_CONFIG]}
                | {"environment": {"DB_USER_NAME": DB_USER_NAME}}
            ),
            TP_DBURI_SYNC_W_SECRET_AND_ENV_RESOLVED,
        ),
    ],
)
def test_installationconfig_thread_persistence_dburi_sync(w_kw, expected):
    installation_config = config_installation.InstallationConfig(**w_kw)

    found = installation_config.thread_persistence_dburi_sync

    assert found == expected


@pytest.mark.parametrize(
    "w_kw, expected",
    [
        (
            BARE_INSTALLATION_CONFIG_KW.copy(),
            config_installation.ASYNC_MEMORY_ENGINE_URL,
        ),
        (W_TP_DBURI_INSTALLATION_CONFIG_KW.copy(), TP_DBURI_ASYNC),
    ],
)
def test_installationconfig_thread_persistence_dburi_async(w_kw, expected):
    installation_config = config_installation.InstallationConfig(**w_kw)

    found = installation_config.thread_persistence_dburi_async

    assert found == expected


@pytest.mark.parametrize(
    "w_kw, expected",
    [
        (
            BARE_INSTALLATION_CONFIG_KW.copy(),
            config_installation.SYNC_MEMORY_ENGINE_URL,
        ),
        (W_RA_DBURI_INSTALLATION_CONFIG_KW.copy(), RA_DBURI_SYNC),
        (
            (
                W_RA_DBURI_W_SECRET_INSTALLATION_CONFIG_KW
                | {"secrets": [DB_SECRET_CONFIG]}
                | {"environment": {"DB_USER_NAME": DB_USER_NAME}}
            ),
            RA_DBURI_SYNC_W_SECRET_AND_ENV_RESOLVED,
        ),
    ],
)
def test_installationconfig_authorization_dburi_sync(w_kw, expected):
    installation_config = config_installation.InstallationConfig(**w_kw)

    found = installation_config.authorization_dburi_sync

    assert found == expected


@pytest.mark.parametrize(
    "w_kw, expected",
    [
        (
            BARE_INSTALLATION_CONFIG_KW.copy(),
            config_installation.ASYNC_MEMORY_ENGINE_URL,
        ),
        (W_RA_DBURI_INSTALLATION_CONFIG_KW.copy(), RA_DBURI_ASYNC),
    ],
)
def test_installationconfig_authorization_dburi_async(w_kw, expected):
    installation_config = config_installation.InstallationConfig(**w_kw)

    found = installation_config.authorization_dburi_async

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (
            BOGUS_INSTALLATION_CONFIG_YAML,
            None,
        ),
        (
            BARE_INSTALLATION_CONFIG_YAML,
            BARE_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_BARE_META_INSTALLATION_CONFIG_YAML,
            W_BARE_META_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_FULL_META_INSTALLATION_CONFIG_YAML,
            W_FULL_META_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_APP_ROUTER_OPERATIONS_INSTALLATION_CONFIG_YAML,
            W_APP_ROUTER_OPERATIONS_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_SECRETS_INSTALLATION_CONFIG_YAML,
            W_SECRETS_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_ENVIRONMENT_LIST_INSTALLATION_CONFIG_YAML,
            W_ENVIRONMENT_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_ENVIRONMENT_MAPPING_INSTALLATION_CONFIG_YAML,
            W_ENVIRONMENT_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_HR_CONFIG_FILE_INSTALLATION_CONFIG_YAML,
            W_HR_CONFIG_FILE_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_AGENT_CONFIG_INSTALLATION_CONFIG_YAML,
            W_AGENT_CONFIG_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_FACTORY_AGENT_CONFIG_INSTALLATION_CONFIG_YAML,
            W_FACTORY_AGENT_CONFIG_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_UPLOAD_PATH_INSTALLATION_CONFIG_YAML,
            W_UPLOAD_PATH_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_OIDC_PATHS_INSTALLATION_CONFIG_YAML,
            W_OIDC_PATHS_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_OIDC_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML,
            W_OIDC_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_ROOM_PATHS_INSTALLATION_CONFIG_YAML,
            W_ROOM_PATHS_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_ROOM_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML,
            W_ROOM_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_COMPLETION_PATHS_INSTALLATION_CONFIG_YAML,
            W_COMPLETION_PATHS_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_COMPLETION_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML,
            W_COMPLETION_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_QUIZZES_PATHS_INSTALLATION_CONFIG_YAML,
            W_QUIZZES_PATHS_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_QUIZZES_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML,
            W_QUIZZES_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_LOGGING_CONFIG_FILE_INSTALLATION_CONFIG_YAML,
            W_LOGGING_CONFIG_FILE_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_SKILLS_PATHS_INSTALLATION_CONFIG_YAML,
            W_SKILLS_PATHS_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_SKILLS_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML,
            W_SKILLS_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_LOGFIRE_CONFIG_INSTALLATION_CONFIG_YAML,
            W_LOGFIRE_CONFIG_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_TP_DBURI_INSTALLATION_CONFIG_YAML,
            W_TP_DBURI_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_TP_DBURI_W_SECRET_INSTALLATION_CONFIG_YAML,
            W_TP_DBURI_W_SECRET_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_RA_DBURI_INSTALLATION_CONFIG_YAML,
            W_RA_DBURI_INSTALLATION_CONFIG_KW.copy(),
        ),
        (
            W_RA_DBURI_W_SECRET_INSTALLATION_CONFIG_YAML,
            W_RA_DBURI_W_SECRET_INSTALLATION_CONFIG_KW.copy(),
        ),
    ],
)
def test_installationconfig_from_yaml(
    temp_dir,
    patched_soliplex_config,
    patched_tool_registries,
    patched_mcp_toolset_configs,
    patched_mcp_tool_wrappers,
    patched_skill_configs,
    patched_secret_getters,
    config_yaml,
    expected_kw,
):
    patched_soliplex_config["test_secret_func"] = test_meta.SECRET_SOURCE_FUNC
    config_path = temp_dir / "installation.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    expected_kw = copy.deepcopy(expected_kw)

    if expected_kw is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_installation.InstallationConfig.from_yaml(
                config_path, config_dict
            )

        assert exc.value._config_path == config_path

    else:
        patched = {"__doc__": "test_installationconfig_from_yaml"}

        if "meta" in expected_kw:
            icmeta_kw = expected_kw.pop("meta")
            expected_kw["meta"] = config_meta.InstallationConfigMeta(
                **icmeta_kw,
                _config_path=config_path,
            )
        else:
            expected_kw["meta"] = config_meta.InstallationConfigMeta(
                _config_path=config_path,
            )

        if "_haiku_rag_config_file" not in expected_kw:
            expected_kw["_haiku_rag_config_file"] = (
                config_path.parent / "haiku.rag.yaml"
            )
        else:
            # Match from_yaml: config_path.parent / hr_config_file
            expected_kw["_haiku_rag_config_file"] = (
                config_path.parent / expected_kw["_haiku_rag_config_file"]
            )

        lfssc = mock.Mock(spec_set=())
        fs_skill_config = mock.create_autospec(
            config_skills.FilesystemSkillConfig
        )
        lfssc.return_value = {
            test_skills.FILESYSTEM_SKILL_NAME: fs_skill_config,
        }
        lepsc = mock.Mock(spec_set=())
        ep_skill_config = mock.create_autospec(
            config_skills.EntrypointSkillConfig
        )
        lepsc.return_value = {
            test_skills.ENTRYPOINT_SKILL_NAME: ep_skill_config,
        }

        if "_skill_configs" in expected_kw:
            patched["_load_filesystem_skill_configs"] = lfssc
            patched["_load_entrypoint_skill_configs"] = lepsc

        with mock.patch.multiple(config_installation, **patched):
            expected = config_installation.InstallationConfig(
                **expected_kw,
                _config_path=config_path,
            )

        if "upload_path" in expected_kw:
            exp_upload_path = temp_dir / expected_kw["upload_path"]
        else:
            exp_upload_path = None

        expected = dataclasses.replace(expected, upload_path=exp_upload_path)

        if "oidc_paths" in expected_kw:
            exp_oidc_paths = [
                temp_dir / oidc_path for oidc_path in expected_kw["oidc_paths"]
            ]
        else:
            exp_oidc_paths = [temp_dir / "oidc"]

        expected = dataclasses.replace(expected, oidc_paths=exp_oidc_paths)

        if "room_paths" in expected_kw:
            exp_room_paths = [
                temp_dir / room_path for room_path in expected_kw["room_paths"]
            ]
        else:
            exp_room_paths = [temp_dir / "rooms"]

        expected = dataclasses.replace(expected, room_paths=exp_room_paths)

        with mock.patch.multiple(config_installation, **patched):
            found = config_installation.InstallationConfig.from_yaml(
                config_path,
                config_dict,
            )

        if "secrets" in expected_kw:
            replaced_secrets = []
            for secret in expected.secrets:
                replaced_sources = [
                    dataclasses.replace(
                        source,
                        _config_path=config_path,
                        _installation_config=found,
                    )
                    for source in secret.sources
                ]
                replaced_secrets.append(
                    dataclasses.replace(
                        secret,
                        sources=replaced_sources,
                        _config_path=config_path,
                        _installation_config=found,
                    )
                )
            expected = dataclasses.replace(expected, secrets=replaced_secrets)

        if "environment" in expected_kw:
            expected = dataclasses.replace(
                expected, _environment_from_config=expected_kw["environment"]
            )

        if "agent_configs" in expected_kw:
            # Assign '_installation_config' after found is constructed.
            for exp_agent_config in expected.agent_configs:
                exp_agent_config._installation_config = found
                exp_agent_config._config_path = config_path

        if "logfire_config" in expected_kw:
            expected.logfire_config._installation_config = found
            expected.logfire_config._config_path = config_path

        assert found.meta == expected.meta
        assert found == expected


W_ENVIRONMENT_LIST_ONLY_STR_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
environment:
  - "TEST_ENVVAR"
"""


W_ENVIRONMENT_LIST_NO_VALUE_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
environment:
  - name: "TEST_ENVVAR"
"""


W_ENVIRONMENT_MAPPING_NO_VALUE_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
environment:
  TEST_ENVVAR:
"""


@pytest.mark.parametrize(
    "config_yaml",
    [
        W_ENVIRONMENT_LIST_ONLY_STR_INSTALLATION_CONFIG_YAML,
        W_ENVIRONMENT_LIST_NO_VALUE_INSTALLATION_CONFIG_YAML,
        W_ENVIRONMENT_MAPPING_NO_VALUE_INSTALLATION_CONFIG_YAML,
    ],
)
def test_installationconfig_from_yaml_environ_wo_value(temp_dir, config_yaml):
    TEST_VALUE = "test value"

    yaml_file = temp_dir / "installation.yaml"
    yaml_file.write_text(config_yaml)

    expected_kw = copy.deepcopy(BARE_INSTALLATION_CONFIG_KW)
    expected_kw["environment"] = {"TEST_ENVVAR": None}
    expected = config_installation.InstallationConfig(**expected_kw)
    expected = dataclasses.replace(
        expected,
        _config_path=yaml_file,
        meta=dataclasses.replace(
            expected.meta,
            _config_path=yaml_file,
        ),
        _haiku_rag_config_file=(yaml_file.parent / "haiku.rag.yaml"),
        oidc_paths=[temp_dir / "oidc"],
        room_paths=[temp_dir / "rooms"],
        completion_paths=[temp_dir / "completions"],
        quizzes_paths=[temp_dir / "quizzes"],
        filesystem_skills_paths=[temp_dir / "skills"],
    )

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    with mock.patch.dict("os.environ", clear=True, TEST_ENVVAR=TEST_VALUE):
        found = config_installation.InstallationConfig.from_yaml(
            yaml_file, config_dict
        )

    assert found == expected


@pytest.mark.parametrize("w_aro", [False, True])
@pytest.mark.parametrize("w_logfire_config", [False, True])
@pytest.mark.parametrize("w_title_agent_config_id", [None, "title"])
def test_installationconfig_as_yaml(
    patched_app_routers,
    w_title_agent_config_id,
    w_logfire_config,
    w_aro,
):
    meta = mock.create_autospec(config_meta.InstallationConfigMeta)
    secret_1 = config_secrets.SecretConfig(secret_name="SECRET_ONE")
    secret_2 = config_secrets.SecretConfig(secret_name="SECRET_TWO")
    agent_config = config_agents.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        model_name=test_agents.MODEL_NAME,
        provider_base_url=test_agents.PROVIDER_BASE_URL,
    )

    kwargs = {}

    if w_logfire_config:
        kwargs["logfire_config"] = config_logfire.LogfireConfig(
            token="secret:LOGFIRE_TOKEN",
        )

    if w_aro:
        kwargs["app_router_operations"] = [
            config_routing.AddAppRouter(
                group_name="test-group",
                router_name="my.package.router",
                prefix="/prefix",
            )
        ]

    installation_config = config_installation.InstallationConfig(
        id=INSTALLATION_ID,
        meta=meta,
        secrets=[secret_1, secret_2],
        environment={
            "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
        },
        _haiku_rag_config_file=pathlib.Path(HAIKU_RAG_CONFIG_FILE),
        agent_configs=[agent_config],
        title_agent_config_id=w_title_agent_config_id,
        _logging_config_file=pathlib.Path(LOGGING_CONFIG_FILE),
        oidc_paths=[pathlib.Path("./oidc-test")],
        room_paths=[
            pathlib.Path("/path/to/rooms"),
            pathlib.Path("./other/rooms"),
        ],
        completion_paths=[pathlib.Path("/path/to/completions")],
        quizzes_paths=[pathlib.Path("./other/quizzes")],
        filesystem_skills_paths=[pathlib.Path("./other/skills")],
        **kwargs,
    )

    expected = {
        "id": INSTALLATION_ID,
        "meta": meta.as_yaml,
        "secrets": [
            secret_1.as_yaml,
            secret_2.as_yaml,
        ],
        "environment": {
            "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
        },
        "haiku_rag_config_file": str(pathlib.Path(HAIKU_RAG_CONFIG_FILE)),
        "agent_configs": [
            agent_config.as_yaml,
        ],
        "logging_config_file": str(pathlib.Path(LOGGING_CONFIG_FILE)),
        "oidc_paths": [str(pathlib.Path("oidc-test"))],
        "room_paths": [
            str(pathlib.Path("/path/to/rooms")),
            str(pathlib.Path("other/rooms")),
        ],
        "completion_paths": [str(pathlib.Path("/path/to/completions"))],
        "quizzes_paths": [str(pathlib.Path("other/quizzes"))],
        "filesystem_skills_paths": [str(pathlib.Path("other/skills"))],
    }

    if w_title_agent_config_id is not None:
        expected["title_agent_config_id"] = w_title_agent_config_id

    if w_logfire_config:
        expected["logfire_config"] = (
            test_logfire.W_TOKEN_ONLY_LOGFIRE_CONFIG_AS_YAML
        )

    if w_aro:
        expected["app_router_operations"] = [
            {
                "kind": "add",
                "group_name": "test-group",
                "router_name": "my.package.router",
                "prefix": "/prefix",
                "replace_existing": False,
            }
        ]

    found = installation_config.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "w_pem_path",
    [
        test_authsystem.ABSOLUTE_OIDC_CLIENT_PEM_PATH,
        test_authsystem.RELATIVE_OIDC_CLIENT_PEM_PATH,
    ],
)
@pytest.mark.parametrize("w_pem", [False, "bare_top", "bare_authsys"])
@mock.patch("soliplex.config.installation._load_config_yaml")
def test_installationconfig_oidc_auth_system_configs_wo_existing(
    lcy,
    temp_dir,
    w_pem,
    w_pem_path,
):
    oidc_bare_path = temp_dir / "oidc_bare"
    # Match source: oidc_path / pem_path
    exp_oidc_client_pem_path = oidc_bare_path / w_pem_path

    bare_config_yaml = {
        "auth_systems": [test_authsystem.BARE_AUTHSYSTEM_CONFIG_KW.copy()],
    }

    if w_pem == "bare_top":
        bare_config_yaml["oidc_client_pem_path"] = w_pem_path
    elif w_pem == "bare_authsys":
        authsys = bare_config_yaml["auth_systems"][0]
        authsys["oidc_client_pem_path"] = w_pem_path
    else:
        assert not w_pem
        exp_oidc_client_pem_path = None

    w_scope_config_yaml = {
        "auth_systems": [test_authsystem.W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy()],
    }

    lcy.side_effect = [bare_config_yaml, w_scope_config_yaml]

    oidc_bare_path = temp_dir / "oidc_bare"
    oidc_bare_config = oidc_bare_path / "config.yaml"

    oidc_w_scope_path = temp_dir / "oidc_w_scope"
    oidc_w_scope_config = oidc_w_scope_path / "config.yaml"

    oidc_bare_kw = test_authsystem.BARE_AUTHSYSTEM_CONFIG_KW.copy()
    oidc_bare_kw["oidc_client_pem_path"] = exp_oidc_client_pem_path
    oidc_bare_kw["_config_path"] = oidc_bare_config

    oidc_w_scope_kw = test_authsystem.W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy()
    oidc_w_scope_kw["oidc_client_pem_path"] = None
    oidc_w_scope_kw["_config_path"] = oidc_w_scope_config

    i_config_kw = BARE_INSTALLATION_CONFIG_KW.copy()
    i_config_kw["oidc_paths"] = [oidc_bare_path, oidc_w_scope_path]

    i_config = config_installation.InstallationConfig(**i_config_kw)

    expected = [
        config_authsystem.OIDCAuthSystemConfig(
            _installation_config=i_config,
            **oidc_bare_kw,
        ),
        config_authsystem.OIDCAuthSystemConfig(
            _installation_config=i_config,
            **oidc_w_scope_kw,
        ),
    ]

    found = i_config.oidc_auth_system_configs

    for f_asc, e_asc in zip(found, expected, strict=True):
        assert f_asc == e_asc


def test_installationconfig_oidc_auth_system_configs_w_existing():
    OASC_1, OASC_2 = object(), object()

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_oidc_auth_system_configs"] = [OASC_1, OASC_2]

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.oidc_auth_system_configs

    assert found == [OASC_1, OASC_2]


def test_installationconfig_room_configs_wo_existing(temp_dir):
    ROOM_IDS = ["foo", "bar", ".baz"]

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT

    rooms = temp_dir / "rooms"
    rooms.mkdir()

    for room_id in ROOM_IDS:
        room_path = rooms / room_id
        room_path.mkdir()
        room_config = room_path / "room_config.yaml"

        if room_id.startswith("."):
            room_id = room_id[1:]

        room_config.write_text(
            test_rooms.BARE_ROOM_CONFIG_YAML.replace(
                f'id: "{test_rooms.ROOM_ID}"',
                f'id: "{room_id}"',
                1,
            ),
        )

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.room_configs

    assert found["foo"].id == "foo"
    assert found["bar"].id == "bar"

    assert ".baz" not in found
    assert "baz" not in found


def test_installationconfig_room_configs_wo_existing_w_conflict(temp_dir):
    ROOM_PATHS = ["./foo", "./bar"]

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT
    kw["room_paths"] = ROOM_PATHS

    for room_path in ROOM_PATHS:
        room_path = temp_dir / room_path
        room_path.mkdir()
        room_config = room_path / "room_config.yaml"
        room_config.write_text(
            test_rooms.BARE_ROOM_CONFIG_YAML.replace(
                # f'id: "{ROOM_ID}"', f'id: "{room_id}"', 1, # conflict on ID
                f'name: "{test_rooms.ROOM_NAME}"',
                f'name: "{room_path.name}"',
                1,
            )
        )

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.room_configs

    assert found[test_rooms.ROOM_ID].id == test_rooms.ROOM_ID
    # order of 'room_paths' governs who wins
    assert found[test_rooms.ROOM_ID].name == "foo"


def test_installationconfig_room_configs_w_existing():
    RC_1, RC_2 = object(), object()
    existing = {"room_1": RC_1, "room_2": RC_2}

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_room_configs"] = existing

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.room_configs

    assert found["room_1"] == RC_1
    assert found["room_2"] == RC_2


def test_installationconfig_completion_configs_wo_existing(temp_dir):
    COMPLETION_IDS = ["foo", "bar"]

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT

    completions = temp_dir / "completions"
    completions.mkdir()

    for completion_id in COMPLETION_IDS:
        completion_path = completions / completion_id
        completion_path.mkdir()
        completion_config = completion_path / "completion_config.yaml"
        completion_config.write_text(
            test_completions.BARE_COMPLETION_CONFIG_YAML.replace(
                f'id: "{test_completions.COMPLETION_ID}"',
                f'id: "{completion_id}"',
                1,
            ),
        )

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.completion_configs

    assert found["foo"].id == "foo"
    assert found["bar"].id == "bar"


def test_installationconfig_completion_configs_wo_existing_w_conflict(
    temp_dir,
):
    COMPLETION_PATHS = ["./foo", "./bar"]

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT
    kw["completion_paths"] = COMPLETION_PATHS

    for completion_path in COMPLETION_PATHS:
        completion_path = temp_dir / completion_path
        completion_path.mkdir()
        completion_config = completion_path / "completion_config.yaml"
        completion_config.write_text(
            test_completions.FULL_COMPLETION_CONFIG_YAML.replace(
                # f'id: "{COMPLETION_ID}"',
                # f'id: "{completion_id}"',
                # 1, # conflict on ID
                f'name: "{test_completions.COMPLETION_NAME}"',
                f'name: "{completion_path.name}"',
                1,
            )
        )

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.completion_configs

    compl_id = test_completions.COMPLETION_ID
    assert found[compl_id].id == compl_id
    # order of 'completion_paths' governs who wins
    assert found[compl_id].name == "foo"


def test_installationconfig_completion_configs_w_existing():
    CC_1, CC_2 = object(), object()
    existing = {"completion_1": CC_1, "completion_2": CC_2}

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_completion_configs"] = existing

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.completion_configs

    assert found["completion_1"] == CC_1
    assert found["completion_2"] == CC_2


@pytest.mark.parametrize("w_error", [False, True])
def test_installationconfig_avl_fs_skill_configs_wo_existing(
    temp_dir,
    w_error,
    patched_agui_features,
):
    SKILL_NAMES = ["foo", "bar"]

    if w_error:
        FOREMATTER = """\
---
name: {skill_name}
---
"""
    else:
        FOREMATTER = """\
---
name: {skill_name}
description: Describing {skill_name}
---
"""

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"

    skills_dir = temp_dir / "skills"
    skills_dir.mkdir()

    for skill_name in SKILL_NAMES:
        skill_path = skills_dir / skill_name
        skill_path.mkdir()
        skill_config = skill_path / "SKILL.md"
        skill_config.write_text(FOREMATTER.format(skill_name=skill_name))

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.available_filesystem_skill_configs

    if w_error:
        assert found["foo"].name == "foo"
        assert found["foo"].errors
        assert found["bar"].name == "bar"
        assert found["bar"].errors
    else:
        assert found["foo"].name == "foo"
        assert not found["foo"].errors
        assert found["bar"].name == "bar"
        assert not found["bar"].errors


@pytest.mark.parametrize("w_error", [False, True])
def test_installationconfig_avl_fs_skill_configs_wo_existing_w_conflict(
    temp_dir,
    w_error,
    patched_agui_features,
):
    SKILLS_PATHS = ["./foo", "./bar"]

    if w_error:
        FOREMATTER = """\
---
name: {skill_name}
---
"""
    else:
        FOREMATTER = """\
---
name: {skill_name}
description: Describing {skill_name} in {skills_path}
---
"""

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"
    kw["filesystem_skills_paths"] = SKILLS_PATHS

    for skills_path in SKILLS_PATHS:
        skill_path = temp_dir / skills_path / test_skills.SKILL_NAME
        skill_path.mkdir(parents=True)
        skill_config = skill_path / "SKILL.md"
        skill_config.write_text(
            FOREMATTER.format(
                skill_name=test_skills.SKILL_NAME, skills_path=skills_path
            )
        )

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.available_filesystem_skill_configs

    f_skill = found[test_skills.SKILL_NAME]
    if w_error:
        assert f_skill.name == test_skills.SKILL_NAME
        assert f_skill.errors
    else:
        found = i_config.available_filesystem_skill_configs
        f_skill = found[test_skills.SKILL_NAME]
        assert f_skill.name == test_skills.SKILL_NAME
        # order of 'completion_paths' governs who wins
        assert (
            f_skill.description
            == f"Describing {test_skills.SKILL_NAME} in ./foo"
        )
        assert not f_skill.errors


def test_installationconfig_avl_fs_skill_configs_w_existing():
    SC_1, SC_2 = object(), object()
    existing = {"skill_1": SC_1, "skill_2": SC_2}

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_available_filesystem_skill_configs"] = existing

    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.available_filesystem_skill_configs

    assert found["skill_1"] == SC_1
    assert found["skill_2"] == SC_2


@mock.patch("haiku.skills.discovery.discover_from_entrypoints")
def test_installationconfig_avl_ep_skill_configs_wo_existing(
    dfe,
    patched_soliplex_config,
    patched_agui_features,
    temp_dir,
):
    STATE_NAMESPACE = "test-state-namespace"

    class DerivedFeatureModel(agui_features.EmptyFeatureModel):
        pass

    ic_hr_config_file = temp_dir / "haiku.rag.yaml"
    ic_hr_config_file.write_text("environment: installation")
    db_path = temp_dir / "test.lancedb"

    ep_skill_1 = mock.create_autospec(hs_models.Skill)
    ep_skill_1.metadata = mock.create_autospec(hs_models.SkillMetadata)
    ep_skill_1.metadata.name = "foo"
    ep_skill_1.state_namespace = STATE_NAMESPACE
    ep_skill_1.state_type = agui_features.EmptyFeatureModel
    ep_skill_1.extras = {
        "db_path": db_path,
    }

    ep_skill_2 = mock.create_autospec(hs_models.Skill)
    ep_skill_2.metadata = mock.create_autospec(hs_models.SkillMetadata)
    ep_skill_2.metadata.name = "bar"
    ep_skill_2.state_namespace = STATE_NAMESPACE
    ep_skill_2.state_type = DerivedFeatureModel
    ep_skill_2.extras = {}

    dfe.return_value = [ep_skill_1, ep_skill_2]

    kw = BARE_INSTALLATION_CONFIG_KW.copy() | {
        "_haiku_rag_config_file": ic_hr_config_file,
    }
    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.available_entrypoint_skill_configs

    assert found["foo"].name == "foo"
    assert found["bar"].name == "bar"

    ep_skill_1.reconfigure.assert_called_once_with(
        db_path=db_path,
        config=i_config.haiku_rag_config,
    )

    # First registration wins
    registered = patched_agui_features[STATE_NAMESPACE]
    assert registered.name == STATE_NAMESPACE
    assert registered.model_klass is agui_features.EmptyFeatureModel


@mock.patch("haiku.skills.discovery.discover_from_entrypoints")
def test_installationconfig_avl_ep_skill_configs_wo_existing_w_conflict(
    dfe,
    patched_soliplex_config,
    patched_agui_features,
):
    ep_skill_1 = mock.create_autospec(hs_models.Skill)
    ep_skill_1.metadata = mock.create_autospec(hs_models.SkillMetadata)
    ep_skill_1.metadata.name = test_skills.SKILL_NAME
    skill_desc_1 = f"{test_skills.SKILL_DESC} (from ep_skill_1)"
    ep_skill_1.metadata.description = skill_desc_1
    ep_skill_1.extras = {}

    ep_skill_2 = mock.create_autospec(hs_models.Skill)
    ep_skill_2.metadata = mock.create_autospec(hs_models.SkillMetadata)
    ep_skill_2.metadata.name = test_skills.SKILL_NAME
    skill_desc_2 = f"{test_skills.SKILL_DESC} (from ep_skill_2)"
    ep_skill_2.metadata.description = skill_desc_2
    ep_skill_2.extras = {}

    dfe.return_value = [ep_skill_1, ep_skill_2]

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.available_entrypoint_skill_configs

    assert found[test_skills.SKILL_NAME].description == skill_desc_1


@mock.patch("haiku.skills.discovery.discover_from_entrypoints")
def test_installationconfig_avl_ep_skill_configs_w_existing(
    dfe,
    patched_soliplex_config,
):
    SC_1, SC_2 = object(), object()
    existing = {"skill_1": SC_1, "skill_2": SC_2}

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_available_entrypoint_skill_configs"] = existing
    i_config = config_installation.InstallationConfig(**kw)

    found = i_config.available_entrypoint_skill_configs

    assert found["skill_1"] == SC_1
    assert found["skill_2"] == SC_2


def test_installationconfig_skill_configs_wo_set():
    kw = BARE_INSTALLATION_CONFIG_KW.copy()

    i_config = config_installation.InstallationConfig(**kw)

    assert i_config.skill_configs == {}


def test_installationconfig_skill_configs_w_set():
    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    skill_config = mock.create_autospec(config_skills._SkillConfigModelBase)
    kw["_skill_configs"] = {
        test_skills.SKILL_NAME: skill_config,
    }
    kw["_available_filesystem_skill_configs"] = {
        test_skills.SKILL_NAME: skill_config,
        "other-skill": object(),
    }
    kw["_available_entrypoint_skill_configs"] = {}

    i_config = config_installation.InstallationConfig(**kw)

    assert i_config.skill_configs == {test_skills.SKILL_NAME: skill_config}


@pytest.mark.parametrize(
    "w_kwargs, expected",
    [
        (BARE_INSTALLATION_CONFIG_KW.copy(), None),
        (W_UPLOAD_PATH_INSTALLATION_CONFIG_KW.copy(), "uploads/rooms"),
    ],
)
def test_installationconfig_rooms_upload_path(
    temp_dir,
    w_kwargs,
    expected,
):
    w_kwargs["_config_path"] = temp_dir / "installation.yaml"

    upload_path = w_kwargs.pop("upload_path", None)
    if upload_path is not None:
        w_kwargs["upload_path"] = pathlib.Path(upload_path)

    if expected is not None:
        expected = temp_dir / expected

    i_config = config_installation.InstallationConfig(**w_kwargs)

    found = i_config.rooms_upload_path

    assert found == expected


@pytest.mark.parametrize(
    "w_kwargs, expected",
    [
        (BARE_INSTALLATION_CONFIG_KW.copy(), None),
        (W_UPLOAD_PATH_INSTALLATION_CONFIG_KW.copy(), "uploads/threads"),
    ],
)
def test_installationconfig_threads_upload_path(
    temp_dir,
    w_kwargs,
    expected,
):
    w_kwargs["_config_path"] = temp_dir / "installation.yaml"

    upload_path = w_kwargs.pop("upload_path", None)
    if upload_path is not None:
        w_kwargs["upload_path"] = pathlib.Path(upload_path)

    if expected is not None:
        expected = temp_dir / expected

    i_config = config_installation.InstallationConfig(**w_kwargs)

    found = i_config.threads_upload_path

    assert found == expected


def test_installationconfig_reload_configurations(temp_dir):
    existing = object()

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_oidc_auth_system_configs"] = existing
    kw["_room_configs"] = existing
    kw["_completion_configs"] = existing
    kw["_available_filesystem_skill_configs"] = {}
    kw["_available_entrypoint_skill_configs"] = {}
    kw["_skill_configs"] = ()
    i_config = config_installation.InstallationConfig(
        _config_path=temp_dir / "installation.yaml",
        **kw,
    )

    with (
        mock.patch.multiple(
            i_config,
            _load_oidc_auth_system_configs=mock.DEFAULT,
            _load_room_configs=mock.DEFAULT,
            _load_completion_configs=mock.DEFAULT,
        ) as ic_patch,
        mock.patch.multiple(
            config_installation,
            _load_filesystem_skill_configs=mock.DEFAULT,
            _load_entrypoint_skill_configs=mock.DEFAULT,
        ) as config_patch,
    ):
        i_config.reload_configurations()

    assert (
        i_config._oidc_auth_system_configs
        is ic_patch["_load_oidc_auth_system_configs"].return_value
    )

    assert (
        i_config._room_configs is ic_patch["_load_room_configs"].return_value
    )

    assert (
        i_config._completion_configs
        is ic_patch["_load_completion_configs"].return_value
    )

    assert (
        i_config._available_filesystem_configs
        is config_patch["_load_filesystem_skill_configs"].return_value
    )
    config_patch["_load_filesystem_skill_configs"].assert_called_once_with(
        i_config,
    )

    assert (
        i_config._available_entrypoint_configs
        is config_patch["_load_entrypoint_skill_configs"].return_value
    )
    config_patch["_load_entrypoint_skill_configs"].assert_called_once_with(
        i_config,
    )


@pytest.fixture
def populated_temp_dir(temp_dir):
    default = temp_dir / "installation.yaml"
    default.write_text('id: "testing"')

    not_a_yaml_file = temp_dir / "not_a_yaml_file.yaml"
    not_a_yaml_file.write_bytes(b"\xde\xad\xbe\xef")

    there_but_no_config = temp_dir / "there-but-no-config"
    there_but_no_config.mkdir()

    there_with_config = temp_dir / "there-with-config"
    there_with_config.mkdir()
    there_with_config_filename = there_with_config / "installation.yaml"
    there_with_config_filename.write_text('id: "there-with-config"')

    alt_config = temp_dir / "alt-config"
    alt_config.mkdir()
    alt_config_filename = alt_config / "filename.yaml"
    alt_config_filename.write_text('id: "alt-config"')

    return temp_dir


@pytest.mark.parametrize(
    "rel_path, raises, expected_id",
    [
        (".", False, "testing"),
        ("./installation.yaml", False, "testing"),
        ("no_such_filename.yaml", config_exc.NoSuchConfig, None),
        ("not_a_yaml_file.yaml", config_exc.FromYamlException, None),
        ("/dev/null", config_exc.NoSuchConfig, None),
        ("./not-there", config_exc.NoSuchConfig, None),
        ("./there-but-no-config", config_exc.NoSuchConfig, None),
        ("./there-with-config", False, "there-with-config"),
        ("./alt-config/filename.yaml", False, "alt-config"),
    ],
)
def test_load_installation(populated_temp_dir, rel_path, raises, expected_id):
    target = populated_temp_dir / rel_path

    if raises:
        with pytest.raises(raises):
            config_installation.load_installation(target)

    else:
        installation = config_installation.load_installation(target)

        assert installation.id == expected_id
