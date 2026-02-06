import contextlib
import copy
import dataclasses
import functools
import inspect
import json
import pathlib
import ssl
import typing
from unittest import mock
from urllib import parse as url_parse

import pydantic
import pytest
import yaml
from haiku.rag import config as hr_config_module
from pydantic_ai import settings as ai_settings
from skills_ref import models as skill_models

from soliplex import config
from soliplex import secrets
from soliplex.agui import features

here = pathlib.Path(__file__).resolve().parent

NoRaise = contextlib.nullcontext()

AUTHSYSTEM_ID = "testing"
AUTHSYSTEM_TITLE = "Testing OIDC"
AUTHSYSTEM_SERVER_URL = "https://example.com/auth/realms/sso"
AUTHSYSTEM_TOKEN_VALIDATION_PEM = """\
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAlXYDp/ux5839pPyhRAjq
RZTeyv6fKZqgvJS2cvrNzjfttYni7/++nU2uywAiKRnxfVIf6TWKaC4/oy0VkLpW
mkC4oyj0ArST9OYWI9mqxqdweEHrzXf8CjU7Q88LVY/9JUmHAiKjOH17m5hLY+q9
cmIs33SMq9g7GMgPfABNsgh57Xei1sVPSzzSzTd80AguMF7B9hrNg6eTr69CN+3s
3535wDD7tBgPzhz1qJ+lhaBSWrht9mjYpX5S0/7IQOV9M7YVBsFYztpD4Ht9TQc0
jbVPyMXk2bi6vmfpfjCtio7RjDqi38wTf38RuD7mhPYyDOzGFcfSr4yNnORRKyYH
9QIDAQAB
-----END PUBLIC KEY-----
"""
AUTHSYSTEM_CLIENT_ID = "testing-oidc"

ABSOLUTE_OIDC_CLIENT_PEM_PATH = "/path/to/cacert.pem"
RELATIVE_OIDC_CLIENT_PEM_PATH = "./cacert.pem"
BARE_AUTHSYSTEM_CONFIG_KW = {
    "id": AUTHSYSTEM_ID,
    "title": AUTHSYSTEM_TITLE,
    "server_url": AUTHSYSTEM_SERVER_URL,
    "token_validation_pem": AUTHSYSTEM_TOKEN_VALIDATION_PEM,
    "client_id": AUTHSYSTEM_CLIENT_ID,
}
BARE_AUTHSYSTEM_CONFIG_YAML = f"""
    id: "{AUTHSYSTEM_ID}"
    title: "{AUTHSYSTEM_TITLE}"
    server_url: "{AUTHSYSTEM_SERVER_URL}"
    token_validation_pem: |
        -----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAlXYDp/ux5839pPyhRAjq
        RZTeyv6fKZqgvJS2cvrNzjfttYni7/++nU2uywAiKRnxfVIf6TWKaC4/oy0VkLpW
        mkC4oyj0ArST9OYWI9mqxqdweEHrzXf8CjU7Q88LVY/9JUmHAiKjOH17m5hLY+q9
        cmIs33SMq9g7GMgPfABNsgh57Xei1sVPSzzSzTd80AguMF7B9hrNg6eTr69CN+3s
        3535wDD7tBgPzhz1qJ+lhaBSWrht9mjYpX5S0/7IQOV9M7YVBsFYztpD4Ht9TQc0
        jbVPyMXk2bi6vmfpfjCtio7RjDqi38wTf38RuD7mhPYyDOzGFcfSr4yNnORRKyYH
        9QIDAQAB
        -----END PUBLIC KEY-----
    client_id: "{AUTHSYSTEM_CLIENT_ID}"
"""

AUTHSYSTEM_SCOPE = "test one two three"
W_SCOPE_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_SCOPE_AUTHSYSTEM_CONFIG_KW["scope"] = AUTHSYSTEM_SCOPE
W_SCOPE_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    scope: "{AUTHSYSTEM_SCOPE}"
"""

W_PEM_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_PEM_AUTHSYSTEM_CONFIG_KW["oidc_client_pem_path"] = (
    ABSOLUTE_OIDC_CLIENT_PEM_PATH
)
W_PEM_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{ABSOLUTE_OIDC_CLIENT_PEM_PATH}"
"""

AUTHSYSTEM_CLIENT_SECRET_LIT = "REALLY BIG SECRET"
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW["client_secret"] = (
    AUTHSYSTEM_CLIENT_SECRET_LIT
)
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    client_secret: "{AUTHSYSTEM_CLIENT_SECRET_LIT}"
"""

CLIENT_SECRET_NAME = "TEST_OIDC_CLIENT_SECRET"
AUTHSYSTEM_CLIENT_SECRET_SECRET = f"secret:{CLIENT_SECRET_NAME}"
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW["client_secret"] = (
    AUTHSYSTEM_CLIENT_SECRET_SECRET
)
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    client_secret: "{AUTHSYSTEM_CLIENT_SECRET_SECRET}"
"""

AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL_NAME = "cacert.pem"
AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL = "./cacert.pem"
W_OIDC_CPP_REL_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_OIDC_CPP_REL_KW["oidc_client_pem_path"] = AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL
W_OIDC_CPP_REL_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL}"
"""

AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS = str(
    pathlib.Path(here, "fixtures/cacert.pem")
)
W_OIDC_CPP_ABS_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_OIDC_CPP_ABS_KW["oidc_client_pem_path"] = AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS
W_OIDC_CPP_ABS_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS}"
"""

W_ERROR_AUTHSYSTM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    unknown: "BOGUS"
"""


# This one raises
BOGUS_STDIO_MCTC_CONFIG_YAML = ""

BARE_STDIO_MCTC_CONFIG_KW = {
    "command": "cat",
}
BARE_STDIO_MCTC_CONFIG_YAML = """
    command: "cat"
"""

FULL_STDIO_MCTC_CONFIG_KW = {
    "command": "cat",
    "args": [
        "-a",
    ],
    "env": {"FOO": "BAR"},
    "allowed_tools": [
        "some_tool",
    ],
}
FULL_STDIO_MCTC_CONFIG_YAML = """
    command: "cat"
    args:
       - "-a"
    env:
        FOO: "BAR"
    allowed_tools:
      - "some_tool"
"""

# This one raises
BOGUS_HTTP_MCTC_CONFIG_YAML = ""

BARE_HTTP_MCTC_CONFIG_KW = {
    "url": "https://example.com/api",
}
BARE_HTTP_MCTC_CONFIG_YAML = """
    url: "https://example.com/api"
"""

FULL_HTTP_MCTC_CONFIG_KW = {
    "url": "https://example.com/api",
    "headers": {
        "Authorization": "Bearer DEADBEEF",
    },
    "query_params": {
        "foo": "bar",
    },
    "allowed_tools": [
        "some_tool",
    ],
}
FULL_HTTP_MCTC_CONFIG_YAML = """
    url: "https://example.com/api"
    headers:
        Authorization: "Bearer DEADBEEF"
    query_params:
        foo: "bar"
    allowed_tools:
      - "some_tool"
"""


AGENT_ID = "testing-agent"
TEMPLATE_AGENT_ID = "testing-template"
W_EXTRA_CONFIG_TEMPLATE_AGENT_ID = "testing-template-w-extra-config"
BOGUS_TEMPLATE_AGENT_ID = "BOGUS"
SYSTEM_PROMPT = "You are a test"
MODEL_NAME = "test-model"
OTHER_MODEL_NAME = "test-model-other"
PROVIDER_BASE_URL = "https://provider.example.com/api"
OTHER_PROVIDER_BASE_URL = "https://other-provider.example.com/api"
PROVIDER_KEY_ENVVAR = "TEST_API_KEY"
PROVIDER_KEY_VALUE = "DEADBEEF"
OLLAMA_BASE_URL = "https://example.com:12345"
AGUI_FEATURE_NAME = "test-agui-feature"

BARE_INSTALLATION_CONFIG_ENVIRONMENT = {
    "OLLAMA_BASE_URL": PROVIDER_BASE_URL,
}

TEST_QUIZ_ID = "test_quiz"
TEST_QUIZ_TITLE = "Test Quiz"
TEST_QUIZ_STEM = "question_file"
TEST_QUIZ_OVR = "/path/to/question_file.json"
TEST_QUIZ_MODEL_DEFAULT = "gpt-oss:20b"
TEST_QUIZ_MODEL_EXPLICIT = "qwen3"
TEST_QUIZ_PROVIDER_BASE_URL = "https://llm.example.com"
INPUTS = "What color is the sky"
EXPECTED_ANSWER = "Blue"
QA_QUESTION_UUID = "DEADBEEF"
MC_QUESTION_UUID = "FACEDACE"
QUESTION_TYPE_QA = "qa"
QUESTION_TYPE_MC = "multiple-choice"
MC_OPTIONS = ["orange", "blue", "purple"]

TEST_QUIZ_W_STEM_KW = {
    "id": TEST_QUIZ_ID,
    "title": TEST_QUIZ_TITLE,
    "question_file": TEST_QUIZ_STEM,
    "randomize": True,
    "max_questions": 3,
    "judge_agent": {
        "id": "test-quiz-judge",
        "model_name": TEST_QUIZ_MODEL_EXPLICIT,
        "provider_base_url": TEST_QUIZ_PROVIDER_BASE_URL,
    },
}
TEST_QUIZ_W_STEM_YAML = f"""
id: "{TEST_QUIZ_ID}"
title: "{TEST_QUIZ_TITLE}"
question_file: "{TEST_QUIZ_STEM}"
randomize: true
max_questions: 3
judge_agent:
    id: "test-quiz-judge"
    model_name: {TEST_QUIZ_MODEL_EXPLICIT}
    provider_base_url: {TEST_QUIZ_PROVIDER_BASE_URL}
"""

TEST_QUIZ_W_OVR_KW = {
    "id": TEST_QUIZ_ID,
    "question_file": TEST_QUIZ_OVR,
    "judge_agent": {
        "id": f"quiz-{TEST_QUIZ_ID}-judge",
        "model_name": TEST_QUIZ_MODEL_DEFAULT,
    },
}
TEST_QUIZ_W_OVR_YAML = f"""
id: "{TEST_QUIZ_ID}"
question_file: "{TEST_QUIZ_OVR}"
"""

ROOM_ID = "test-room"
ROOM_NAME = "Test Room"
ROOM_DESCRIPTION = "This room is for testing"
WELCOME_MESSAGE = "Welcome to this room!"
SUGGESTION = "Try us out for a spin!"
IMAGE_FILENAME = "test_image.jpg"

HTTP_MCP_URL = "https://example.com/services/baz/mcp"
HTTP_MCP_QP_KEY = "frob"
HTTP_MCP_QP_VALUE = "secret:BAZQUYTH"
HTTP_MCP_QUERY_PARAMS = {HTTP_MCP_QP_KEY: HTTP_MCP_QP_VALUE}
BEARER_TOKEN = "FACEDACE"
HTTP_MCP_AUTH_HEADER = {"Authorization": "Bearer secret:BEARER_TOKEN"}
QUIZ_ID = "test_quiz"

DADS_BASE_URL = "https://docs.stage.josce.mil/dev/"
DADS_SSO_SERVER_URL = "https://sso.test.josce.mil/auth/"
DADS_BEARER_TOKEN = "CAFEBEAD"
DADS_API_CONFIG_KW = {
    "base_url": DADS_BASE_URL,
    "sso_server_url": DADS_SSO_SERVER_URL,
    "verify_ssl_certs": False,
    "bearer_token": DADS_BEARER_TOKEN,
}
DADS_API_CONFIG_YAML = f"""
base_url: "{DADS_BASE_URL}"
sso_server_url: "{DADS_SSO_SERVER_URL}"
verify_ssl_certs: false
bearer_token: "{DADS_BEARER_TOKEN}"
"""
FADTC_PROJECT = "test-project"
FADTC_SOURCE_DOC_PATH_1 = "modules/ROOT/pages/test-one.adoc"
FADTC_SOURCE_DOC_PATH_2 = "modules/ROOT/pages/test-two.adoc"
FADTC_CONFIG_KW = {
    "project": FADTC_PROJECT,
    "source_document_paths": [
        FADTC_SOURCE_DOC_PATH_1,
        FADTC_SOURCE_DOC_PATH_2,
    ],
    "dads_api_config_path": None,  # to be replaced
    "allow_mcp": True,
}


BOGUS_AGENT_CONFIG_YAML = ""

W_KIND_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    kind="testing",
)

BARE_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    system_prompt=SYSTEM_PROMPT,
)
BARE_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
system_prompt: "{SYSTEM_PROMPT}"
"""

W_PROVIDER_KW_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    provider_type=config.LLMProviderType.OPENAI,
    provider_base_url=OTHER_PROVIDER_BASE_URL,
    provider_key="secret:OTHER_PROVIDER_KEY",
)
W_PROVIDER_KW_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
provider_type: "openai"
provider_base_url: "{OTHER_PROVIDER_BASE_URL}"
provider_key: "secret:OTHER_PROVIDER_KEY"
"""

AGENT_RETRIES = 7
W_RETRIES_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    retries=AGENT_RETRIES,
)
W_RETRIES_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
retries: {AGENT_RETRIES}
"""

MODEL_SETTING_MAX_TOKENS = 1000
MODEL_SETTING_TEMPERATURE = 0.90
MODEL_SETTING_TOP_P = 0.70
MODEL_SETTING_TIMEOUT = 60
MODEL_SETTING_PARALLELL_TOOL_CALLS = True
MODEL_SETTING_SEED = 1234
MODEL_SETTING_FREQUENCY_PENALTY = 0.31
MODEL_SETTING_PRESENCE_PENALTY = 0.21
MODEL_SETTING_LOGIT_BIAS = {"waaa": 14}
MODEL_SETTING_STOP_SEQUENCE = "STOP"
MODEL_SETTING_EXTRA_HEADER_NAME = "test-header"
MODEL_SETTING_EXTRA_HEADER_VALUE = "test-header-value"
MODEL_SETTING_EXTRA_BODY_NAME = "test-body"
MODEL_SETTING_EXTRA_BODY_VALUE = "test-body-value"

W_MODEL_SETTINGS_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    provider_type="ollama",
    model_settings=ai_settings.ModelSettings(
        max_tokens=MODEL_SETTING_MAX_TOKENS,
        temperature=MODEL_SETTING_TEMPERATURE,
        top_p=MODEL_SETTING_TOP_P,
        timeout=MODEL_SETTING_TIMEOUT,
        parallel_tool_calls=MODEL_SETTING_PARALLELL_TOOL_CALLS,
        seed=MODEL_SETTING_SEED,
        frequency_penalty=MODEL_SETTING_FREQUENCY_PENALTY,
        presence_penalty=MODEL_SETTING_PRESENCE_PENALTY,
        logit_bias=MODEL_SETTING_LOGIT_BIAS,
        stop_sequences=[MODEL_SETTING_STOP_SEQUENCE],
        extra_headers={
            MODEL_SETTING_EXTRA_HEADER_NAME: MODEL_SETTING_EXTRA_HEADER_VALUE,
        },
        extra_body={
            MODEL_SETTING_EXTRA_BODY_NAME: MODEL_SETTING_EXTRA_BODY_VALUE,
        },
    ),
)
W_MODEL_SETTINGS_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
model_settings:
    max_tokens: {MODEL_SETTING_MAX_TOKENS}
    temperature: {MODEL_SETTING_TEMPERATURE}
    top_p: {MODEL_SETTING_TOP_P}
    timeout: {MODEL_SETTING_TIMEOUT}
    parallel_tool_calls: {str(MODEL_SETTING_PARALLELL_TOOL_CALLS).lower()}
    seed: {MODEL_SETTING_SEED}
    frequency_penalty: {MODEL_SETTING_FREQUENCY_PENALTY}
    presence_penalty: {MODEL_SETTING_PRESENCE_PENALTY}
    logit_bias: {MODEL_SETTING_LOGIT_BIAS}
    stop_sequences:
        - {MODEL_SETTING_STOP_SEQUENCE}
    extra_headers:
        {MODEL_SETTING_EXTRA_HEADER_NAME}: {MODEL_SETTING_EXTRA_HEADER_VALUE}
    extra_body:
        {MODEL_SETTING_EXTRA_BODY_NAME}: {MODEL_SETTING_EXTRA_BODY_VALUE}
"""


W_PROMPT_FILE_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    _system_prompt_path="./prompt.txt",
)
W_PROMPT_FILE_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
system_prompt: ./prompt.txt
"""

# 'model_name' not required heree:  supplied by template
W_PROMPT_FILE_W_TEMPLATE_ID_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    _template_id=TEMPLATE_AGENT_ID,
    _system_prompt_path="./prompt.txt",
)
W_PROMPT_FILE_W_TEMPLATE_ID_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{TEMPLATE_AGENT_ID}"
system_prompt: ./prompt.txt
"""

W_PROMPT_FILE_W_BOGUS_TEMPLATE_ID_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{BOGUS_TEMPLATE_AGENT_ID}"
system_prompt: ./prompt.txt
"""

W_AGUI_FEATURE_NAMES_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    system_prompt=SYSTEM_PROMPT,
    agui_feature_names=(AGUI_FEATURE_NAME,),
)
W_AGUI_FEATURE_NAMES_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
system_prompt: "{SYSTEM_PROMPT}"
agui_feature_names:
  - "{AGUI_FEATURE_NAME}"
"""

FACTORY_NAME = "soliplex.config.test_factory_wo_config"
WO_CONFIG_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    factory_name=FACTORY_NAME,
    with_agent_config=False,
)
WO_CONFIG_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
factory_name: "{FACTORY_NAME}"
with_agent_config: false
"""

