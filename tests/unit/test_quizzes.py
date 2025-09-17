import dataclasses
import json
import pathlib
import tempfile
from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex import models
from soliplex import quizzes
from soliplex import util

TEST_ROOM_ID = "test_room"
TEST_QUIZ_ID = "test_quiz"

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
def quiz_questions(qa_question, mc_question):
    return [qa_question, mc_question]


@pytest.fixture
def test_quiz(qa_question, mc_question):
    rcq = config.QuizConfig(
        id="testing",
        question_file="ignored.json",
        judge_agent_model=QUIZ_JUDGE_AGENT_MODEL,
    )
    rcq._questions_map = {
        question.metadata.uuid: question
        for question in [qa_question, mc_question]
    }
    return rcq


@pytest.fixture
def test_quiz_json(quiz_questions):
    return {
        "cases": [
            dataclasses.asdict(question)
            for question in quiz_questions
        ]
    }


@pytest.fixture
def quiz_tempdir():
    with tempfile.TemporaryDirectory() as td:
        yield pathlib.Path(td)


@pytest.fixture
def populated_quiz(quiz_tempdir, test_quiz_json):
    populated_quiz = quiz_tempdir / f"{TEST_QUIZ_ID}.json"
    populated_quiz.write_text(json.dumps(test_quiz_json))
    return populated_quiz


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


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", [None, "room", "quiz"])
@mock.patch("soliplex.auth.authenticate")
async def test_get_quiz(auth_fn, test_quiz, w_miss):
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.Mock(spec_set=["get_room_config"])
    token = object()

    if w_miss == "room":
        the_installation.get_room_config.side_effect = ValueError("no room")

        with pytest.raises(fastapi.HTTPException) as exc:
            await quizzes.get_quiz(
                request=request,
                room_id=TEST_ROOM_ID,
                quiz_id=TEST_QUIZ_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404

    else:
        room_config = the_installation.get_room_config.return_value

        if w_miss == "quiz":
            room_config.quiz_map = {}

            with pytest.raises(fastapi.HTTPException) as exc:
                await quizzes.get_quiz(
                    request=request,
                    room_id=TEST_ROOM_ID,
                    quiz_id=TEST_QUIZ_ID,
                    the_installation=the_installation,
                    token=token,
                )

            assert exc.value.status_code == 404

        else:
            room_config.quiz_map = {TEST_QUIZ_ID: test_quiz}

            found = await quizzes.get_quiz(
                request=request,
                room_id=TEST_ROOM_ID,
                quiz_id=TEST_QUIZ_ID,
                the_installation=the_installation,
                token=token,
            )

            expected_json = dataclasses.asdict(test_quiz)
            expected_json["questions"] = [
                dataclasses.asdict(question)
                for question in test_quiz.get_questions()
            ]
            expected_json = util.scrub_private_keys(expected_json)
            assert found == expected_json

    the_installation.get_room_config.assert_called_once_with(
        TEST_ROOM_ID, user=auth_fn.return_value,
    )

    auth_fn.assert_called_once_with(the_installation, token)



@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", [None, "room", "quiz", "question"])
@mock.patch("soliplex.quizzes.check_answer")
@mock.patch("soliplex.auth.authenticate")
async def test_post_quiz_question(auth_fn, ca, test_quiz, w_miss):
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.Mock(spec_set=["get_room_config"])
    answer = models.UserPromptClientMessage(text="Answer")
    token = object()

    if w_miss == "room":
        the_installation.get_room_config.side_effect = ValueError("no room")

        with pytest.raises(fastapi.HTTPException) as exc:
            await quizzes.post_quiz_question(
                request=request,
                room_id=TEST_ROOM_ID,
                quiz_id=TEST_QUIZ_ID,
                question_uuid=QA_QUESTION_UUID,
                answer=answer,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404

    else:
        room_config = the_installation.get_room_config.return_value

        if w_miss == "quiz":
            room_config.quiz_map = {}

            with pytest.raises(fastapi.HTTPException) as exc:
                await quizzes.post_quiz_question(
                    request=request,
                    room_id=TEST_ROOM_ID,
                    quiz_id=TEST_QUIZ_ID,
                    question_uuid=QA_QUESTION_UUID,
                    answer=answer,
                    the_installation=the_installation,
                    token=token,
                )

            assert exc.value.status_code == 404

            ca.assert_not_called()

        else:
            room_config.quiz_map = {TEST_QUIZ_ID: test_quiz}

            if w_miss == "question":
                ca.side_effect = quizzes.QuestionNotFound(
                    TEST_QUIZ_ID, QA_QUESTION_UUID,
                )

                with pytest.raises(fastapi.HTTPException) as exc:
                    await quizzes.post_quiz_question(
                        request=request,
                        room_id=TEST_ROOM_ID,
                        quiz_id=TEST_QUIZ_ID,
                        question_uuid=QA_QUESTION_UUID,
                        answer=answer,
                        the_installation=the_installation,
                        token=token,
                    )

                assert exc.value.status_code == 404

            else:  # hit
                found = await quizzes.post_quiz_question(
                    request,
                    room_id=TEST_ROOM_ID,
                    quiz_id=TEST_QUIZ_ID,
                    question_uuid=QA_QUESTION_UUID,
                    answer=answer,
                    the_installation=the_installation,
                    token=token,
                )

                assert found is ca.return_value

            ca.assert_called_once_with(
                test_quiz, QA_QUESTION_UUID, answer.text,
            )


    auth_fn.assert_called_once_with(the_installation, token)
