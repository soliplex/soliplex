from unittest import mock

import pytest

from soliplex import config
from soliplex import models
from soliplex import quizzes

INPUTS = "What color is the sky"
EXPECTED_ANSWER = "Blue"
QA_QUESTION_UUID = "DEADBEEF"
MC_QUESTION_UUID = "FACEDACE"
QUESTION_TYPE_QA = "qa"
QUESTION_TYPE_MC = "multiple-choice"
MC_OPTIONS = ["orange", "blue", "purple"]
QUIZ_JUDGE_AGENT_MODEL = "test-model"

OLLAMA_BASE_URL = "https://example.com:12345"


@pytest.fixture
def qa_question():
    return config.QuizQuestion(
        inputs=INPUTS,
        expected_output=EXPECTED_ANSWER,
        metadata=config.QuizQuestionMetadata(
            uuid=QA_QUESTION_UUID,
            type=QUESTION_TYPE_QA,
        )
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
        )
    )


@pytest.fixture
def test_quiz(qa_question, mc_question):
    quiz = config.QuizConfig(
        id="testing",
        question_file="ignored.json",
        judge_agent_model=QUIZ_JUDGE_AGENT_MODEL,
    )
    quiz._questions_map = {
        question.metadata.uuid: question
        for question in [qa_question, mc_question]
    }
    return quiz


@mock.patch("pydantic_ai.providers.ollama.OllamaProvider")
@mock.patch("pydantic_ai.models.openai.OpenAIChatModel")
@mock.patch("pydantic_ai.Agent")
def test_get_quiz_judge_agent(
    agent_klass, model_klass, provider_klass, test_quiz,
):
    env_patch = {
        "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
    }
    expected_provider_kw = {
        "base_url": OLLAMA_BASE_URL + "/v1",
        "api_key": "dummy",
    }

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        found = quizzes.get_quiz_judge_agent(test_quiz)

    assert found is agent_klass.return_value
    agent_klass.assert_called_once_with(
        model=model_klass.return_value,
        output_type=models.QuizLLMJudgeResponse,
        system_prompt=quizzes.ANSWER_EQUIVALENCE_RUBRIC,
    )

    model_klass.assert_called_once_with(
        model_name=test_quiz.judge_agent_model,
        provider=provider_klass.return_value,
    )

    provider_klass.assert_called_once_with(**expected_provider_kw)


@pytest.mark.anyio
@mock.patch("soliplex.quizzes.get_quiz_judge_agent")
async def test_check_answer_with_agent(gqja, qa_question, test_quiz):
    agent = gqja.return_value
    a_run = agent.run = mock.AsyncMock()
    answer = "Who knows?"

    found = await quizzes.check_answer_with_agent(
        test_quiz, qa_question, answer,
    )

    assert found is a_run.return_value.output.equivalent

    a_run_call, = a_run.await_args_list
    prompt, = a_run_call.args
    lines = prompt.splitlines()
    assert f"QUESTION: {INPUTS}" in lines
    assert f"ANSWER: {answer}" in lines
    assert f"EXPECTED ANSWER: {EXPECTED_ANSWER}" in lines

    gqja.assert_called_once_with(test_quiz)


@pytest.mark.anyio
@pytest.mark.parametrize("w_correct", [None, False, True])
@mock.patch("soliplex.quizzes.check_answer_with_agent")
async def test_check_answer_w_mc(cawa, test_quiz, w_correct):
    if w_correct is None:  # invalid question ID
        question_uuid = "nonesuch"
        answer = "doesn't matter"
    else:
        question_uuid = MC_QUESTION_UUID

        if w_correct:
            answer = EXPECTED_ANSWER
        else:
            answer = "wrong"

    if w_correct is None:
        with pytest.raises(quizzes.QuestionNotFound):
            await quizzes.check_answer(test_quiz, question_uuid, answer)

    else:
        found = await quizzes.check_answer(test_quiz, question_uuid, answer)

        if w_correct:
            assert found["correct"] == "true"
        else:
            assert found["correct"] == "false"
            assert found["expected_output"] == EXPECTED_ANSWER

        cawa.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("w_correct", [None, False, True])
@mock.patch("soliplex.quizzes.check_answer_with_agent")
async def test_check_answer_w_qa(cawa, test_quiz, qa_question, w_correct):
    if w_correct is None:  # invalid question ID
        question_uuid = "nonesuch"
        answer = "doesn't matter"
    else:
        question_uuid = QA_QUESTION_UUID

        if w_correct:
            answer = EXPECTED_ANSWER
            cawa.return_value = True
        else:
            answer = "wrong"
            cawa.return_value = False

    if w_correct is None:
        with pytest.raises(quizzes.QuestionNotFound):
            await quizzes.check_answer(test_quiz, question_uuid, answer)

    else:
        found = await quizzes.check_answer(test_quiz, question_uuid, answer)

        if w_correct:
            assert found["correct"] == "true"
        else:
            assert found["correct"] == "false"
            assert found["expected_output"] == EXPECTED_ANSWER

        cawa.assert_awaited_once_with(test_quiz, qa_question, answer)