W_CONFIG_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    factory_name=FACTORY_NAME,
    with_agent_config=True,
    extra_config={
        "foo": "Bar",
    },
)
W_CONFIG_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
factory_name: "{FACTORY_NAME}"
with_agent_config: true
extra_config:
  foo: "Bar"
"""

W_AGUI_FEATURE_NAMES_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    factory_name=FACTORY_NAME,
    with_agent_config=False,
    agui_feature_names=(AGUI_FEATURE_NAME,),
)
W_AGUI_FEATURE_NAMES_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
factory_name: "{FACTORY_NAME}"
with_agent_config: false
agui_feature_names:
  - "{AGUI_FEATURE_NAME}"
"""

W_BOGUS_TEMPLATE_ID_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{BOGUS_TEMPLATE_AGENT_ID}"
"""

W_TEMPLATE_ID_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    _template_id=TEMPLATE_AGENT_ID,
)
W_TEMPLATE_ID_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{TEMPLATE_AGENT_ID}"
"""

W_TEMPLATE_ID_W_EXTRA_CONFIG_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    _template_id=W_EXTRA_CONFIG_TEMPLATE_AGENT_ID,
    extra_config={
        "foo": "Bar",
    },
)
W_TEMPLATE_ID_W_EXTRA_CONFIG_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{W_EXTRA_CONFIG_TEMPLATE_AGENT_ID}"
extra_config:
  foo: "Bar"
"""

Q_UUID_1 = "DEADBEEF"
QUESTION_1 = "What color is the sky"
ANSWER_1 = "blue"
TYPE_1 = "qa"

Q_UUID_2 = "FACEDACE"
QUESTION_2 = "What color is grass?"
ANSWER_2 = "green"
TYPE_2 = "multiple-choice"
OPTIONS_2 = ["red", "green", "blue"]

QUESTIONS = [
    config.QuizQuestion(
        inputs=QUESTION_1,
        expected_output=ANSWER_1,
        metadata=config.QuizQuestionMetadata(
            uuid=Q_UUID_1,
            type=TYPE_1,
        ),
    ),
    config.QuizQuestion(
        inputs=QUESTION_2,
        expected_output=ANSWER_2,
        metadata=config.QuizQuestionMetadata(
            type=TYPE_2, uuid=Q_UUID_2, options=OPTIONS_2
        ),
    ),
]

HRC_OVERRIDE_KW = {
    "testing": "override",
}
HRC_OVERRIDE_YAML = """\
testing: "override"
"""

BOGUS_ROOM_CONFIG_YAML = ""

BARE_ROOM_CONFIG_KW = {
    "id": ROOM_ID,
    "name": ROOM_NAME,
    "description": ROOM_DESCRIPTION,
    "agent_config": config.AgentConfig(
        id=f"room-{ROOM_ID}",
        model_name=MODEL_NAME,
        system_prompt=SYSTEM_PROMPT,
    ),
}
BARE_ROOM_CONFIG_YAML = f"""\
id: "{ROOM_ID}"
name: "{ROOM_NAME}"
description: "{ROOM_DESCRIPTION}"
agent:
    model_name: "{MODEL_NAME}"
    system_prompt: "{SYSTEM_PROMPT}"
"""

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
    "agent_config": config.AgentConfig(
        id=f"room-{ROOM_ID}",
        model_name=MODEL_NAME,
        system_prompt=SYSTEM_PROMPT,
        agui_feature_names=(AGUI_FEATURE_NAME,),
    ),
    "quizzes": [
        config.QuizConfig(
            id=TEST_QUIZ_ID,
            question_file=TEST_QUIZ_OVR,
            judge_agent=config.AgentConfig(
                id="test-quiz-judge",
                model_name=TEST_QUIZ_MODEL_EXPLICIT,
                provider_base_url=TEST_QUIZ_PROVIDER_BASE_URL,
            ),
        ),
    ],
    "_agui_feature_names": [
        EXTRA_AGUI_FEATURE_NAME,
    ],
    "allow_mcp": True,
    "tool_configs": {
        "get_current_datetime": config.ToolConfig(
            tool_name="soliplex.tools.get_current_datetime",
            allow_mcp=True,
        ),
    },
    "mcp_client_toolset_configs": {
        "stdio_test": config.Stdio_MCP_ClientToolsetConfig(
            command="cat",
            args=[
                "-",
            ],
            env={
                "foo": "bar",
            },
        ),
        "http_test": config.HTTP_MCP_ClientToolsetConfig(
            url=HTTP_MCP_URL,
            headers={
                "Authorization": "Bearer secret:BEARER_TOKEN",
            },
            query_params=HTTP_MCP_QUERY_PARAMS,
        ),
    },
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
    model_name: "{MODEL_NAME}"
    system_prompt: "{SYSTEM_PROMPT}"
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
      url: "{HTTP_MCP_URL}"
      headers:
        Authorization: "Bearer secret:BEARER_TOKEN"
      query_params:
        {HTTP_MCP_QP_KEY}: "{HTTP_MCP_QP_VALUE}"
quizzes:
  - id: "{TEST_QUIZ_ID}"
    question_file: "{TEST_QUIZ_OVR}"
    judge_agent:
        id: "test-quiz-judge"
        model_name: {TEST_QUIZ_MODEL_EXPLICIT}
        provider_base_url: {TEST_QUIZ_PROVIDER_BASE_URL}
agui_feature_names:
  - {EXTRA_AGUI_FEATURE_NAME}
allow_mcp: true
"""

COMPLETION_ID = "test-completion"
COMPLETION_NAME = "Test Completions"

BARE_COMPLETION_CONFIG_KW = {
    "id": COMPLETION_ID,
    "agent_config": config.AgentConfig(
        id=f"completion-{COMPLETION_ID}",
        model_name=MODEL_NAME,
        system_prompt=SYSTEM_PROMPT,
    ),
}
BARE_COMPLETION_CONFIG_YAML = f"""\
id: "{COMPLETION_ID}"
agent:
    model_name: "{MODEL_NAME}"
    system_prompt: "{SYSTEM_PROMPT}"
"""

FULL_COMPLETION_CONFIG_KW = {
    "id": COMPLETION_ID,
    "name": COMPLETION_NAME,
    "agent_config": config.AgentConfig(
        id=f"completion-{COMPLETION_ID}",
        model_name=MODEL_NAME,
        system_prompt=SYSTEM_PROMPT,
    ),
    "tool_configs": {
        "get_current_datetime": config.ToolConfig(
            tool_name="soliplex.tools.get_current_datetime",
        ),
    },
    "mcp_client_toolset_configs": {
        "stdio_test": config.Stdio_MCP_ClientToolsetConfig(
            command="cat",
            args=[
                "-",
            ],
            env={
                "foo": "bar",
            },
        ),
        "http_test": config.HTTP_MCP_ClientToolsetConfig(
            url=HTTP_MCP_URL,
            headers={
                "Authorization": "Bearer secret:BEARER_TOKEN",
            },
            query_params=HTTP_MCP_QUERY_PARAMS,
        ),
    },
}
FULL_COMPLETION_CONFIG_YAML = f"""\
id: "{COMPLETION_ID}"
name: "{COMPLETION_NAME}"
agent:
    model_name: "{MODEL_NAME}"
    system_prompt: "{SYSTEM_PROMPT}"
tools:
    - tool_name: "soliplex.tools.get_current_datetime"
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
      url: "{HTTP_MCP_URL}"
      headers:
        Authorization: "Bearer secret:BEARER_TOKEN"
      query_params:
        {HTTP_MCP_QP_KEY}: "{HTTP_MCP_QP_VALUE}"
"""

EMPTY_LFIPYDAI_CONFIG_YAML = ""  # raises
DEFAULT_LFIPYDAI_EXP_KWARGS = {
    "include_binary_content": True,
    "include_content": True,
}

W_VALUES_LFIPYDAI_CONFIG_KW = {
    "include_binary_content": False,
    "include_content": False,
}
W_VALUES_LFIPYDAI_CONFIG_YAML = """\
include_binary_content: false
include_content: false
"""
W_VALUES_LFIPYDAI_CONFIG_EXP_KW = W_VALUES_LFIPYDAI_CONFIG_KW


EMPTY_LFIFAPI_CONFIG_YAML = ""  # raises
DEFAULT_LFIFAPI_EXP_KWARGS = {
    "capture_headers": False,
    "excluded_urls": None,
    "record_send_receive": False,
    "extra_spans": False,
}

LFIFAPI_EXCLUDE_URL = "https://exclude-ifapi.example.com"
W_VALUES_LFIFAPI_CONFIG_KW = {
    "capture_headers": True,
    "excluded_urls": [LFIFAPI_EXCLUDE_URL],
    "record_send_receive": True,
    "extra_spans": True,
}
W_VALUES_LFIFAPI_CONFIG_YAML = f"""\
capture_headers: true
excluded_urls:
    - "{LFIFAPI_EXCLUDE_URL}"
record_send_receive: true
extra_spans: true
"""
W_VALUES_LFIFAPI_CONFIG_EXP_KW = W_VALUES_LFIFAPI_CONFIG_KW


EMPTY_LOGFIRE_CONFIG_YAML = ""  # raises

#
#   Secret / environment for default 'logfire_config' (token-only)
#
TEST_LOGFIRE_TOKEN = "DEADBEEF"
TEST_LOGFIRE_SERVICE_NAME = "test-service-name"
TEST_LOGFIRE_SERVICE_VERSION = "test-service-version"
TEST_LOGFIRE_ENVIRONMENT = "test-environment"
TEST_LOGFIRE_CONFIG_DIR = "/path/to/logfire/config"
TEST_LOGFIRE_DATA_DIR = "/path/to/logfire/data"
TEST_LOGFIRE_MIN_LEVEL = "debug"
TEST_LOGFIRE_BASE_URL = "https://logfire.example.com"

TEST_LOGFIRE_IC_DEFAULT_SECRETS = {
    "secret:LOGFIRE_TOKEN": TEST_LOGFIRE_TOKEN,
}

TEST_LOGFIRE_IC_DEFAULT_ENV = {
    "LOGFIRE_SERVICE_NAME": TEST_LOGFIRE_SERVICE_NAME,
    "LOGFIRE_SERVICE_VERSION": TEST_LOGFIRE_SERVICE_VERSION,
    "LOGFIRE_ENVIRONMENT": TEST_LOGFIRE_ENVIRONMENT,
    "LOGFIRE_CONFIG_DIR": TEST_LOGFIRE_CONFIG_DIR,
    "LOGFIRE_DATA_DIR": TEST_LOGFIRE_DATA_DIR,
    "LOGFIRE_MIN_LEVEL": TEST_LOGFIRE_MIN_LEVEL,
}

W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_INIT_KW = {
    "send_to_logfire": False,
    "token": "secret:LOGFIRE_TOKEN",
}
W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_YAML = """\
send_to_logfire: false
token: "secret:LOGFIRE_TOKEN"
"""
W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "send_to_logfire": False,
    "token": TEST_LOGFIRE_TOKEN,
    "service_name": TEST_LOGFIRE_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_DATA_DIR,
    "min_level": TEST_LOGFIRE_MIN_LEVEL,
    "add_baggage_to_attributes": True,
}
W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_AS_YAML = {
    "send_to_logfire": False,
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
}

W_TOKEN_ONLY_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
}
W_TOKEN_ONLY_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
"""
W_TOKEN_ONLY_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_TOKEN,
    "service_name": TEST_LOGFIRE_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_DATA_DIR,
    "min_level": TEST_LOGFIRE_MIN_LEVEL,
    "add_baggage_to_attributes": True,
}
W_TOKEN_ONLY_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
}

#
#   Secret / environment for full 'logfire_config' (all scalars)
#
TEST_LOGFIRE_OTHER_TOKEN = "FACEDACE"
TEST_LOGFIRE_OTHER_SERVICE_NAME = "other-service-name"
TEST_LOGFIRE_OTHER_SERVICE_VERSION = "other-service-version"
TEST_LOGFIRE_OTHER_ENVIRONMENT = "other-environment"
TEST_LOGFIRE_OTHER_CONFIG_DIR = "/other/path/to/logfire/config"
TEST_LOGFIRE_OTHER_DATA_DIR = "/other/path/to/logfire/data"
TEST_LOGFIRE_OTHER_MIN_LEVEL = "other"
TEST_LOGFIRE_OTHER_BASE_URL = "https://logfire-other.example.com"

TEST_LOGFIRE_IC_OTHER_SECRETS = {
    "secret:LOGFIRE_TOKEN": TEST_LOGFIRE_OTHER_TOKEN,
}

TEST_LOGFIRE_IC_OTHER_ENV = {
    "LOGFIRE_SERVICE_NAME": TEST_LOGFIRE_OTHER_SERVICE_NAME,
    "LOGFIRE_SERVICE_VERSION": TEST_LOGFIRE_OTHER_SERVICE_VERSION,
    "LOGFIRE_ENVIRONMENT": TEST_LOGFIRE_OTHER_ENVIRONMENT,
    "LOGFIRE_CONFIG_DIR": TEST_LOGFIRE_OTHER_CONFIG_DIR,
    "LOGFIRE_DATA_DIR": TEST_LOGFIRE_OTHER_DATA_DIR,
    "LOGFIRE_MIN_LEVEL": TEST_LOGFIRE_OTHER_MIN_LEVEL,
    "LOGFIRE_BASE_URL": TEST_LOGFIRE_OTHER_BASE_URL,
}

W_SOME_SCALARS_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "NOT_ENVVAR_LOGFIRE_SERVICE_NAME",
    "service_version": "NOT_ENVVAR_LOGFIRE_SERVICE_VERSION",
    "environment": "NOT_ENVVAR_LOGFIRE_ENVIRONMENT",
}
W_SOME_SCALARS_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
service_name: "NOT_ENVVAR_LOGFIRE_SERVICE_NAME"
service_version: "NOT_ENVVAR_LOGFIRE_SERVICE_VERSION"
environment: "NOT_ENVVAR_LOGFIRE_ENVIRONMENT"
"""
W_SOME_SCALARS_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_OTHER_TOKEN,
    "service_name": "NOT_ENVVAR_LOGFIRE_SERVICE_NAME",
    "service_version": "NOT_ENVVAR_LOGFIRE_SERVICE_VERSION",
    "environment": "NOT_ENVVAR_LOGFIRE_ENVIRONMENT",
    "config_dir": TEST_LOGFIRE_OTHER_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_OTHER_DATA_DIR,
    "min_level": TEST_LOGFIRE_OTHER_MIN_LEVEL,
    "add_baggage_to_attributes": True,
}
W_SOME_SCALARS_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "NOT_ENVVAR_LOGFIRE_SERVICE_NAME",
    "service_version": "NOT_ENVVAR_LOGFIRE_SERVICE_VERSION",
    "environment": "NOT_ENVVAR_LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
}

W_SCALARS_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "inspect_arguments": False,
    "add_baggage_to_attributes": False,
    "distributed_tracing": True,
}
W_SCALARS_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
service_name: "env:LOGFIRE_SERVICE_NAME"
service_version: "env:LOGFIRE_SERVICE_VERSION"
environment: "env:LOGFIRE_ENVIRONMENT"
config_dir: "env:LOGFIRE_CONFIG_DIR"
data_dir: "env:LOGFIRE_DATA_DIR"
min_level: "env:LOGFIRE_MIN_LEVEL"
inspect_arguments: False
add_baggage_to_attributes: False
distributed_tracing: True
"""
W_SCALARS_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_OTHER_TOKEN,
    "service_name": TEST_LOGFIRE_OTHER_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_OTHER_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_OTHER_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_OTHER_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_OTHER_DATA_DIR,
    "min_level": TEST_LOGFIRE_OTHER_MIN_LEVEL,
    "inspect_arguments": False,
    "add_baggage_to_attributes": False,
    "distributed_tracing": True,
}
W_SCALARS_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "inspect_arguments": False,
    "add_baggage_to_attributes": False,
    "distributed_tracing": True,
}

W_BASE_URL_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "base_url": "env:LOGFIRE_BASE_URL",
}
W_BASE_URL_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
base_url: "env:LOGFIRE_BASE_URL"
"""
W_BASE_URL_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_OTHER_TOKEN,
    "service_name": TEST_LOGFIRE_OTHER_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_OTHER_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_OTHER_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_OTHER_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_OTHER_DATA_DIR,
    "min_level": TEST_LOGFIRE_OTHER_MIN_LEVEL,
    "add_baggage_to_attributes": True,
    "advanced": {
        "base_url": TEST_LOGFIRE_OTHER_BASE_URL,
    },
}
W_BASE_URL_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
    "base_url": "env:LOGFIRE_BASE_URL",
}

W_SCRUBBING_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "scrubbing_patterns": [".*"],
}
W_SCRUBBING_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
scrubbing_patterns:
    - ".*"
"""
W_SCRUBBING_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_TOKEN,
    "service_name": TEST_LOGFIRE_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_DATA_DIR,
    "min_level": TEST_LOGFIRE_MIN_LEVEL,
    "add_baggage_to_attributes": True,
    "scrubbing": {
        "extra_patterns": [
            ".*",
        ],
    },
}
W_SCRUBBING_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
    "scrubbing_patterns": [".*"],
}

W_IPYDAI_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "instrument_pydantic_ai": config.LogfireInstrumentPydanticAI(
        include_binary_content=False,
        include_content=False,
    ),
}
W_IPYDAI_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
instrument_pydantic_ai:
    include_binary_content: false
    include_content: false
"""
W_IPYDAI_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
    "instrument_pydantic_ai": {
        "include_binary_content": False,
        "include_content": False,
    },
}

