import contextlib
import dataclasses
import json
import pathlib
from unittest import mock

import pytest
import yaml

from soliplex.config import agents as config_agents
from soliplex.config import exceptions as config_exc
from soliplex.config import quizzes as config_quizzes

NoRaise = contextlib.nullcontext()

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

QUIZ_ID = "test_quiz"

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
    config_quizzes.QuizQuestion(
        inputs=QUESTION_1,
        expected_output=ANSWER_1,
        metadata=config_quizzes.QuizQuestionMetadata(
            uuid=Q_UUID_1,
            type=TYPE_1,
        ),
    ),
    config_quizzes.QuizQuestion(
        inputs=QUESTION_2,
        expected_output=ANSWER_2,
        metadata=config_quizzes.QuizQuestionMetadata(
            type=TYPE_2, uuid=Q_UUID_2, options=OPTIONS_2
        ),
    ),
]

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


@pytest.fixture
def qa_question():
    return config_quizzes.QuizQuestion(
        inputs=INPUTS,
        expected_output=EXPECTED_ANSWER,
        metadata=config_quizzes.QuizQuestionMetadata(
            uuid=QA_QUESTION_UUID,
            type=QUESTION_TYPE_QA,
            options=None,
        ),
    )


@pytest.fixture
def mc_question():
    return config_quizzes.QuizQuestion(
        inputs=INPUTS,
        expected_output=EXPECTED_ANSWER,
        metadata=config_quizzes.QuizQuestionMetadata(
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
    with pytest.raises(config_quizzes.QCExactlyOneOfStemOrOverride):
        config_quizzes.QuizConfig(id=TEST_QUIZ_ID)


def test_quizconfig_ctor_exclusive():
    with pytest.raises(config_quizzes.QCExactlyOneOfStemOrOverride):
        config_quizzes.QuizConfig(
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

    qc = config_quizzes.QuizConfig(
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

    with pytest.raises(config_exc.FromYamlException) as exc:
        config_quizzes.QuizConfig.from_yaml(
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

    expected_kw["judge_agent"] = config_agents.AgentConfig(**jac)

    expected = config_quizzes.QuizConfig(**expected_kw)

    expected = dataclasses.replace(
        expected,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    found = config_quizzes.QuizConfig.from_yaml(
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
    qc = config_quizzes.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file="nonesuch",
        _installation_config=installation_config,
    )

    with pytest.raises(config_quizzes.QuestionFileNotFoundWithStem):
        qc._load_questions_file()


def test_quizconfig__load_questions_file_miss_w_override(
    installation_config,
    temp_dir,
):
    qc = config_quizzes.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file=str(temp_dir / "nonesuch.json"),
        _installation_config=installation_config,
    )

    with pytest.raises(config_quizzes.QuestionFileNotFoundWithOverride):
        qc._load_questions_file()


def test_quizconfig__load_questions_file(temp_dir, populated_quiz, quiz_json):
    expected_questions = quiz_json["cases"]

    qc = config_quizzes.QuizConfig(
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

    qc = config_quizzes.QuizConfig(**kwargs)

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
    qc = config_quizzes.QuizConfig(
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

    qc = config_quizzes.QuizConfig(
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