W_IFAPI_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "instrument_fast_api": config.LogfireInstrumentFastAPI(
        capture_headers=True,
        excluded_urls=[LFIFAPI_EXCLUDE_URL],
        record_send_receive=True,
        extra_spans=True,
    ),
}
W_IFAPI_LOGFIRE_CONFIG_YAML = f"""\
token: "secret:LOGFIRE_TOKEN"
instrument_fast_api:
    capture_headers: true
    excluded_urls:
        - "{LFIFAPI_EXCLUDE_URL}"
    record_send_receive: true
    extra_spans: true
"""
W_IFAPI_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
    "instrument_fast_api": {
        "capture_headers": True,
        "excluded_urls": [LFIFAPI_EXCLUDE_URL],
        "record_send_receive": True,
        "extra_spans": True,
    },
}


SECRET_NAME = "TEST_SECRET"
SECRET_VALUE = "DEADBEEF"
ENV_VAR_NAME = "TEST_ENV_VAR"
COMMAND = "cat"

AGUI_FEATURE_DESCRIPTION = "This is an AG-UI feature"
AGUI_FEATURE_DESCRIPTION_EXTRA = "It is a really useful feature"
AGUI_FEATURE_MODEL_KLASS = "soliplex.agui.features.Testing"

BOGUS_ICMETA_YAML = """\
meta:
    tool_configs:
"""
BARE_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [],
    "secret_sources": [],
}
BARE_ICMETA_YAML = """\
meta:
"""

W_AGUI_FEATURES_ICMETA_KW = {
    "agui_features": [
        config.AGUI_FeatureConfigMeta(
            name=features.HAIKU_CHAT_FEATURE,
            model_klass=features.hr_chat_state.ChatSessionState,
            source="server",
        ),
    ],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [],
    "secret_sources": [],
}
W_AGUI_FEATURES_ICMETA_YAML = """\
meta:
  agui_features:
      - name: "haiku.rag.chat"
        model_klass: "haiku.rag.agents.chat.state.ChatSessionState"
        source: "server"
"""


W_MCP_TOOLSET_CONFIGS_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [
        config.ConfigMeta(config_klass=config.Stdio_MCP_ClientToolsetConfig),
    ],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [],
    "secret_sources": [],
}
W_MCP_TOOLSET_CONFIGS_ICMETA_YAML = """\
meta:
  mcp_toolset_configs:
    - "soliplex.config.Stdio_MCP_ClientToolsetConfig"
"""


W_AGENT_CONFIGS_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [
        config.ConfigMeta(config_klass=config.AgentConfig),
        config.ConfigMeta(config_klass=config.FactoryAgentConfig),
    ],
    "secret_sources": [],
}
W_AGENT_CONFIGS_ICMETA_YAML = """\
meta:
  agent_configs:
      - "soliplex.config.AgentConfig"
      - "soliplex.config.FactoryAgentConfig"
"""

SECRET_SOURCE_FUNC = lambda source: "SEEKRIT"  # noqa E731
W_SECRET_SOURCE_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [],
    "secret_sources": [
        config.ConfigMeta(
            config_klass=config.EnvVarSecretSource,
            registered_func=SECRET_SOURCE_FUNC,
        ),
    ],
}
W_SECRET_SOURCE_ICMETA_YAML = """\
meta:
  secret_sources:
    - "config_klass": "soliplex.config.EnvVarSecretSource"
      "registered_func": "soliplex.config.test_secret_func"
"""


FULL_ICMETA_KW = {
    "agui_features": [
        config.AGUI_FeatureConfigMeta(
            name=features.HAIKU_CHAT_FEATURE,
            model_klass=features.hr_chat_state.ChatSessionState,
            source="server",
        ),
    ],
    "tool_configs": [],
    "mcp_toolset_configs": [
        config.ConfigMeta(config_klass=config.Stdio_MCP_ClientToolsetConfig),
        config.ConfigMeta(config_klass=config.HTTP_MCP_ClientToolsetConfig),
    ],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [
        config.ConfigMeta(config_klass=config.AgentConfig),
        config.ConfigMeta(config_klass=config.FactoryAgentConfig),
    ],
    "secret_sources": [
        config.ConfigMeta(
            config_klass=config.EnvVarSecretSource,
            registered_func=SECRET_SOURCE_FUNC,
        ),
    ],
}
FULL_ICMETA_YAML = """\
meta:
  agui_features:
      - name: "haiku.rag.chat"
        model_klass: "haiku.rag.agents.chat.state.ChatSessionState"
        source: "server"
  mcp_toolset_configs:
      - "soliplex.config.Stdio_MCP_ClientToolsetConfig"
      - "soliplex.config.HTTP_MCP_ClientToolsetConfig"
  agent_configs:
      - "soliplex.config.AgentConfig"
      - "soliplex.config.FactoryAgentConfig"
  secret_sources:
    - "config_klass": "soliplex.config.EnvVarSecretSource"
      "registered_func": "soliplex.config.test_secret_func"
"""

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
    "meta": copy.deepcopy(BARE_ICMETA_KW),
}
W_BARE_META_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
meta:
"""

W_FULL_META_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "meta": FULL_ICMETA_KW,
}
W_FULL_META_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
{FULL_ICMETA_YAML}
"""

SECRET_NAME_1 = "TEST_SECRET_ONE"
SECRET_NAME_2 = "TEST_SECRET_TWO"
DB_SECRET_NAME = "DBSECRET"
DB_SECRET_VALUE = "R34ll7#S33KR1T"

SECRET_CONFIG_1 = config.SecretConfig(secret_name=SECRET_NAME_1)
SECRET_CONFIG_2 = config.SecretConfig(secret_name=SECRET_NAME_2)
DB_SECRET_CONFIG = config.SecretConfig(
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
        config.SecretConfig(secret_name=SECRET_NAME_1),
        config.SecretConfig(
            secret_name=SECRET_NAME_2,
            sources=[
                config.EnvVarSecretSource(
                    secret_name=SECRET_NAME_2,
                    env_var_name=SECRET_ENV_VAR,
                ),
                config.FilePathSecretSource(
                    secret_name=SECRET_NAME_2,
                    file_path=SECRET_FILE_PATH,
                ),
                config.SubprocessSecretSource(
                    secret_name=SECRET_NAME_2,
                    command=SECRET_COMAND,
                    args=SECRET_ARGS,
                ),
                config.RandomCharsSecretSource(
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
        config.AgentConfig(
            id=AGENT_CONFIG_ID,
            model_name=MODEL_NAME,
            system_prompt=SYSTEM_PROMPT,
        ),
    ],
}
W_AGENT_CONFIG_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
agent_configs:
    - id: "{AGENT_CONFIG_ID}"
      model_name: "{MODEL_NAME}"
      system_prompt: "{SYSTEM_PROMPT}"
"""

W_FACTORY_AGENT_CONFIG_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "meta": {
        "agent_configs": [
            config.ConfigMeta(config_klass=config.FactoryAgentConfig),
        ],
    },
    "agent_configs": [
        config.FactoryAgentConfig(
            id=AGENT_CONFIG_ID,
            factory_name="soliplex.haiku_chat.chat_agent_factory",
        ),
    ],
}
W_FACTORY_AGENT_CONFIG_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
meta:
    agent_configs:
        - "soliplex.config.FactoryAgentConfig"
agent_configs:
    - id: "{AGENT_CONFIG_ID}"
      kind: "factory"
      factory_name: "soliplex.haiku_chat.chat_agent_factory"
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

SKILL_NAME = "test-skill"
SKILL_DESC = "Skill description"
SKILL_LICENSE = "Skill license"
SKILL_COMPAT = "Skill compatibility"
SKILL_ALLOWED_TOOLS = "Skill allowed tools"
SKILL_AUTHOR = "phreddy@example.com"
SKILL_VERSION = "0.0.1"
SKILL_METADATA = {
    "author": SKILL_AUTHOR,
    "version": SKILL_VERSION,
}
SKILLS_PATH_1 = "./skills"
SKILLS_PATH_2 = "/path/to/other/skills"

W_SKILLS_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "skills_paths": [
        SKILLS_PATH_1,
        SKILLS_PATH_2,
    ],
}
W_SKILLS_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
skills_paths:
    - "{SKILLS_PATH_1}"
    - "{SKILLS_PATH_2}"
"""

W_SKILLS_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "skills_paths": [],
}
W_SKILLS_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
skills_paths:
    -
"""

W_LOGFIRE_CONFIG_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "logfire_config": config.LogfireConfig(token=TEST_LOGFIRE_TOKEN),
}
W_LOGFIRE_CONFIG_INSTALLATION_CONFIG_YAML = f"""
id: "{INSTALLATION_ID}"
logfire_config:
    token: "{TEST_LOGFIRE_TOKEN}"
"""

TP_DBURI_SYNC = "sqlite+pysqlite:////tmp/tp_testing.sqlite"
TP_DBURI_SYNC_W_SECRET = (
    f"sqlite+pysqlcipher://secret:{DB_SECRET_NAME}//tmp/tp_testing.sqlite"
)
TP_DBURI_SYNC_W_SECRET_RESOLVED = (
    f"sqlite+pysqlcipher://{DB_SECRET_VALUE}//tmp/tp_testing.sqlite"
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
    "_thread_persistence_dburi_sync": TP_DBURI_SYNC_W_SECRET,
    # aiosqlite doesn't support secrets
    "_thread_persistence_dburi_async": TP_DBURI_ASYNC,
}
W_TP_DBURI_W_SECRET_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
thread_persistence_dburi:
    sync: {TP_DBURI_SYNC_W_SECRET}
    async: {TP_DBURI_ASYNC}
"""

RA_DBURI_SYNC = "sqlite+pysqlite:////tmp/ra_testing.sqlite"
RA_DBURI_SYNC_W_SECRET = (
    f"sqlite+pysqlcipher://secret:{DB_SECRET_NAME}//tmp/ra_testing.sqlite"
)
RA_DBURI_SYNC_W_SECRET_RESOLVED = (
    f"sqlite+pysqlcipher://{DB_SECRET_VALUE}//tmp/ra_testing.sqlite"
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
    "_authorization_dburi_sync": RA_DBURI_SYNC_W_SECRET,
    # aiosqlite doesn't support secrets
    "_authorization_dburi_async": RA_DBURI_ASYNC,
}
W_RA_DBURI_W_SECRET_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
authorization_dburi:
    sync: {RA_DBURI_SYNC_W_SECRET}
    async: {RA_DBURI_ASYNC}
"""


@pytest.fixture
def installation_config():
    return mock.create_autospec(config.InstallationConfig)


def test_authsystem_from_yaml_w_error(
    installation_config,
    temp_dir,
):
    config_path = temp_dir / "config.yaml"
    config_path.write_text(W_ERROR_AUTHSYSTM_CONFIG_YAML)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    with pytest.raises(config.FromYamlException) as exc_info:
        config.OIDCAuthSystemConfig.from_yaml(
            installation_config,
            config_path,
            config_dict,
        )

    assert exc_info.value._config_path == config_path


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (BARE_AUTHSYSTEM_CONFIG_YAML, BARE_AUTHSYSTEM_CONFIG_KW.copy()),
        (W_SCOPE_AUTHSYSTEM_CONFIG_YAML, W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy()),
        (W_PEM_AUTHSYSTEM_CONFIG_YAML, W_PEM_AUTHSYSTEM_CONFIG_KW.copy()),
    ],
)
def test_authsystem_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
):
    expected = config.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        **exp_config,
    )

    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    oidc_client_pem_path = exp_config.get("oidc_client_pem_path")

    if oidc_client_pem_path is not None:
        expected = dataclasses.replace(
            expected,
            oidc_client_pem_path=pathlib.Path(oidc_client_pem_path),
        )

    expected._config_path = config_path

    found = config.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_path,
        config_dict,
    )

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, exp_config, exp_secret",
    [
        (
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_YAML,
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW,
            AUTHSYSTEM_CLIENT_SECRET_LIT,
        ),
        (
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_YAML,
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW,
            AUTHSYSTEM_CLIENT_SECRET_SECRET,
        ),
    ],
)
def test_authsystem_from_yaml_w_client_secret(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
    exp_secret,
):
    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    expected = config.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        _config_path=config_path,
        **exp_config,
    )
    expected.client_secret = exp_secret

    found = config.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_path,
        config_dict,
    )

    assert found == expected


@pytest.mark.parametrize(
    "exp_config, exp_path",
    [
        (W_OIDC_CPP_REL_KW, "{temp_dir}/{rel_name}"),
        (
            W_OIDC_CPP_ABS_KW,
            AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS,
        ),
    ],
)
def test_authsystem_from_yaml_w_oid_cpp(
    installation_config,
    temp_dir,
    exp_config,
    exp_path,
):
    expected = config.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        **exp_config,
    )
    config_path = expected._config_path = temp_dir / "config.yaml"

    if exp_path.startswith("{"):
        kwargs = {
            "temp_dir": temp_dir,
            "rel_name": AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL_NAME,
        }
        exp_path = exp_path.format(**kwargs)

    expected.oidc_client_pem_path = pathlib.Path(exp_path)

    found = config.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_path,
        exp_config,
    )

    assert found == expected


def test_authsystem_server_metadata_url():
    inst = config.OIDCAuthSystemConfig(**BARE_AUTHSYSTEM_CONFIG_KW)

    assert inst.server_metadata_url == (
        f"{AUTHSYSTEM_SERVER_URL}/{config.WELL_KNOWN_OPENID_CONFIGURATION}"
    )


@pytest.mark.parametrize(
    "w_config, exp_client_kwargs, exp_secret, bare_secret",
    [
        (BARE_AUTHSYSTEM_CONFIG_KW.copy(), {}, "", True),
        (
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW,
            {},
            AUTHSYSTEM_CLIENT_SECRET_LIT,
            True,
        ),
        (
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW,
            {},
            AUTHSYSTEM_CLIENT_SECRET_SECRET,
            False,
        ),
        (W_SCOPE_AUTHSYSTEM_CONFIG_KW, {"scope": AUTHSYSTEM_SCOPE}, "", True),
        (
            W_OIDC_CPP_ABS_KW,
            {"verify": AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS},
            "",
            True,
        ),
    ],
)
def test_authsystem_oauth_client_args(
    installation_config,
    temp_dir,
    w_config,
    exp_client_kwargs,
    exp_secret,
    bare_secret,
):
    inst = config.OIDCAuthSystemConfig(
        **w_config,
    )
    inst._installation_config = installation_config
    exp_url = (
        f"{AUTHSYSTEM_SERVER_URL}/{config.WELL_KNOWN_OPENID_CONFIGURATION}"
    )

    icgs = installation_config.get_secret

    if bare_secret:
        icgs.side_effect = ValueError("testing")

    found = inst.oauth_client_kwargs

    assert found["name"] == AUTHSYSTEM_ID
    assert found["server_metadata_url"] == exp_url
    assert found["client_id"] == AUTHSYSTEM_CLIENT_ID
    if "verify" in found["client_kwargs"]:
        exp_client_kwargs.pop("verify")
        actual_verify = found["client_kwargs"].pop("verify")
        assert actual_verify.__class__ is ssl.SSLContext
    assert found["client_kwargs"] == exp_client_kwargs

    if bare_secret:
        assert found["client_secret"] == exp_secret
    else:
        assert found["client_secret"] is icgs.return_value

    icgs.assert_called_once_with(exp_secret)


def test_toolconfig_from_yaml_w_error(temp_dir):
    tool_name = "soliplex.tools.test_tool"
    config_path = temp_dir / "thing_config.yaml"

    with pytest.raises(config.FromYamlException) as exc_info:
        config.ToolConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict={
                "tool_name": tool_name,
                "allow_mcp": True,
                "nonesuch": "BOGUS",
            },
        )

    assert exc_info.value._config_path == config_path


@pytest.mark.parametrize(
    "w_feature_names, exp_feature_names",
    [
        (None, ()),
        (["foo"], ("foo",)),
    ],
)
def test_toolconfig_from_yaml(
    installation_config,
    temp_dir,
    w_feature_names,
    exp_feature_names,
):
    tool_name = "soliplex.tools.test_tool"
    config_path = temp_dir / "thing_config.yaml"

    expected = config.ToolConfig(
        _installation_config=installation_config,
        _config_path=config_path,
        tool_name=tool_name,
        allow_mcp=True,
        agui_feature_names=exp_feature_names,
    )

    config_dict = {
        "tool_name": tool_name,
        "allow_mcp": True,
    }

    if w_feature_names is not None:
        config_dict["agui_feature_names"] = w_feature_names

    tool_config = config.ToolConfig.from_yaml(
        installation_config=installation_config,
        config_path=config_path,
        config_dict=config_dict,
    )

    assert tool_config == expected


def test_toolconfig_kind():
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    assert tool_config.kind == "test_tool"


def test_toolconfig_tool_id():
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    assert tool_config.tool_id == "test_tool"


@pytest.mark.parametrize("w_existing", [False, True])
def test_toolconfig_tool(w_existing):
    def existing():  # pragma: NO COVER
        pass

    def test_tool(ctx, tool_config=None):
        "This is a test"

    if w_existing:
        tool_config = config.ToolConfig(
            tool_name="no.such.animal.exists",
        )
        tool_config._tool = existing
    else:
        tool_config = config.ToolConfig(
            tool_name="soliplex.tools.test_tool",
        )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        found = tool_config.tool

    if w_existing:
        assert found is existing

    else:
        assert found is test_tool


def TEST_TOOL_W_CTX_WO_PARAM_WO_TC(
    ctx,
) -> str:
    "This is a test"


def TEST_TOOL_W_CTX_W_PARAM_WO_TC(
    ctx,
    query: str,
) -> str:
    "This is a test"


def TEST_TOOL_W_CTX_WO_PARAM_W_TC(
    ctx,
    tool_config: config.ToolConfig,
) -> str:
    "This is a test"


def TEST_TOOL_W_CTX_W_PARAM_W_TC(
    ctx,
    query: str,
    tool_config: config.ToolConfig,
) -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_WO_PARAM_WO_TC() -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_W_PARAM_WO_TC(
    query: str,
) -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_WO_PARAM_W_TC(
    tool_config: config.ToolConfig,
) -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_W_PARAM_W_TC(
    query: str,
    tool_config: config.ToolConfig,
) -> str:
    "This is a test"


@pytest.mark.parametrize(
    "test_tool",
    [
        TEST_TOOL_W_CTX_WO_PARAM_W_TC,
        TEST_TOOL_W_CTX_W_PARAM_W_TC,
    ],
)
def test_toolconfig_tool_requires_w_conflict(test_tool):
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        with pytest.raises(config.ToolRequirementConflict):
            _ = tool_config.tool_requires


@pytest.mark.parametrize(
    "test_tool",
    [
        TEST_TOOL_W_CTX_WO_PARAM_WO_TC,
        TEST_TOOL_W_CTX_W_PARAM_WO_TC,
        TEST_TOOL_WO_CTX_WO_PARAM_WO_TC,
        TEST_TOOL_WO_CTX_W_PARAM_WO_TC,
        TEST_TOOL_WO_CTX_WO_PARAM_W_TC,
        TEST_TOOL_WO_CTX_W_PARAM_W_TC,
    ],
)
def test_toolconfig_tool_description(test_tool):
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        found = tool_config.tool_description

    assert found == test_tool.__doc__.strip()


@pytest.mark.parametrize(
    "test_tool, expected",
    [
        (TEST_TOOL_W_CTX_WO_PARAM_WO_TC, config.ToolRequires.FASTAPI_CONTEXT),
        (TEST_TOOL_W_CTX_W_PARAM_WO_TC, config.ToolRequires.FASTAPI_CONTEXT),
        (TEST_TOOL_WO_CTX_WO_PARAM_WO_TC, config.ToolRequires.BARE),
        (TEST_TOOL_WO_CTX_W_PARAM_WO_TC, config.ToolRequires.BARE),
        (TEST_TOOL_WO_CTX_WO_PARAM_W_TC, config.ToolRequires.TOOL_CONFIG),
        (TEST_TOOL_WO_CTX_W_PARAM_W_TC, config.ToolRequires.TOOL_CONFIG),
    ],
)
def test_toolconfig_tool_requires(test_tool, expected):
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        found = tool_config.tool_requires

    assert found == expected


@pytest.mark.parametrize(
    "test_tool, exp_wrapped",
    [
        (TEST_TOOL_W_CTX_WO_PARAM_WO_TC, False),
        (TEST_TOOL_W_CTX_W_PARAM_WO_TC, False),
        (TEST_TOOL_WO_CTX_WO_PARAM_WO_TC, False),
        (TEST_TOOL_WO_CTX_W_PARAM_WO_TC, False),
        (TEST_TOOL_WO_CTX_WO_PARAM_W_TC, True),
        (TEST_TOOL_WO_CTX_W_PARAM_W_TC, True),
    ],
)
def test_toolconfig_tool_with_config(test_tool, exp_wrapped):
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        found = tool_config.tool_with_config

    if exp_wrapped:
        assert isinstance(found, functools.partial)
        assert found.func is test_tool
        assert found.keywords == {"tool_config": tool_config}
        assert found.__name__ == test_tool.__name__
        assert found.__doc__ == test_tool.__doc__

        exp_signature = inspect.signature(test_tool)
        for param in found.__signature__.parameters:
            assert param in exp_signature.parameters

    else:
        assert found is test_tool


def test_toolconfig_get_extra_parameters():
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    assert tool_config.get_extra_parameters() == {}


rdb_exactly_one = pytest.raises(config.RagDbExactlyOneOfStemOrOverride)
rdb_not_found = pytest.raises(config.RagDbFileNotFound)
ok_stem = contextlib.nullcontext("stem")
ok_ovr = contextlib.nullcontext("override")


@pytest.mark.parametrize(
    "w_config_path, stem, override, ctor_expectation, rlp_expectation",
    [
        (False, None, None, rdb_exactly_one, None),
        (False, "testing", "/dev/null", rdb_exactly_one, None),
        (False, "testing", None, ok_stem, ok_stem),
        (False, None, "./override", ok_ovr, rdb_not_found),
        (True, None, "./override", ok_ovr, ok_ovr),
    ],
)
def test__rcb_ctor(
    installation_config,
    temp_dir,
    w_config_path,
    stem,
    override,
    ctor_expectation,
    rlp_expectation,
):
    db_rag_path = temp_dir / "db" / "rag"
    db_rag_path.mkdir(parents=True)

    if stem is not None:
        from_stem = db_rag_path / f"{stem}.lancedb"
        from_stem.mkdir()

    if override is not None:
        from_override = temp_dir / "rooms" / "test" / override
        if not from_override.exists():
            from_override.mkdir(parents=True)

    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_path)}
    installation_config.get_environment = ic_environ.get

    kw = {"_installation_config": installation_config}

    if w_config_path:
        exp_config_path = kw["_config_path"] = (
            temp_dir / "rooms" / "test" / "room_config.yaml"
        )
    else:
        exp_config_path = None

    if stem is not None:
        kw["rag_lancedb_stem"] = stem

    if override is not None:
        kw["rag_lancedb_override_path"] = override

    with ctor_expectation as which:
        rcb_config = config._RAGConfigBase(**kw)

    if isinstance(which, str):
        if which == "stem":
            expected = from_stem
        else:
            expected = from_override

        assert rcb_config._config_path == exp_config_path

        with rlp_expectation as which:
            found = rcb_config.rag_lancedb_path

        if isinstance(which, str):
            assert found.resolve() == expected.resolve()

            expected_ep = {
                "rag_lancedb_path": expected.resolve(),
            }

            assert rcb_config.get_extra_parameters() == expected_ep


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (BOGUS_STDIO_MCTC_CONFIG_YAML, None),
        (BARE_STDIO_MCTC_CONFIG_YAML, BARE_STDIO_MCTC_CONFIG_KW),
        (FULL_STDIO_MCTC_CONFIG_YAML, FULL_STDIO_MCTC_CONFIG_KW),
    ],
)
def test_stdio_mctc_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
):
    config_dir = temp_dir / "rooms" / "test_room"
    config_dir.mkdir(parents=True)

    config_path = config_dir / "room_config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    if exp_config is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.Stdio_MCP_ClientToolsetConfig.from_yaml(
                installation_config=installation_config,
                config_path=config_path,
                config_dict=config_dict,
            )

        assert exc.value._config_path == config_path

    else:
        stdio_mctc = config.Stdio_MCP_ClientToolsetConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )
        expected = config.Stdio_MCP_ClientToolsetConfig(
            _installation_config=installation_config,
            _config_path=config_path,
            **exp_config,
        )
        assert stdio_mctc == expected


@pytest.mark.parametrize("w_env", [{}, {"foo": "bar"}])
def test_stdio_mctc_toolset_params(w_env):
    stdio_mctc = config.Stdio_MCP_ClientToolsetConfig(
        command="cat",
        args=["-"],
        env=w_env,
    )

    found = stdio_mctc.toolset_params

    assert found["command"] == stdio_mctc.command
    assert found["args"] == stdio_mctc.args
    assert found["env"] == stdio_mctc.env
    assert found["allowed_tools"] == stdio_mctc.allowed_tools


@pytest.mark.parametrize("w_env", [{}, {"FOO_KEY": "secret:FOO_KEY"}])
def test_stdio_mctc_tool_kwargs(installation_config, w_env):
    stdio_mctc = config.Stdio_MCP_ClientToolsetConfig(
        command="cat",
        args=["-"],
        env=w_env,
        _installation_config=installation_config,
    )

    found = stdio_mctc.tool_kwargs

    assert found["command"] == stdio_mctc.command
    assert found["args"] == stdio_mctc.args
    assert found["allowed_tools"] == stdio_mctc.allowed_tools

    for (f_key, f_val), (cfg_key, cfg_value) in zip(
        found["env"].items(),
        w_env.items(),
        strict=True,
    ):
        assert f_key == cfg_key
        assert f_val is installation_config.get_secret.return_value
        assert (
            mock.call(cfg_value)
            in installation_config.get_secret.call_args_list
        )


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (BOGUS_HTTP_MCTC_CONFIG_YAML, None),
        (BARE_HTTP_MCTC_CONFIG_YAML, BARE_HTTP_MCTC_CONFIG_KW),
        (FULL_HTTP_MCTC_CONFIG_YAML, FULL_HTTP_MCTC_CONFIG_KW),
    ],
)
def test_http_mctc_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
):
    config_dir = temp_dir / "rooms" / "test_room"
    config_dir.mkdir(parents=True)

    config_path = config_dir / "room_config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    if exp_config is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.HTTP_MCP_ClientToolsetConfig.from_yaml(
                installation_config=installation_config,
                config_path=config_path,
                config_dict=config_dict,
            )

        assert exc.value._config_path == config_path

    else:
        http_mctc = config.HTTP_MCP_ClientToolsetConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )
        expected = config.HTTP_MCP_ClientToolsetConfig(
            _installation_config=installation_config,
            _config_path=config_path,
            **exp_config,
        )
        assert http_mctc == expected


@pytest.mark.parametrize("w_headers", [{}, HTTP_MCP_AUTH_HEADER])
@pytest.mark.parametrize("w_query_params", [{}, HTTP_MCP_QUERY_PARAMS])
def test_http_mctc_toolset_params(w_query_params, w_headers):
    http_mctc = config.HTTP_MCP_ClientToolsetConfig(
        url=HTTP_MCP_URL,
        headers=w_headers,
        query_params=w_query_params,
    )

    found = http_mctc.toolset_params

    assert found["url"] == http_mctc.url
    assert found["query_params"] == http_mctc.query_params
    assert found["headers"] == http_mctc.headers
    assert found["allowed_tools"] == http_mctc.allowed_tools


@pytest.mark.parametrize("w_headers", [{}, HTTP_MCP_AUTH_HEADER])
@pytest.mark.parametrize("w_query_params", [{}, HTTP_MCP_QUERY_PARAMS])
def test_http_mctc_tool_kwargs(
    installation_config,
    w_query_params,
    w_headers,
):
    installation_config.get_secret.return_value = "<secret>"
    installation_config.interpolate_secrets.return_value = "<interp>"

    http_mctc = config.HTTP_MCP_ClientToolsetConfig(
        url=HTTP_MCP_URL,
        headers=w_headers,
        query_params=w_query_params,
        _installation_config=installation_config,
    )

    found = http_mctc.tool_kwargs

    assert found["allowed_tools"] == http_mctc.allowed_tools

    if w_query_params:
        base, qs = found["url"].split("?")
        assert base == http_mctc.url

        qp_dict = dict(url_parse.parse_qsl(qs))

        for (f_key, f_val), (cfg_key, cfg_value) in zip(
            qp_dict.items(),
            w_query_params.items(),
            strict=True,
        ):
            assert f_key == cfg_key
            assert f_val == installation_config.get_secret.return_value
            assert (
                mock.call(cfg_value)
                in installation_config.get_secret.call_args_list
            )

    else:
        assert found["url"] == http_mctc.url

    for (f_key, f_val), (cfg_key, cfg_value) in zip(
        found["headers"].items(),
        w_headers.items(),
        strict=True,
    ):
        assert f_key == cfg_key
        assert f_val is installation_config.interpolate_secrets.return_value
        assert (
            mock.call(cfg_value)
            in installation_config.interpolate_secrets.call_args_list
        )


def test_noargsmcpwrapper_call():
    func = mock.Mock(spec_set=())
    tool_config = mock.create_autospec(config.ToolConfig)

    wrapper = config.NoArgsMCPWrapper(func=func, tool_config=tool_config)

    found = wrapper()

    assert found is func.return_value
    func.assert_called_once_with(tool_config=tool_config)


def test_withquerymcpwrapper_call():
    func = mock.Mock(spec_set=())
    tool_config = mock.create_autospec(config.ToolConfig)

    wrapper = config.WithQueryMCPWrapper(func=func, tool_config=tool_config)

    found = wrapper(query="text")

    assert found is func.return_value
    func.assert_called_once_with("text", tool_config=tool_config)


@pytest.mark.parametrize(
    "config_dict, expected",
    [
        ({}, {}),
        ({"template_id": BOGUS_TEMPLATE_AGENT_ID}, None),
        ({"other": "OTHER"}, {"other": "OTHER"}),
        (
            {"template_id": TEMPLATE_AGENT_ID, "other": "OTHER"},
            {
                "other": "OTHER",
                "key": "from_template",
                "_template_id": TEMPLATE_AGENT_ID,
            },
        ),
        (
            {"template_id": TEMPLATE_AGENT_ID, "key": "from_local"},
            {"key": "from_local", "_template_id": TEMPLATE_AGENT_ID},
        ),
        (
            {
                "template_id": TEMPLATE_AGENT_ID,
                "key": "from_local",
                "other": "OTHER",
            },
            {
                "other": "OTHER",
                "key": "from_local",
                "_template_id": TEMPLATE_AGENT_ID,
            },
        ),
    ],
)
def test__apply_agent_config_template(temp_dir, config_dict, expected):
    template_ac = mock.Mock(spec_set=["id", "as_yaml"])
    template_ac.id = TEMPLATE_AGENT_ID
    template_ac.as_yaml = {"key": "from_template"}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs = [template_ac]
    config_path = temp_dir / "test.yaml"

    if expected is None:
        with pytest.raises(config.InvalidAgentTemplateID):
            config._apply_agent_config_template(
                config_dict,
                i_config,
                config_path,
            )

    else:
        found = config._apply_agent_config_template(
            config_dict,
            i_config,
            config_path,
        )

        assert found == expected


@pytest.mark.parametrize(
    "kw",
    [
        BARE_AGENT_CONFIG_KW.copy(),
    ],
)
def test_agentconfig_ctor(installation_config, kw):
    kw["_installation_config"] = installation_config

    found = config.AgentConfig(**kw)

    assert found.model_name == kw["model_name"]


@pytest.mark.parametrize(
    "config_yaml, expectation",
    [
        (
            BOGUS_AGENT_CONFIG_YAML,
            pytest.raises(config.FromYamlException),
        ),
        (
            BARE_AGENT_CONFIG_YAML,
            contextlib.nullcontext(BARE_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_PROVIDER_KW_AGENT_CONFIG_YAML,
            contextlib.nullcontext(W_PROVIDER_KW_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_RETRIES_AGENT_CONFIG_YAML,
            contextlib.nullcontext(W_RETRIES_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_MODEL_SETTINGS_AGENT_CONFIG_YAML,
            contextlib.nullcontext(W_MODEL_SETTINGS_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_PROMPT_FILE_AGENT_CONFIG_YAML,
            contextlib.nullcontext(W_PROMPT_FILE_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_PROMPT_FILE_W_TEMPLATE_ID_AGENT_CONFIG_YAML,
            contextlib.nullcontext(
                W_PROMPT_FILE_W_TEMPLATE_ID_AGENT_CONFIG_KW.copy()
            ),
        ),
        (
            W_PROMPT_FILE_W_BOGUS_TEMPLATE_ID_AGENT_CONFIG_YAML,
            pytest.raises(config.FromYamlException),
        ),
        (
            W_AGUI_FEATURE_NAMES_AGENT_CONFIG_YAML,
            contextlib.nullcontext(
                W_AGUI_FEATURE_NAMES_AGENT_CONFIG_KW.copy()
            ),
        ),
    ],
)
def test_agentconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expectation,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if config_dict is not None:
        template_id = config_dict.get("template_id")
    else:
        template_id = None

    if template_id not in (None, BOGUS_TEMPLATE_AGENT_ID):
        template_kw = {
            "model_name": OTHER_MODEL_NAME,
            "provider_base_url": OTHER_PROVIDER_BASE_URL,
        }
        installation_config.agent_configs = [
            config.AgentConfig(id=template_id, **template_kw),
        ]
    else:
        template_kw = {}
        installation_config.agent_configs = []

    with expectation as expected:
        found = config.AgentConfig.from_yaml(
            installation_config,
            yaml_file,
            config_dict,
        )

    if isinstance(expected, dict):
        exp_agent_config = config.AgentConfig(
            _installation_config=installation_config,
            _config_path=yaml_file,
            **(template_kw | expected),
        )

        assert found == exp_agent_config

        # See #180.
        assert found._installation_config is installation_config


@pytest.mark.parametrize("w_config_path", [False, True])
@pytest.mark.parametrize(
    "agent_config_kw",
    [
        BARE_AGENT_CONFIG_KW.copy(),
        W_MODEL_SETTINGS_AGENT_CONFIG_KW.copy(),
        W_PROMPT_FILE_AGENT_CONFIG_KW.copy(),
    ],
)
def test_agentconfig_get_system_prompt(
    temp_dir,
    agent_config_kw,
    w_config_path,
):
    agent_config_kw = agent_config_kw.copy()

    if w_config_path:
        config_path = temp_dir / "prompt.txt"
        config_path.write_text(SYSTEM_PROMPT)

        agent_config_kw["_config_path"] = config_path

    agent_config = config.AgentConfig(**agent_config_kw)

    if agent_config._system_prompt_text is not None:
        found = agent_config.get_system_prompt()
        assert found == agent_config._system_prompt_text
        return

    if agent_config._config_path:
        if agent_config._system_prompt_path is not None:
            expected = SYSTEM_PROMPT
        else:
            expected = None

        assert agent_config.get_system_prompt() == expected

    else:
        if agent_config._system_prompt_path is not None:
            with pytest.raises(config.NoConfigPath):
                agent_config.get_system_prompt()

        else:
            assert agent_config.get_system_prompt() is None


@pytest.mark.parametrize(
    "provider_type, kw, expected",
    [
        (config.LLMProviderType.OLLAMA, {}, OLLAMA_BASE_URL),
        (
            config.LLMProviderType.OLLAMA,
            {"provider_base_url": PROVIDER_BASE_URL},
            PROVIDER_BASE_URL,
        ),
        (config.LLMProviderType.OPENAI, {}, None),
        (
            config.LLMProviderType.OPENAI,
            {"provider_base_url": PROVIDER_BASE_URL},
            PROVIDER_BASE_URL,
        ),
        (config.LLMProviderType.GOOGLE, {}, None),
    ],
)
def test_agentconfig_llm_provider_base_url(
    installation_config,
    provider_type,
    kw,
    expected,
):
    ic_environ = {"OLLAMA_BASE_URL": OLLAMA_BASE_URL}
    installation_config.get_environment = ic_environ.get

    aconfig = config.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=provider_type,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_base_url

    assert found == expected


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_ollama_w_default_base_url(
    installation_config,
    has_pk,
):
    ic_environ = {"OLLAMA_BASE_URL": OLLAMA_BASE_URL}
    installation_config.get_environment = ic_environ.get

    kw = {}
    expected = {
        "base_url": f"{OLLAMA_BASE_URL}/v1",
    }

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config.LLMProviderType.OLLAMA,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_ollama_w_explicit_base_url(
    installation_config,
    has_pk,
):
    kw = {}
    expected = {
        "base_url": f"{PROVIDER_BASE_URL}/v1",
    }

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config.LLMProviderType.OLLAMA,
        provider_base_url=PROVIDER_BASE_URL,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_openai_wo_provider_url(
    installation_config,
    has_pk,
):
    kw = {}
    expected = {}

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config.LLMProviderType.OPENAI,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_openai_w_provider_url(
    installation_config,
    has_pk,
):
    kw = {}
    expected = {
        "base_url": f"{PROVIDER_BASE_URL}/v1",
    }

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config.LLMProviderType.OPENAI,
        provider_base_url=PROVIDER_BASE_URL,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_google(
    installation_config,
    has_pk,
):
    kw = {}
    expected = {}

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config.LLMProviderType.GOOGLE,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize(
    "agent_config_kw",
    [
        BARE_AGENT_CONFIG_KW.copy(),
        W_PROVIDER_KW_AGENT_CONFIG_KW.copy(),
        W_RETRIES_AGENT_CONFIG_KW.copy(),
        W_PROMPT_FILE_AGENT_CONFIG_KW.copy(),
    ],
)
def test_agentconfig_as_yaml(
    installation_config,
    agent_config_kw,
):
    agent_config_kw = copy.deepcopy(agent_config_kw)

    ic_environ = {
        "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
    }
    installation_config.get_environment = ic_environ.get
    agent_config_kw["_installation_config"] = installation_config

    system_prompt = (
        agent_config_kw.get("system_prompt")
        or agent_config_kw.get("_system_prompt_text")
        or agent_config_kw.get("_system_prompt_path")
    )
    model_name = agent_config_kw.get("model_name") or MODEL_NAME
    model_settings = agent_config_kw.get("model_settings")
    expected = {
        "id": AGENT_ID,
        "system_prompt": system_prompt,
        "model_name": model_name,
        "model_settings": model_settings,
        "retries": agent_config_kw.get("retries", 3),
        "provider_type": agent_config_kw.get("provider_type", "ollama"),
    }

    expected["provider_base_url"] = agent_config_kw.get(
        "provider_base_url",
        OLLAMA_BASE_URL,
    )

    expected["provider_key"] = agent_config_kw.get("provider_key")

    aconfig = config.AgentConfig(**agent_config_kw)

    found = aconfig.as_yaml

    assert found == expected

    installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize(
    "kw",
    [
        WO_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        W_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
    ],
)
def test_factoryagentconfig_ctor(kw):
    found = config.FactoryAgentConfig(**kw)

    assert found.id == AGENT_ID
    assert found.factory_name == kw["factory_name"]
    assert found.with_agent_config == kw["with_agent_config"]
    assert found.extra_config == kw.get("extra_config", {})


@pytest.mark.parametrize("w_existing", [False, True])
@pytest.mark.parametrize(
    "kw",
    [
        WO_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        W_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
    ],
)
def test_factoryagentconfig_factory(kw, w_existing):
    def existing():  # pragma: NO COVER
        pass

    def test_factory(ctx, agent_config=None):
        "This is a test"

    pyagent_config = config.FactoryAgentConfig(**kw)

    if w_existing:
        pyagent_config._factory = existing

    _, factory_name = kw["factory_name"].rsplit(".", 1)
    patch = {factory_name: test_factory}

    with mock.patch.dict("soliplex.config.__dict__", **patch):
        found = pyagent_config.factory

    if w_existing:
        assert found is existing

    else:
        if kw["with_agent_config"]:
            assert isinstance(found, functools.partial)
            assert found.func is test_factory
            assert found.keywords == {"agent_config": pyagent_config}
            assert found.__name__ == test_factory.__name__
            assert found.__doc__ == test_factory.__doc__
        else:
            assert found is test_factory


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BOGUS_AGENT_CONFIG_YAML, None),
        (
            WO_CONFIG_FACTORY_AGENT_CONFIG_YAML,
            WO_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
        (
            W_CONFIG_FACTORY_AGENT_CONFIG_YAML,
            W_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
        (
            W_AGUI_FEATURE_NAMES_FACTORY_AGENT_CONFIG_YAML,
            W_AGUI_FEATURE_NAMES_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
        (W_BOGUS_TEMPLATE_ID_FACTORY_AGENT_CONFIG_YAML, None),
        (
            W_TEMPLATE_ID_FACTORY_AGENT_CONFIG_YAML,
            W_TEMPLATE_ID_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
        (
            W_TEMPLATE_ID_W_EXTRA_CONFIG_FACTORY_AGENT_CONFIG_YAML,
            W_TEMPLATE_ID_W_EXTRA_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
    ],
)
def test_factoryagentconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if config_dict is not None:
        template_id = config_dict.get("template_id")
    else:
        template_id = None

    if template_id not in (None, BOGUS_TEMPLATE_AGENT_ID):
        template_kw = {
            "factory_name": FACTORY_NAME,
            "with_agent_config": True,
        }
        installation_config.agent_configs = [
            config.FactoryAgentConfig(id=template_id, **template_kw),
        ]
    else:
        template_kw = {}
        installation_config.agent_configs = []

    if expected_kw is None:
        with pytest.raises(config.FromYamlException):
            config.FactoryAgentConfig.from_yaml(
                installation_config,
                yaml_file,
                config_dict,
            )
    else:
        expected = config.FactoryAgentConfig(
            _installation_config=installation_config,
            _config_path=yaml_file,
            **(template_kw | expected_kw),
        )

        found = config.FactoryAgentConfig.from_yaml(
            installation_config,
            yaml_file,
            config_dict,
        )

        assert found == expected

        # See #180.
        assert found._installation_config is installation_config


@pytest.mark.parametrize(
    "kw",
    [
        WO_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        W_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
    ],
)
def test_factoryagentconfig_as_yaml(
    installation_config,
    kw,
):
    kw = copy.deepcopy(kw)
    expected = copy.deepcopy(kw)

    if "extra_config" not in expected:
        expected["extra_config"] = {}

    aconfig = config.FactoryAgentConfig(**kw)

    found = aconfig.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "agent_config, expected_kw",
    [
        (BARE_AGENT_CONFIG_KW.copy(), BARE_AGENT_CONFIG_KW),
        (W_KIND_AGENT_CONFIG_KW.copy(), W_KIND_AGENT_CONFIG_KW),
    ],
)
def test_extract_agent_configs(
    installation_config,
    temp_dir,
    agent_config,
    expected_kw,
):
    @dataclasses.dataclass(kw_only=True)
    class TestAgentConfig:
        id: str
        model_name: str
        kind: typing.ClassVar[str] = "testing"
        _installation_config: config.InstallationConfig = None
        _config_path: pathlib.Path = None

        @classmethod
        def from_yaml(cls, i_config, c_path, c_dict):
            return cls(
                _installation_config=i_config,
                _config_path=c_path,
                **c_dict,
            )

    if agent_config.get("kind") == "testing":
        kw_no_kind = {k: v for k, v in expected_kw.items() if k != "kind"}
        expected = TestAgentConfig(
            _installation_config=installation_config,
            _config_path=temp_dir,
            **kw_no_kind,
        )
    else:
        expected = config.AgentConfig(
            _installation_config=installation_config,
            _config_path=temp_dir,
            **expected_kw,
        )

    # Register our extension agent config
    with mock.patch.dict(
        "soliplex.config.AGENT_CONFIG_CLASSES_BY_KIND",
        testing=TestAgentConfig,
    ):
        found = config.extract_agent_config(
            installation_config,
            temp_dir,
            agent_config,
        )

    assert found == expected


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
def populated_quiz(temp_dir, quiz_json):
    quizzes_path = temp_dir / "quizzes"
    quizzes_path.mkdir()
    populated_quiz = quizzes_path / f"{TEST_QUIZ_ID}.json"
    populated_quiz.write_text(json.dumps(quiz_json))
    return populated_quiz


def test_quizconfig_ctor_defaults():
    with pytest.raises(config.QCExactlyOneOfStemOrOverride):
        config.QuizConfig(id=TEST_QUIZ_ID)


def test_quizconfig_ctor_exclusive():
    with pytest.raises(config.QCExactlyOneOfStemOrOverride):
        config.QuizConfig(
            id=TEST_QUIZ_ID,
            _question_file_stem="question_file.json",
            _question_file_path_override="/path/to/question_file.json",
        )


@pytest.mark.parametrize(
    "qf, exp_stem, exp_ovr",
    [
        ("foo.json", "foo", None),
        ("bar", "bar", None),
        ("/path/to/foo.json", None, "/path/to/foo.json"),
    ],
)
def test_quizconfig_ctor_w_question_file(
    installation_config,
    temp_dir,
    qf,
    exp_stem,
    exp_ovr,
):
    qp_1 = temp_dir / "qp_1"
    qp_1.mkdir()

    qp_2 = temp_dir / "qp_2"
    qp_2.mkdir()

    if exp_stem == "foo":
        qf_in_qp2 = qp_2 / "foo.json"
        qf_in_qp2.write_text("{}")

    installation_config.quizzes_paths = [qp_1, qp_2]

    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file=qf,
        _installation_config=installation_config,
    )
    assert qc._question_file_stem == exp_stem
    assert qc._question_file_path_override == exp_ovr

    found = qc.question_file_path

    if exp_stem == "foo":
        assert found == qf_in_qp2
    elif exp_stem == "bar":
        assert found is None
    else:
        assert found == pathlib.Path(exp_ovr)


def test_quizconfig_from_yaml_exceptions(installation_config, temp_dir):
    config_kw = {
        "id": TEST_QUIZ_ID,
        "title": TEST_QUIZ_TITLE,
    }

    config_path = temp_dir / "test.yaml"

    with pytest.raises(config.FromYamlException) as exc:
        config.QuizConfig.from_yaml(
            installation_config,
            config_path,
            config_kw,
        )

    assert exc.value._config_path == config_path


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (TEST_QUIZ_W_STEM_YAML, TEST_QUIZ_W_STEM_KW),
        (TEST_QUIZ_W_OVR_YAML, TEST_QUIZ_W_OVR_KW),
    ],
)
def test_quizconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    jac = expected_kw.pop("judge_agent")

    if "provider_base_url" not in jac:
        jac["provider_base_url"] = (
            installation_config.get_environment.return_value
        )
    else:
        jac["_config_path"] = yaml_file
        jac["_installation_config"] = installation_config

    expected_kw["judge_agent"] = config.AgentConfig(**jac)

    expected = config.QuizConfig(**expected_kw)

    expected = dataclasses.replace(
        expected,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    found = config.QuizConfig.from_yaml(
        installation_config,
        yaml_file,
        config_dict,
    )

    assert found == expected


def test_quizconfig__load_questions_file_miss_w_stem(
    installation_config,
    temp_dir,
):
    installation_config.quizzes_paths = [temp_dir]
    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file="nonesuch",
        _installation_config=installation_config,
    )

    with pytest.raises(config.QuestionFileNotFoundWithStem):
        qc._load_questions_file()


def test_quizconfig__load_questions_file_miss_w_override(
    installation_config,
    temp_dir,
):
    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file=str(temp_dir / "nonesuch.json"),
        _installation_config=installation_config,
    )

    with pytest.raises(config.QuestionFileNotFoundWithOverride):
        qc._load_questions_file()


def test_quizconfig__load_questions_file(temp_dir, populated_quiz, quiz_json):
    expected_questions = quiz_json["cases"]

    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file=str(populated_quiz),
    )

    found = qc.get_questions()

    for f_question, e_question in zip(
        found,
        expected_questions,
        strict=True,
    ):
        assert f_question.inputs == e_question["inputs"]
        assert f_question.expected_output == e_question["expected_output"]
        assert f_question.metadata.type == e_question["metadata"]["type"]
        assert f_question.metadata.uuid == e_question["metadata"]["uuid"]
        options = e_question["metadata"].get("options")
        assert f_question.metadata.options == options


@pytest.mark.parametrize("w_max_questions", [None, 1])
@pytest.mark.parametrize("w_loaded", [False, True])
def test_quizconfig_get_questions(quiz_questions, w_loaded, w_max_questions):
    expected_questions = quiz_questions

    kwargs = {"id": TEST_QUIZ_ID, "question_file": "ignored.json"}

    if w_max_questions is not None:
        kwargs["max_questions"] = w_max_questions
        expected_questions = expected_questions[:w_max_questions]

    q_map = {
        question.metadata.uuid: question for question in expected_questions
    }

    qc = config.QuizConfig(**kwargs)

    if w_loaded:
        qc._questions_map = q_map
    else:
        qc._load_questions_file = mock.Mock(spec_set=(), return_value=q_map)

    found = qc.get_questions()

    assert found == list(q_map.values())


@mock.patch("random.shuffle")
def test_quizconfig_get_questions_w_randomize(
    shuffle,
    temp_dir,
    populated_quiz,
    quiz_json,
):
    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file=str(populated_quiz),
        randomize=True,
    )

    found = qc.get_questions()

    shuffle.assert_called_once_with(found)


@pytest.mark.parametrize("w_miss", [False, True])
@pytest.mark.parametrize("w_loaded", [False, True])
def test_quizconfig_get_question(w_loaded, w_miss):
    UUID = "DEADBEEF"
    expected = object()

    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file="ignored.json",
    )
    q_map = {}

    if w_loaded:
        qc._questions_map = q_map
    else:
        qc._load_questions_file = mock.Mock(spec_set=(), return_value=q_map)

    if w_miss:
        with pytest.raises(KeyError):
            qc.get_question(UUID)

    else:
        q_map[UUID] = expected

        found = qc.get_question(UUID)

        assert found is expected


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BOGUS_ROOM_CONFIG_YAML, None),
        (BARE_ROOM_CONFIG_YAML, BARE_ROOM_CONFIG_KW),
        (FULL_ROOM_CONFIG_YAML, FULL_ROOM_CONFIG_KW),
    ],
)
def test_roomconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if expected_kw is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.RoomConfig.from_yaml(
                installation_config,
                yaml_file,
                {},
            )
        assert exc.value._config_path == yaml_file

    else:
        expected = config.RoomConfig(**expected_kw)
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

        if len(expected_kw.get("tool_configs", {})) > 0:
            for tool_config in expected_kw["tool_configs"].values():
                tool_config._installation_config = installation_config
                tool_config._config_path = yaml_file

        if len(expected_kw.get("mcp_client_toolset_configs", {})) > 0:
            for mcts_config in expected_kw[
                "mcp_client_toolset_configs"
            ].values():
                mcts_config._installation_config = installation_config
                mcts_config._config_path = yaml_file

        if "quizzes" in config_yaml:
            expected.quizzes = [
                dataclasses.replace(
                    qc,
                    _installation_config=installation_config,
                    _config_path=yaml_file,
                )
                for qc in expected.quizzes
            ]

        found = config.RoomConfig.from_yaml(
            installation_config,
            yaml_file,
            config_dict,
        )

        assert found == expected


@pytest.mark.parametrize("w_existing", [False, True])
def test_roomconfig_quiz_map(w_existing):
    NUM_QUIZZES = 3
    quizzes = [
        mock.create_autospec(
            config.QuizConfig,
            id=f"quiz-{iq}",
            question_file=f"ignored-{iq}.json",
        )
        for iq in range(NUM_QUIZZES)
    ]

    existing = object()
    room_config = config.RoomConfig(**BARE_ROOM_CONFIG_KW)

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


@pytest.mark.parametrize("w_order", [False, True])
def test_roomconfig_sort_key(w_order):
    _ORDER = "explicitly_ordered"

    room_config_kw = BARE_ROOM_CONFIG_KW.copy()

    if w_order:
        room_config_kw["_order"] = _ORDER

    room_config = config.RoomConfig(**room_config_kw)

    found = room_config.sort_key

    if w_order:
        assert found == _ORDER
    else:
        assert found == ROOM_ID


@pytest.mark.parametrize(
    "rc_kwargs, expected",
    [
        (BARE_ROOM_CONFIG_KW.copy(), ()),
        (
            FULL_ROOM_CONFIG_KW.copy(),
            [
                # from 'agent_config'
                AGUI_FEATURE_NAME,
                # from 'room_config'
                EXTRA_AGUI_FEATURE_NAME,
            ],
        ),
    ],
)
def test_roomconfig_agui_feature_names(rc_kwargs, expected):
    room_config = config.RoomConfig(**rc_kwargs)

    found = room_config.agui_feature_names

    assert set(found) == set(expected)


@pytest.mark.parametrize("w_config_path", [False, True])
@pytest.mark.parametrize(
    "room_config_kw",
    [BARE_ROOM_CONFIG_KW, FULL_ROOM_CONFIG_KW],
)
def test_roomconfig_get_logo_image(temp_dir, room_config_kw, w_config_path):
    room_config_kw = room_config_kw.copy()

    if w_config_path:
        room_config_kw["_config_path"] = temp_dir / "room_config.yaml"

    room_config = config.RoomConfig(**room_config_kw)

    if room_config._config_path:
        if room_config._logo_image is not None:
            expected = temp_dir / room_config._logo_image
        else:
            expected = None

        found = room_config.get_logo_image()

        assert found == expected

    else:
        if room_config._logo_image is not None:
            with pytest.raises(config.NoConfigPath):
                room_config.get_logo_image()

        else:
            assert room_config.get_logo_image() is None


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BARE_COMPLETION_CONFIG_YAML, BARE_COMPLETION_CONFIG_KW),
        (FULL_COMPLETION_CONFIG_YAML, FULL_COMPLETION_CONFIG_KW),
    ],
)
def test_completionconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    if "name" not in expected_kw:
        expected_kw = expected_kw.copy()
        expected_kw["name"] = expected_kw["id"]

    expected = config.CompletionConfig(**expected_kw)

    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)
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

    if len(expected_kw.get("tool_configs", {})) > 0:
        for tool_config in expected_kw["tool_configs"].values():
            tool_config._installation_config = installation_config
            tool_config._config_path = yaml_file

    if len(expected_kw.get("mcp_client_toolset_configs", {})) > 0:
        for mcts_config in expected_kw["mcp_client_toolset_configs"].values():
            mcts_config._installation_config = installation_config
            mcts_config._config_path = yaml_file

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    found = config.CompletionConfig.from_yaml(
        installation_config,
        yaml_file,
        config_dict,
    )

    assert found == expected


@pytest.mark.parametrize(
    "w_properties_kw",
    [
        {"name": SKILL_NAME, "description": SKILL_DESC},
        {
            "name": SKILL_NAME,
            "description": SKILL_DESC,
            "license": SKILL_LICENSE,
            "compatibility": SKILL_COMPAT,
            "allowed_tools": SKILL_ALLOWED_TOOLS,
            "metadata": SKILL_METADATA,
        },
    ],
)
def test_skillconfig_properties(w_properties_kw):
    skill_config = config.SkillConfig(
        _skill_properties=skill_models.SkillProperties(**w_properties_kw)
    )

    assert skill_config.name == SKILL_NAME
    assert skill_config.description == SKILL_DESC
    assert skill_config.license == w_properties_kw.get("license")
    assert skill_config.compatibility == w_properties_kw.get("compatibility")
    assert skill_config.allowed_tools == w_properties_kw.get("allowed_tools")
    assert skill_config.metadata == w_properties_kw.get("metadata", {})
    assert skill_config.errors == []


def test_skillconfig_properties_w_errors():
    TEST_VALIDATION_ERROR = "Test validation error"

    skill_config = config.SkillConfig(
        _skill_properties=None,
        _validation_errors=[TEST_VALIDATION_ERROR],
    )

    assert skill_config.name is None
    assert skill_config.description is None
    assert skill_config.license is None
    assert skill_config.compatibility is None
    assert skill_config.allowed_tools is None
    assert skill_config.metadata is None
    assert skill_config.errors == [TEST_VALIDATION_ERROR]


@pytest.mark.parametrize(
    "w_params, exp_env_var_name",
    [
        ({}, SECRET_NAME),
        ({"env_var_name": ENV_VAR_NAME}, ENV_VAR_NAME),
    ],
)
def test_envvar_secret_source_ctor(w_params, exp_env_var_name):
    source = config.EnvVarSecretSource(secret_name=SECRET_NAME, **w_params)

    assert source.env_var_name == exp_env_var_name
    assert source.extra_arguments == {"env_var_name": exp_env_var_name}


@pytest.mark.parametrize("yaml_config", [{}, {"env_var_name": ENV_VAR_NAME}])
def test_envvarsecretsource_from_yaml(temp_dir, yaml_config):
    config_path = temp_dir / "installation.yaml"
    yaml_config["secret_name"] = SECRET_NAME

    source = config.EnvVarSecretSource.from_yaml(config_path, yaml_config)

    assert source._config_path == config_path
    assert source.secret_name == SECRET_NAME

    exp_env_var_name = (
        ENV_VAR_NAME if "env_var_name" in yaml_config else SECRET_NAME
    )

    assert source.env_var_name == exp_env_var_name
    assert source.extra_arguments == {"env_var_name": exp_env_var_name}


@pytest.mark.parametrize("has_ev", [False, True])
def test_envvarsecretsource_as_yaml(has_ev):
    config_kw = {"secret_name": SECRET_NAME}

    if has_ev:
        config_kw["env_var_name"] = ENV_VAR_NAME

    source = config.EnvVarSecretSource(**config_kw)

    expected = {
        "kind": config.EnvVarSecretSource.kind,
        "secret_name": SECRET_NAME,
        "env_var_name": ENV_VAR_NAME if has_ev else SECRET_NAME,
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize("file_path", ["/path/to/file", "./file"])
def test_filepathsecretsource_from_yaml(temp_dir, file_path):
    config_path = temp_dir / "installation.yaml"
    yaml_config = {"secret_name": SECRET_NAME, "file_path": file_path}

    source = config.FilePathSecretSource.from_yaml(config_path, yaml_config)

    assert source._config_path == config_path
    assert source.secret_name == SECRET_NAME
    assert source.file_path == file_path
    assert source.extra_arguments == {"file_path": file_path}


def test_filepathsecretsource_as_yaml():
    config_kw = {
        "secret_name": SECRET_NAME,
        "file_path": SECRET_FILE_PATH,
    }

    source = config.FilePathSecretSource(**config_kw)

    expected = {
        "kind": config.FilePathSecretSource.kind,
        "secret_name": SECRET_NAME,
        "file_path": SECRET_FILE_PATH,
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "w_args, exp_command_line",
    [
        ((), COMMAND),
        (["-a", "foo"], f"{COMMAND} -a foo"),
    ],
)
def test_subprocess_secret_source_command_line(w_args, exp_command_line):
    source = config.SubprocessSecretSource(
        secret_name=SECRET_NAME,
        command=COMMAND,
        args=w_args,
    )
    assert source.command_line == exp_command_line
    assert source.extra_arguments == {"command_line": exp_command_line}


@pytest.mark.parametrize(
    "w_args",
    [
        (),
        ["-a", "foo"],
    ],
)
def test_subprocesssecretsource_as_yaml(w_args):
    config_kw = {
        "secret_name": SECRET_NAME,
        "command": COMMAND,
        "args": w_args,
    }

    source = config.SubprocessSecretSource(**config_kw)

    expected = {
        "kind": config.SubprocessSecretSource.kind,
        "secret_name": SECRET_NAME,
        "command": COMMAND,
        "args": list(w_args),
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "kwargs, exp_nc",
    [
        ({}, 32),
        ({"n_chars": 17}, 17),
    ],
)
def test_randomcharssecretsource_extra_args(kwargs, exp_nc):
    source = config.RandomCharsSecretSource(secret_name=SECRET_NAME, **kwargs)

    assert source.extra_arguments == {"n_chars": exp_nc}


@pytest.mark.parametrize(
    "kwargs, exp_nc",
    [
        ({}, 32),
        ({"n_chars": 17}, 17),
    ],
)
def test_randomcharssecretsource_as_yaml(kwargs, exp_nc):
    source = config.RandomCharsSecretSource(secret_name=SECRET_NAME, **kwargs)

    expected = {
        "kind": config.RandomCharsSecretSource.kind,
        "secret_name": SECRET_NAME,
        "n_chars": exp_nc,
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "w_sources, exp_sources",
    [
        (None, [config.EnvVarSecretSource(secret_name=SECRET_NAME)]),
        (
            [
                config.EnvVarSecretSource(
                    secret_name=SECRET_NAME,
                    env_var_name=ENV_VAR_NAME,
                ),
            ],
            None,
        ),
    ],
)
def test_secretconfig_ctor(w_sources, exp_sources):
    if exp_sources is None:
        exp_sources = w_sources

    secret = config.SecretConfig(secret_name=SECRET_NAME, sources=w_sources)

    assert secret.secret_name == SECRET_NAME
    assert secret.sources == exp_sources


def test_secretconfig_as_yaml():
    source_1 = mock.Mock(spec_set=["as_yaml"])
    source_2 = mock.Mock(spec_set=["as_yaml"])
    secret = config.SecretConfig(
        secret_name=SECRET_NAME,
        sources=[source_1, source_2],
    )

    expected = {
        "secret_name": SECRET_NAME,
        "sources": [
            source_1.as_yaml,
            source_2.as_yaml,
        ],
    }
    found = secret.as_yaml

    assert found == expected


def test_secretconfig_resolved():
    secret = config.SecretConfig(secret_name=SECRET_NAME)

    assert secret.resolved is None
    secret._resolved = SECRET_VALUE
    assert secret.resolved == SECRET_VALUE


class FeatureModel(pydantic.BaseModel):
    """Feature model for testing"""

    foo: str
    bar: str | None = None


@pytest.fixture
def the_agui_feature():
    return config.AGUI_Feature(
        name=AGUI_FEATURE_NAME,
        model_klass=FeatureModel,
        source=config.AGUI_FeatureSource.CLIENT,
    )


def test_aguifeature_description(the_agui_feature):
    found = the_agui_feature.description

    assert found == "Feature model for testing"


def test_aguifeature_as_yaml(the_agui_feature):
    found = the_agui_feature.as_yaml

    assert found == {
        "name": AGUI_FEATURE_NAME,
        "description": "Feature model for testing",
        "source": "client",
    }


def test_aguifeature_json_schema(the_agui_feature):
    found = the_agui_feature.json_schema

    assert found == FeatureModel.model_json_schema()


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        ({}, DEFAULT_LFIPYDAI_EXP_KWARGS),
        (W_VALUES_LFIPYDAI_CONFIG_KW, W_VALUES_LFIPYDAI_CONFIG_EXP_KW),
    ],
)
def test_lfipydai_instrument_pydantic_ai_kwargs(init_kw, expected):
    ipydai_config = config.LogfireInstrumentPydanticAI(**init_kw)

    found = ipydai_config.instrument_pydantic_ai_kwargs

    assert found == expected


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        ({}, DEFAULT_LFIPYDAI_EXP_KWARGS),
        (W_VALUES_LFIPYDAI_CONFIG_KW, W_VALUES_LFIPYDAI_CONFIG_EXP_KW),
    ],
)
def test_lfipydai_as_yaml(init_kw, expected):
    ipydai_config = config.LogfireInstrumentPydanticAI(**init_kw)

    found = ipydai_config.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (EMPTY_LFIPYDAI_CONFIG_YAML, None),
        (W_VALUES_LFIPYDAI_CONFIG_YAML, W_VALUES_LFIPYDAI_CONFIG_KW),
    ],
)
def test_lfipydai_from_yaml(
    temp_dir,
    config_yaml,
    expected_kw,
):
    pass
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if expected_kw is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.LogfireInstrumentPydanticAI.from_yaml(
                yaml_file,
                config_dict,
            )

        assert exc.value._config_path == yaml_file

    else:
        expected = config.LogfireInstrumentPydanticAI(**expected_kw)
        expected = dataclasses.replace(
            expected,
            _config_path=yaml_file,
        )

        found = config.LogfireInstrumentPydanticAI.from_yaml(
            yaml_file,
            config_dict,
        )

        assert found == expected


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        ({}, DEFAULT_LFIFAPI_EXP_KWARGS),
        (W_VALUES_LFIFAPI_CONFIG_KW, W_VALUES_LFIFAPI_CONFIG_EXP_KW),
    ],
)
def test_lfifapi_instrument_fast_api_kwargs(init_kw, expected):
    ipydai_config = config.LogfireInstrumentFastAPI(**init_kw)

    found = ipydai_config.instrument_fast_api_kwargs

    assert found == expected


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        ({}, DEFAULT_LFIFAPI_EXP_KWARGS),
        (W_VALUES_LFIFAPI_CONFIG_KW, W_VALUES_LFIFAPI_CONFIG_EXP_KW),
    ],
)
def test_lfifapi_as_yaml(init_kw, expected):
    ipydai_config = config.LogfireInstrumentFastAPI(**init_kw)

    found = ipydai_config.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (EMPTY_LFIFAPI_CONFIG_YAML, None),
        (W_VALUES_LFIFAPI_CONFIG_YAML, W_VALUES_LFIFAPI_CONFIG_KW),
    ],
)
def test_lfifapi_from_yaml(
    temp_dir,
    config_yaml,
    expected_kw,
):
    pass
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if expected_kw is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.LogfireInstrumentFastAPI.from_yaml(
                yaml_file,
                config_dict,
            )

        assert exc.value._config_path == yaml_file

    else:
        expected = config.LogfireInstrumentFastAPI(**expected_kw)
        expected = dataclasses.replace(
            expected,
            _config_path=yaml_file,
        )

        found = config.LogfireInstrumentFastAPI.from_yaml(
            yaml_file,
            config_dict,
        )

        assert found == expected


@pytest.mark.parametrize(
    "init_kw, ic_secrets, ic_env, expected",
    [
        (
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_DEFAULT_SECRETS,
            TEST_LOGFIRE_IC_DEFAULT_ENV,
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_TOKEN_ONLY_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_DEFAULT_SECRETS,
            TEST_LOGFIRE_IC_DEFAULT_ENV,
            W_TOKEN_ONLY_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_SOME_SCALARS_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_OTHER_SECRETS,
            TEST_LOGFIRE_IC_OTHER_ENV,
            W_SOME_SCALARS_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_SCALARS_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_OTHER_SECRETS,
            TEST_LOGFIRE_IC_OTHER_ENV,
            W_SCALARS_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_BASE_URL_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_OTHER_SECRETS,
            TEST_LOGFIRE_IC_OTHER_ENV,
            W_BASE_URL_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_SCRUBBING_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_DEFAULT_SECRETS,
            TEST_LOGFIRE_IC_DEFAULT_ENV,
            W_SCRUBBING_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
    ],
)
def test_logfireconfig_logfire_config_kwargs(
    installation_config,
    init_kw,
    ic_secrets,
    ic_env,
    expected,
):
    get_secret = installation_config.get_secret
    get_secret.side_effect = ic_secrets.get

    installation_config.get_environment.side_effect = ic_env.get

    lf_config = config.LogfireConfig(
        _installation_config=installation_config,
        **init_kw,
    )

    found = lf_config.logfire_config_kwargs

    assert found == expected


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        (
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_INIT_KW,
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_TOKEN_ONLY_LOGFIRE_CONFIG_INIT_KW,
            W_TOKEN_ONLY_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_SOME_SCALARS_LOGFIRE_CONFIG_INIT_KW,
            W_SOME_SCALARS_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_SCALARS_LOGFIRE_CONFIG_INIT_KW,
            W_SCALARS_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_BASE_URL_LOGFIRE_CONFIG_INIT_KW,
            W_BASE_URL_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_SCRUBBING_LOGFIRE_CONFIG_INIT_KW,
            W_SCRUBBING_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_IPYDAI_LOGFIRE_CONFIG_INIT_KW,
            W_IPYDAI_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_IFAPI_LOGFIRE_CONFIG_INIT_KW,
            W_IFAPI_LOGFIRE_CONFIG_AS_YAML,
        ),
    ],
)
def test_logfireconfig_logfire_as_yaml(
    installation_config,
    init_kw,
    expected,
):
    lf_config = config.LogfireConfig(
        _installation_config=installation_config,
        **init_kw,
    )

    found = lf_config.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (EMPTY_LOGFIRE_CONFIG_YAML, None),
        (
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_YAML,
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_TOKEN_ONLY_LOGFIRE_CONFIG_YAML,
            W_TOKEN_ONLY_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_SOME_SCALARS_LOGFIRE_CONFIG_YAML,
            W_SOME_SCALARS_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_SCALARS_LOGFIRE_CONFIG_YAML,
            W_SCALARS_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_BASE_URL_LOGFIRE_CONFIG_YAML,
            W_BASE_URL_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_SCRUBBING_LOGFIRE_CONFIG_YAML,
            W_SCRUBBING_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_IPYDAI_LOGFIRE_CONFIG_YAML,
            W_IPYDAI_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_IFAPI_LOGFIRE_CONFIG_YAML,
            W_IFAPI_LOGFIRE_CONFIG_INIT_KW,
        ),
    ],
)
def test_logfireconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if expected_kw is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.LogfireConfig.from_yaml(
                installation_config,
                yaml_file,
                config_dict,
            )

        assert exc.value._config_path == yaml_file

    else:
        ipydai = expected_kw.pop("instrument_pydantic_ai", None)

        if ipydai is not None:
            ipydai = dataclasses.replace(ipydai, _config_path=yaml_file)
            expected_kw["instrument_pydantic_ai"] = ipydai

        ifapi = expected_kw.pop("instrument_fast_api", None)

        if ifapi is not None:
            ifapi = dataclasses.replace(ifapi, _config_path=yaml_file)
            expected_kw["instrument_fast_api"] = ifapi

        expected = config.LogfireConfig(**expected_kw)
        expected = dataclasses.replace(
            expected,
            _installation_config=installation_config,
            _config_path=yaml_file,
        )

        found = config.LogfireConfig.from_yaml(
            installation_config,
            yaml_file,
            config_dict,
        )

        assert found == expected


def test__load_config_yaml_w_missing(temp_dir):
    config_path = temp_dir / "oidc"
    config_path.mkdir()
    missing_cfg = config_path / "config.yaml"

    with pytest.raises(config.NoSuchConfig) as exc:
        config._load_config_yaml(missing_cfg)

    assert exc.value._config_path == missing_cfg


@pytest.mark.parametrize(
    "invalid",
    [
        b"\xde\xad\xbe\xef",  # raises UnicodeDecodeError
        "",  # parses as None
        "123",  # parses as int
        "4.56",  # parses as float
        '"foo"',  # parses as str
        '- "abc"\n- "def"',  # parses as list of str
    ],
)
def test__load_config_yaml_w_invalid(temp_dir, invalid):
    config_path = temp_dir / "oidc"
    config_path.mkdir()
    invalid_cfg = config_path / "config.yaml"

    if isinstance(invalid, bytes):
        invalid_cfg.write_bytes(invalid)
    else:
        invalid_cfg.write_text(invalid)

    with pytest.raises(config.FromYamlException) as exc:
        config._load_config_yaml(invalid_cfg)

    assert exc.value._config_path == invalid_cfg


def test__find_configs_yaml_w_single(temp_dir):
    THING_ID = "testing"
    CONFIG_FILENAME = "config.yaml"
    to_search = temp_dir / "to_search"
    to_search.mkdir()
    config_file = to_search / CONFIG_FILENAME
    config_file.write_text(f"id: {THING_ID}")
    expected = {"id": THING_ID}

    found = list(config._find_configs_yaml(to_search, CONFIG_FILENAME))

    assert found == [(config_file, expected)]


def test__find_configs_w_multiple(temp_dir):
    THING_IDS = ["foo", "bar", "baz", "qux"]
    CONFIG_FILENAME = "config.yaml"

    expected_things = []

    for thing_id in sorted(THING_IDS):
        thing_path = temp_dir / thing_id
        if thing_id == "baz":  # file, not dir
            thing_path.write_text("DEADBEEF")
        elif thing_id == "qux":  # empty dir
            thing_path.mkdir()
        else:
            thing_path.mkdir()
            config_file = thing_path / CONFIG_FILENAME
            config_file.write_text(f"id: {thing_id}")
            expected_thing = {"id": thing_id}
            expected_things.append((config_file, expected_thing))

    found_things = list(config._find_configs_yaml(temp_dir, CONFIG_FILENAME))

    for (f_key, f_thing), (e_key, e_thing) in zip(
        sorted(found_things),
        sorted(expected_things),
        strict=True,
    ):
        assert f_key == e_key
        assert f_thing == e_thing


def test__find_skill_paths_w_single(temp_dir):
    CONFIG_FILENAME = "SKILL.md"
    to_search = temp_dir / "to_search"
    to_search.mkdir()
    config_file = to_search / CONFIG_FILENAME
    config_file.write_text(f"""
---
name: {SKILL_NAME}
description: {SKILL_DESC}
---
""")

    found = list(config._find_skill_paths(to_search))

    assert found == [to_search]


def test__find_skill_paths_w_multiple(temp_dir):
    SKILL_NAMES = ["foo", "bar", "baz", "qux", ".skipme"]
    CONFIG_FILENAME = "SKILL.md"

    expected_paths = []

    for skill_name in sorted(SKILL_NAMES):
        maybe_path = temp_dir / skill_name
        if skill_name == "baz":  # file, not dir
            maybe_path.write_text("DEADBEEF")
        elif skill_name == "qux":  # empty dir
            maybe_path.mkdir()
        else:
            maybe_path.mkdir()
            config_file = maybe_path / CONFIG_FILENAME
            config_file.write_text(f"""
---
name: {skill_name}
description: Describing {skill_name}
---
""")
            if not maybe_path.stem.startswith("."):
                expected_paths.append(maybe_path)

    found_paths = list(config._find_skill_paths(temp_dir))

    assert found_paths == expected_paths


NotASecret = pytest.raises(config.NotASecret)


@pytest.mark.parametrize(
    "config_str, expectation, expected",
    [
        ("secret:test", NoRaise, "test"),
        ("invalid", NotASecret, None),
    ],
)
def test_strip_secret_prefix(config_str, expectation, expected):
    with expectation:
        found = config.strip_secret_prefix(config_str)

    if expected is not None:
        assert found == expected


@pytest.mark.parametrize(
    "config_value, expected",
    [
        ("no_prefix", "no_prefix"),
        ("file:test.foo", "{temp_dir}/test.foo"),
        (1234, 1234),
    ],
)
def test_resolve_file_prefix(temp_dir, config_value, expected):
    config_path = temp_dir / "config.yaml"

    if isinstance(expected, str):
        expected = expected.format(temp_dir=temp_dir.resolve())

    found = config.resolve_file_prefix(config_value, config_path)

    assert found == expected


@pytest.mark.parametrize(
    "env_name, env_value, dotenv_env, osenv_patch, expectation",
    [
        ("ENVVAR", None, {}, {}, pytest.raises(config.MissingEnvVar)),
        (
            "ENVVAR",
            None,
            {"ENVVAR": "dotenv"},
            {},
            contextlib.nullcontext("dotenv"),
        ),
        (
            "ENVVAR",
            None,
            {},
            {"ENVVAR": "osenv"},
            contextlib.nullcontext("osenv"),
        ),
        (
            "ENVVAR",
            None,
            {"ENVVAR": "dotenv"},
            {"ENVVAR": "osenv"},
            contextlib.nullcontext("dotenv"),  # dotenv_env wins
        ),
        (
            "ENVVAR",
            "baz",
            {},
            {},
            contextlib.nullcontext("baz"),
        ),
        (
            "ENVVAR",
            "baz",
            {"ENVVAR": "dotenv"},
            {},
            contextlib.nullcontext("baz"),
        ),
        (
            "ENVVAR",
            "baz",
            {},
            {"ENVVAR": "osenv"},
            contextlib.nullcontext("baz"),
        ),
        (
            "ENVVAR",
            "baz",
            {"ENVVAR": "dotenv"},
            {"ENVVAR": "osenv"},
            contextlib.nullcontext("baz"),
        ),
    ],
)
def test_resolve_environment_entry(
    env_name,
    env_value,
    dotenv_env,
    osenv_patch,
    expectation,
):
    with (
        mock.patch.dict("os.environ", **osenv_patch),
        expectation as expected,
    ):
        found = config.resolve_environment_entry(
            env_name,
            env_value,
            dotenv_env,
        )

    if isinstance(expected, str):
        assert found == expected

    else:
        assert expected.value.env_var == "ENVVAR"


@mock.patch("importlib.import_module")
def test__from_dotted_name(im):
    dotted_name = "somemodule.SomeClass"

    faux_module = im.return_value = mock.Mock()

    klass = config._from_dotted_name(dotted_name)

    assert klass is faux_module.SomeClass


@mock.patch("importlib.import_module")
def test_configmeta_from_yaml_w_dotted_name(im):
    config_yaml = "somemodule.SomeClass"

    faux_module = im.return_value = mock.Mock()

    meta = config.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is faux_module.SomeClass


@pytest.mark.parametrize("w_wrapper", [False, True])
def test_configmeta_from_yaml_w_dict(w_wrapper):
    config_klass = mock.Mock()
    wrapper_klass = mock.Mock()

    config_yaml = {"config_klass": config_klass}

    if w_wrapper:
        config_yaml["wrapper_klass"] = wrapper_klass

    meta = config.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is config_klass

    if w_wrapper:
        assert meta.wrapper_klass is wrapper_klass
    else:
        assert meta.wrapper_klass is None


@pytest.mark.parametrize("w_wrapper", [False, True])
def test_configmeta_from_yaml_w_dict_w_names(w_wrapper):
    dummy_module = mock.Mock()
    config_klass = dummy_module.ConfigClass = mock.Mock()
    wrapper_klass = dummy_module.WrapperClass = mock.Mock()

    config_yaml = {"config_klass": "dummy.ConfigClass"}

    if w_wrapper:
        config_yaml["wrapper_klass"] = "dummy.WrapperClass"

    with mock.patch.dict("sys.modules", dummy=dummy_module):
        meta = config.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is config_klass

    if w_wrapper:
        assert meta.wrapper_klass is wrapper_klass
    else:
        assert meta.wrapper_klass is None


def test_configmeta_dottedname():
    config_klass = mock.create_autospec(
        type,
        __module__="some.module",
        __name__="some_config",
    )
    meta = config.ConfigMeta(config_klass=config_klass)

    assert meta.dotted_name == "some.module.some_config"


@pytest.fixture
def patched_soliplex_config():
    with mock.patch.dict(config.__dict__) as patched:
        patched["test_secret_func"] = SECRET_SOURCE_FUNC
        patched["AGUI_FEATURES_BY_NAME"] = {}
        patched["TOOL_CONFIG_CLASSES_BY_TOOL_NAME"] = {}
        patched["MCP_TOOLSET_CONFIG_CLASSES_BY_KIND"] = {}
        patched["MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME"] = {}
        patched["AGENT_CONFIG_CLASSES_BY_KIND"] = {}
        patched["SECRET_GETTERS_BY_KIND"] = {}

        yield patched


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BOGUS_ICMETA_YAML, None),
        (BARE_ICMETA_YAML, BARE_ICMETA_KW),
        (W_AGUI_FEATURES_ICMETA_YAML, W_AGUI_FEATURES_ICMETA_KW),
        (W_MCP_TOOLSET_CONFIGS_ICMETA_YAML, W_MCP_TOOLSET_CONFIGS_ICMETA_KW),
        (W_AGENT_CONFIGS_ICMETA_YAML, W_AGENT_CONFIGS_ICMETA_KW),
        (
            W_SECRET_SOURCE_ICMETA_YAML,
            W_SECRET_SOURCE_ICMETA_KW,
        ),
        (FULL_ICMETA_YAML, FULL_ICMETA_KW),
    ],
)
def test_installationconfigmeta_from_yaml(
    temp_dir,
    patched_soliplex_config,
    config_yaml,
    expected_kw,
):
    expected_kw = copy.deepcopy(expected_kw)

    yaml_file = temp_dir / "config.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as fp:
        config_dict = yaml.safe_load(fp)

    config_meta = config_dict["meta"]

    if expected_kw is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.InstallationConfigMeta.from_yaml(
                yaml_file,
                config_meta,
            )
        assert exc.value._config_path == yaml_file

    else:
        expected = config.InstallationConfigMeta(
            _config_path=yaml_file,
            **expected_kw,
        )

        ic_meta = config.InstallationConfigMeta.from_yaml(
            yaml_file,
            config_meta.copy() if config_meta is not None else None,
        )

        assert ic_meta == expected

        if config_meta and "agui_features" in config_meta:
            afs_by_feature_name = patched_soliplex_config[
                "AGUI_FEATURES_BY_NAME"
            ]
            for (af_name, af_found), af_expected in zip(
                afs_by_feature_name.items(),
                config_meta["agui_features"],
                strict=True,
            ):
                assert af_name == af_expected["name"]
                assert af_found.name == af_expected["name"]
                assert af_found.model_klass == af_expected["model_klass"]
                assert af_found.source == af_expected["source"]

        if config_meta and "mcp_toolset_configs" in config_meta:
            tcs_by_kind = patched_soliplex_config[
                "MCP_TOOLSET_CONFIG_CLASSES_BY_KIND"
            ]
            tcs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in tcs_by_kind.values()
            }
            for klass_name in config_meta["mcp_toolset_configs"]:
                assert tcs_by_class_name[klass_name].kind in tcs_by_kind

        if config_meta and "mcp_toolset_configs" in config_meta:
            tcs_by_kind = patched_soliplex_config[
                "MCP_TOOLSET_CONFIG_CLASSES_BY_KIND"
            ]
            tcs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in tcs_by_kind.values()
            }
            for klass_name in config_meta["mcp_toolset_configs"]:
                assert tcs_by_class_name[klass_name].kind in tcs_by_kind

        if config_meta and "agent_configs" in config_meta:
            acs_by_kind = patched_soliplex_config[
                "AGENT_CONFIG_CLASSES_BY_KIND"
            ]
            acs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in acs_by_kind.values()
            }
            for klass_name in config_meta["agent_configs"]:
                kind = acs_by_class_name[klass_name].kind
                assert kind in acs_by_kind

        if config_meta and "secret_sources" in config_meta:
            sg_by_kind = patched_soliplex_config["SECRET_GETTERS_BY_KIND"]
            assert sg_by_kind == {
                config.EnvVarSecretSource.kind: SECRET_SOURCE_FUNC
            }


@pytest.mark.parametrize("w_secret_reg", [False, True])
@pytest.mark.parametrize("w_agent", [False, True])
@pytest.mark.parametrize("w_mcp_toolsets", [False, True])
def test_installationconfigmeta_as_yaml(
    patched_soliplex_config,
    w_mcp_toolsets,
    w_agent,
    w_secret_reg,
):
    icmeta_kw = {}
    expected_dict = copy.deepcopy(BARE_ICMETA_KW)
    icmeta_kw = icmeta_kw.copy()

    if w_mcp_toolsets:
        config.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND[
            config.Stdio_MCP_ClientToolsetConfig.kind
        ] = config.Stdio_MCP_ClientToolsetConfig
        expected_dict["mcp_toolset_configs"].append(
            "soliplex.config.Stdio_MCP_ClientToolsetConfig",
        )

    if w_agent:
        config.AGENT_CONFIG_CLASSES_BY_KIND[config.AgentConfig.kind] = (
            config.AgentConfig
        )
        expected_dict["agent_configs"].append(
            "soliplex.config.AgentConfig",
        )

    if w_secret_reg:
        config.SECRET_GETTERS_BY_KIND[config.EnvVarSecretSource.kind] = (
            secrets.get_env_var_secret
        )
        expected_dict["secret_sources"].append(
            {
                "config_klass": "soliplex.config.EnvVarSecretSource",
                "registered_func": "soliplex.secrets.get_env_var_secret",
            }
        )

    icmeta = config.InstallationConfigMeta(**icmeta_kw)

    found = icmeta.as_yaml

    assert found == expected_dict


def test_installationconfigmeta_postinit_registers_tool_configs(
    patched_soliplex_config,
):
    @dataclasses.dataclass(kw_only=True)
    class _DummyToolConfig(config.ToolConfig):
        tool_name: str = "tests.unit.test_config.dummy_tool"

    tc_meta = config.ConfigMeta(config_klass=_DummyToolConfig)
    config.InstallationConfigMeta(tool_configs=[tc_meta])

    tcs = patched_soliplex_config["TOOL_CONFIG_CLASSES_BY_TOOL_NAME"]
    assert tcs[_DummyToolConfig.tool_name] is _DummyToolConfig


def test_installationconfigmeta_postinit_registers_mcp_tool_wrappers(
    patched_soliplex_config,
):
    @dataclasses.dataclass(kw_only=True)
    class _DummyToolConfig(config.ToolConfig):
        tool_name: str = "tests.unit.test_config.dummy_tool"

    @dataclasses.dataclass(kw_only=True)
    class _DummyWrapper:
        func: typing.Any
        tool_config: config.ToolConfig

    mstw_meta = config.ConfigMeta(
        config_klass=_DummyToolConfig,
        wrapper_klass=_DummyWrapper,
    )
    config.InstallationConfigMeta(mcp_server_tool_wrappers=[mstw_meta])

    wrappers = patched_soliplex_config["MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME"]
    assert wrappers[_DummyToolConfig.tool_name] is _DummyWrapper


@pytest.mark.parametrize("w_disable_dotenv", [False, True])
def test_installationconfig_from_dotenv_already(w_disable_dotenv):
    already = {"KEY": "value"}

    i_config = config.InstallationConfig(
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

    i_config = config.InstallationConfig(
        id="test-ic",
        disable_dotenv=w_disable_dotenv,
        _config_path=inst_config_file,
    )

    found = i_config.from_dotenv

    assert found == expected


def test_installationconfig_secrets_map_wo_existing():
    secrets = [
        config.SecretConfig(secret_name=f"secret-{i_secret}")
        for i_secret in range(5)
    ]

    i_config = config.InstallationConfig(id="test-ic", secrets=secrets)

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
    i_config = config.InstallationConfig(id="test-ic", _secrets_map=already)

    found = i_config.secrets_map

    assert found is already


RaiseUnknownSecret = pytest.raises(secrets.UnknownSecret)
NoRaise = contextlib.nullcontext()


@pytest.mark.parametrize(
    "secret_map, expectation",
    [
        ({}, RaiseUnknownSecret),
        ({SECRET_NAME_1: SECRET_CONFIG_1}, NoRaise),
    ],
)
@mock.patch("soliplex.secrets.get_secret")
def test_installationconfig_get_secret(gs, secret_map, expectation):
    i_config = config.InstallationConfig(
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

    i_config = config.InstallationConfig(
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


@pytest.mark.parametrize("w_default", [False, True])
@pytest.mark.parametrize("w_hit", [False, True])
def test_installationconfig_get_environment(w_hit, w_default):
    KEY = "test-key"
    VALUE = "test-value"
    DEFAULT = "test-default"

    kwargs = {}

    if w_default:
        kwargs["default"] = DEFAULT

    i_config = config.InstallationConfig(id="test-ic")

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
            pytest.raises(config.MissingEnvVars),
            "UNRESOLVED",
            None,
        ),
        (
            [UNRESOLVED, UNRESOLVED_MOAR],
            (None, False),
            pytest.raises(config.MissingEnvVars),
            "UNRESOLVED,UNRESOLVED_MOAR",
            None,
        ),
        (
            [UNRESOLVED, UNRESOLVED_MOAR],
            ({"UNRESOLVED": "via_dotenv"}, False),
            pytest.raises(config.MissingEnvVars),
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
            pytest.raises(config.MissingEnvVars),
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
def test_installation_resolve_environment(
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

    i_config = config.InstallationConfig(
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


@pytest.mark.parametrize("w_obu", [False, True])
def test_installationconfig_haiku_rag_config(temp_dir, w_obu):
    hr_config_file = temp_dir / "haiku.rag.yaml"
    hr_config_file.write_text("""\
environment: production
""")

    i_config = config.InstallationConfig(
        id="test-ic",
        _config_path=temp_dir / "installation.yaml",
        _haiku_rag_config_file=hr_config_file,
    )

    if w_obu:
        exp_obu = i_config.environment["OLLAMA_BASE_URL"] = OLLAMA_BASE_URL
    else:
        exp_obu = "http://localhost:11434"

    with mock.patch.dict("os.environ", clear=True):
        hr_config = i_config.haiku_rag_config

    assert isinstance(hr_config, hr_config_module.AppConfig)
    assert hr_config.providers.ollama.base_url == exp_obu


def test_installationconfig_agent_configs_map_wo_existing():
    agent_configs = [
        config.AgentConfig(
            id=f"agent-config-{i_agent_config}",
        )
        for i_agent_config in range(5)
    ]

    i_config = config.InstallationConfig(
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
    i_config = config.InstallationConfig(
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

    i_config = config.InstallationConfig(
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

    i_config = config.InstallationConfig(
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

    i_config = config.InstallationConfig(
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

    i_config = config.InstallationConfig(
        id="test-ic",
        _config_path=temp_dir / "installation.yaml",
        **kw,
    )

    logging_claims_map = i_config.logging_claims_map

    if w_map:
        assert logging_claims_map == {"foo": "bar"}
    else:
        assert logging_claims_map == {}


def test_installationconfig_agui_features(the_agui_feature):
    i_config = config.InstallationConfig(id="test-ic")

    with mock.patch.dict(
        "soliplex.config.AGUI_FEATURES_BY_NAME",
        clear=True,
        the_agui_feature=the_agui_feature,
    ):
        found = i_config.agui_features

    assert found == [the_agui_feature]


@pytest.mark.parametrize(
    "w_kw, expected",
    [
        (
            BARE_INSTALLATION_CONFIG_KW.copy(),
            config.SYNC_MEMORY_ENGINE_URL,
        ),
        (W_TP_DBURI_INSTALLATION_CONFIG_KW.copy(), TP_DBURI_SYNC),
        (
            (
                W_TP_DBURI_W_SECRET_INSTALLATION_CONFIG_KW
                | {"secrets": [DB_SECRET_CONFIG]}
            ),
            TP_DBURI_SYNC_W_SECRET_RESOLVED,
        ),
    ],
)
def test_installationconfig_thread_persistence_dburi_sync(w_kw, expected):
    installation_config = config.InstallationConfig(**w_kw)

    found = installation_config.thread_persistence_dburi_sync

    assert found == expected


@pytest.mark.parametrize(
    "w_kw, expected",
    [
        (
            BARE_INSTALLATION_CONFIG_KW.copy(),
            config.ASYNC_MEMORY_ENGINE_URL,
        ),
        (W_TP_DBURI_INSTALLATION_CONFIG_KW.copy(), TP_DBURI_ASYNC),
    ],
)
def test_installationconfig_thread_persistence_dburi_async(w_kw, expected):
    installation_config = config.InstallationConfig(**w_kw)

    found = installation_config.thread_persistence_dburi_async

    assert found == expected


@pytest.mark.parametrize(
    "w_kw, expected",
    [
        (
            BARE_INSTALLATION_CONFIG_KW.copy(),
            config.SYNC_MEMORY_ENGINE_URL,
        ),
        (W_RA_DBURI_INSTALLATION_CONFIG_KW.copy(), RA_DBURI_SYNC),
        (
            (
                W_RA_DBURI_W_SECRET_INSTALLATION_CONFIG_KW
                | {"secrets": [DB_SECRET_CONFIG]}
            ),
            RA_DBURI_SYNC_W_SECRET_RESOLVED,
        ),
    ],
)
def test_installationconfig_authorization_dburi_sync(w_kw, expected):
    installation_config = config.InstallationConfig(**w_kw)

    found = installation_config.authorization_dburi_sync

    assert found == expected


@pytest.mark.parametrize(
    "w_kw, expected",
    [
        (
            BARE_INSTALLATION_CONFIG_KW.copy(),
            config.ASYNC_MEMORY_ENGINE_URL,
        ),
        (W_RA_DBURI_INSTALLATION_CONFIG_KW.copy(), RA_DBURI_ASYNC),
    ],
)
def test_installationconfig_authorization_dburi_async(w_kw, expected):
    installation_config = config.InstallationConfig(**w_kw)

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
    config_yaml,
    expected_kw,
):
    config_path = temp_dir / "installation.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    expected_kw = copy.deepcopy(expected_kw)

    if expected_kw is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.InstallationConfig.from_yaml(config_path, config_dict)

        assert exc.value._config_path == config_path

    else:
        if "meta" in expected_kw:
            icmeta_kw = expected_kw.pop("meta")
            expected_kw["meta"] = config.InstallationConfigMeta(
                **icmeta_kw,
                _config_path=config_path,
            )
        else:
            expected_kw["meta"] = config.InstallationConfigMeta(
                _config_path=config_path,
            )

        if "_haiku_rag_config_file" not in expected_kw:
            expected_kw["_haiku_rag_config_file"] = (
                config_path.parent / "haiku.rag.yaml"
            )

        expected = config.InstallationConfig(
            **expected_kw,
            _config_path=config_path,
        )

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

        found = config.InstallationConfig.from_yaml(config_path, config_dict)

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

        if "agent_configs" in expected_kw:
            # Assign '_installation_config' after found is constructed.
            for exp_agent_config in expected.agent_configs:
                exp_agent_config._installation_config = found
                exp_agent_config._config_path = config_path

        if "logfire_config" in expected_kw:
            expected.logfire_config._installation_config = found
            expected.logfire_config._config_path = config_path

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
    expected = config.InstallationConfig(**expected_kw)
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
        skills_paths=[temp_dir / "skills"],
    )

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    with mock.patch.dict("os.environ", clear=True, TEST_ENVVAR=TEST_VALUE):
        found = config.InstallationConfig.from_yaml(yaml_file, config_dict)

    assert found == expected


@pytest.mark.parametrize("w_logfire_config", [False, True])
def test_installationconfig_as_yaml(w_logfire_config):
    meta = mock.create_autospec(config.InstallationConfigMeta)
    secret_1 = config.SecretConfig(secret_name="SECRET_ONE")
    secret_2 = config.SecretConfig(secret_name="SECRET_TWO")
    agent_config = config.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        model_name=MODEL_NAME,
        provider_base_url=PROVIDER_BASE_URL,
    )

    kwargs = {}

    if w_logfire_config:
        kwargs["logfire_config"] = config.LogfireConfig(
            token="secret:LOGFIRE_TOKEN",
        )

    installation_config = config.InstallationConfig(
        id=INSTALLATION_ID,
        meta=meta,
        secrets=[secret_1, secret_2],
        environment={
            "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
        },
        _haiku_rag_config_file=pathlib.Path(HAIKU_RAG_CONFIG_FILE),
        agent_configs=[agent_config],
        _logging_config_file=pathlib.Path(LOGGING_CONFIG_FILE),
        oidc_paths=[pathlib.Path("./oidc-test")],
        room_paths=[
            pathlib.Path("/path/to/rooms"),
            pathlib.Path("./other/rooms"),
        ],
        completion_paths=[pathlib.Path("/path/to/completions")],
        quizzes_paths=[pathlib.Path("./other/quizzes")],
        skills_paths=[pathlib.Path("./other/skills")],
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
        "haiku_rag_config_file": HAIKU_RAG_CONFIG_FILE,
        "agent_configs": [
            agent_config.as_yaml,
        ],
        "logging_config_file": LOGGING_CONFIG_FILE,
        "oidc_paths": ["oidc-test"],
        "room_paths": ["/path/to/rooms", "other/rooms"],
        "completion_paths": ["/path/to/completions"],
        "quizzes_paths": ["other/quizzes"],
        "skills_paths": ["other/skills"],
    }

    if w_logfire_config:
        expected["logfire_config"] = W_TOKEN_ONLY_LOGFIRE_CONFIG_AS_YAML

    found = installation_config.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "w_pem_path",
    [
        ABSOLUTE_OIDC_CLIENT_PEM_PATH,
        RELATIVE_OIDC_CLIENT_PEM_PATH,
    ],
)
@pytest.mark.parametrize("w_pem", [False, "bare_top", "bare_authsys"])
@mock.patch("soliplex.config._load_config_yaml")
def test_installationconfig_oidc_auth_system_configs_wo_existing(
    lcy,
    temp_dir,
    w_pem,
    w_pem_path,
):
    if w_pem_path.startswith("."):
        exp_oidc_client_pem_path = temp_dir / "oidc_bare" / w_pem_path
    else:
        exp_oidc_client_pem_path = pathlib.Path(w_pem_path)

    bare_config_yaml = {
        "auth_systems": [BARE_AUTHSYSTEM_CONFIG_KW.copy()],
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
        "auth_systems": [W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy()],
    }

    lcy.side_effect = [bare_config_yaml, w_scope_config_yaml]

    oidc_bare_path = temp_dir / "oidc_bare"
    oidc_bare_config = oidc_bare_path / "config.yaml"

    oidc_w_scope_path = temp_dir / "oidc_w_scope"
    oidc_w_scope_config = oidc_w_scope_path / "config.yaml"

    oidc_bare_kw = BARE_AUTHSYSTEM_CONFIG_KW.copy()
    oidc_bare_kw["oidc_client_pem_path"] = exp_oidc_client_pem_path
    oidc_bare_kw["_config_path"] = oidc_bare_config

    oidc_w_scope_kw = W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy()
    oidc_w_scope_kw["oidc_client_pem_path"] = None
    oidc_w_scope_kw["_config_path"] = oidc_w_scope_config

    i_config_kw = BARE_INSTALLATION_CONFIG_KW.copy()
    i_config_kw["oidc_paths"] = [oidc_bare_path, oidc_w_scope_path]

    i_config = config.InstallationConfig(**i_config_kw)

    expected = [
        config.OIDCAuthSystemConfig(
            _installation_config=i_config,
            **oidc_bare_kw,
        ),
        config.OIDCAuthSystemConfig(
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

    i_config = config.InstallationConfig(**kw)

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
            BARE_ROOM_CONFIG_YAML.replace(
                f'id: "{ROOM_ID}"',
                f'id: "{room_id}"',
                1,
            ),
        )

    i_config = config.InstallationConfig(**kw)

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
            BARE_ROOM_CONFIG_YAML.replace(
                # f'id: "{ROOM_ID}"', f'id: "{room_id}"', 1, # conflict on ID
                f'name: "{ROOM_NAME}"',
                f'name: "{room_path.name}"',
                1,
            )
        )

    i_config = config.InstallationConfig(**kw)

    found = i_config.room_configs

    assert found[ROOM_ID].id == ROOM_ID
    # order of 'room_paths' governs who wins
    assert found[ROOM_ID].name == "foo"


def test_installationconfig_room_configs_w_existing():
    RC_1, RC_2 = object(), object()
    existing = {"room_1": RC_1, "room_2": RC_2}

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_room_configs"] = existing

    i_config = config.InstallationConfig(**kw)

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
            BARE_COMPLETION_CONFIG_YAML.replace(
                f'id: "{COMPLETION_ID}"',
                f'id: "{completion_id}"',
                1,
            ),
        )

    i_config = config.InstallationConfig(**kw)

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
            FULL_COMPLETION_CONFIG_YAML.replace(
                # f'id: "{COMPLETION_ID}"',
                # f'id: "{completion_id}"',
                # 1, # conflict on ID
                f'name: "{COMPLETION_NAME}"',
                f'name: "{completion_path.name}"',
                1,
            )
        )

    i_config = config.InstallationConfig(**kw)

    found = i_config.completion_configs

    assert found[COMPLETION_ID].id == COMPLETION_ID
    # order of 'completion_paths' governs who wins
    assert found[COMPLETION_ID].name == "foo"


def test_installationconfig_completion_configs_w_existing():
    CC_1, CC_2 = object(), object()
    existing = {"completion_1": CC_1, "completion_2": CC_2}

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_completion_configs"] = existing

    i_config = config.InstallationConfig(**kw)

    found = i_config.completion_configs

    assert found["completion_1"] == CC_1
    assert found["completion_2"] == CC_2


@pytest.mark.parametrize("w_error", [False, True])
def test_installationconfig_skill_configs_wo_existing(temp_dir, w_error):
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
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT

    skills = temp_dir / "skills"
    skills.mkdir()

    for skill_name in SKILL_NAMES:
        skill_path = skills / skill_name
        skill_path.mkdir()
        skill_config = skill_path / "SKILL.md"
        skill_config.write_text(FOREMATTER.format(skill_name=skill_name))

    i_config = config.InstallationConfig(**kw)

    found = i_config.skill_configs

    if w_error:
        assert found["foo"].name is None
        assert found["foo"].errors
        assert found["bar"].name is None
        assert found["bar"].errors
    else:
        assert found["foo"].name == "foo"
        assert not found["foo"].errors
        assert found["bar"].name == "bar"
        assert not found["bar"].errors


@pytest.mark.parametrize("w_error", [False, True])
def test_installationconfig_skill_configs_wo_existing_w_conflict(
    temp_dir,
    w_error,
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
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT
    kw["skills_paths"] = SKILLS_PATHS

    for skills_path in SKILLS_PATHS:
        skill_path = temp_dir / skills_path / SKILL_NAME
        skill_path.mkdir(parents=True)
        skill_config = skill_path / "SKILL.md"
        skill_config.write_text(
            FOREMATTER.format(skill_name=SKILL_NAME, skills_path=skills_path)
        )

    i_config = config.InstallationConfig(**kw)

    found = i_config.skill_configs

    f_skill = found[SKILL_NAME]
    if w_error:
        assert f_skill.name is None
        assert f_skill.errors
    else:
        assert f_skill.name == SKILL_NAME
        # order of 'completion_paths' governs who wins
        assert f_skill.description == f"Describing {SKILL_NAME} in ./foo"
        assert not f_skill.errors


def test_installationconfig_skill_configs_w_existing():
    SC_1, SC_2 = object(), object()
    existing = {"skill_1": SC_1, "skill_2": SC_2}

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_skill_configs"] = existing

    i_config = config.InstallationConfig(**kw)

    found = i_config.skill_configs

    assert found["skill_1"] == SC_1
    assert found["skill_2"] == SC_2


def test_installationconfig_reload_configurations():
    existing = object()

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_oidc_auth_system_configs"] = existing
    kw["_room_configs"] = existing
    kw["_completion_configs"] = existing
    kw["_skill_configs"] = existing
    i_config = config.InstallationConfig(**kw)

    with mock.patch.multiple(
        i_config,
        _load_oidc_auth_system_configs=mock.DEFAULT,
        _load_room_configs=mock.DEFAULT,
        _load_completion_configs=mock.DEFAULT,
        _load_skill_configs=mock.DEFAULT,
    ) as patched:
        i_config.reload_configurations()

    assert (
        i_config._oidc_auth_system_configs
        is patched["_load_oidc_auth_system_configs"].return_value
    )

    assert i_config._room_configs is patched["_load_room_configs"].return_value

    assert (
        i_config._completion_configs
        is patched["_load_completion_configs"].return_value
    )

    assert (
        i_config._skill_configs is patched["_load_skill_configs"].return_value
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
        ("no_such_filename.yaml", config.NoSuchConfig, None),
        ("not_a_yaml_file.yaml", config.FromYamlException, None),
        ("/dev/null", config.NoSuchConfig, None),
        ("./not-there", config.NoSuchConfig, None),
        ("./there-but-no-config", config.NoSuchConfig, None),
        ("./there-with-config", False, "there-with-config"),
        ("./alt-config/filename.yaml", False, "alt-config"),
    ],
)
def test_load_installation(populated_temp_dir, rel_path, raises, expected_id):
    target = populated_temp_dir / rel_path

    if raises:
        with pytest.raises(raises):
            config.load_installation(target)

    else:
        installation = config.load_installation(target)

        assert installation.id == expected_id
