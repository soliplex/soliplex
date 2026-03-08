from unittest import mock

import fastapi
import pytest

from soliplex import authz as authz_package
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import quizzes
from soliplex.config import quizzes as config_quizzes
from soliplex.views import quizzes as quizzes_views

TEST_ROOM_ID = "test_room"
TEST_QUIZ_ID = "test_quiz"
ADMIN_EMAIL = "admin@example.com"
THE_USER_CLAIMS = {"email": ADMIN_EMAIL}

INPUTS = "What color is the sky"
EXPECTED_ANSWER = "Blue"
QA_QUESTION_UUID = "DEADBEEF"
MC_QUESTION_UUID = "FACEDACE"
QUESTION_TYPE_QA = "qa"
QUESTION_TYPE_MC = "multiple-choice"
MC_OPTIONS = ["orange", "blue", "purple"]


@pytest.fixture
def qa_question():
    return config_quizzes.QuizQuestion(
        inputs=INPUTS,
        expected_output=EXPECTED_ANSWER,
        metadata=config_quizzes.QuizQuestionMetadata(
            uuid=QA_QUESTION_UUID,
            type=QUESTION_TYPE_QA,
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
def test_quiz(qa_question, mc_question):
    quiz = config_quizzes.QuizConfig(
        id="testing",
        question_file="ignored.json",
    )
    quiz._questions_map = {
        question.metadata.uuid: question
        for question in [qa_question, mc_question]
    }
    return quiz


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", [None, "room", "quiz"])
async def test_get_quiz(test_quiz, w_miss):
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if w_miss == "room":
        the_installation.get_room_config.side_effect = KeyError("no room")

        with pytest.raises(fastapi.HTTPException) as exc:
            await quizzes_views.get_quiz(
                request=request,
                room_id=TEST_ROOM_ID,
                quiz_id=TEST_QUIZ_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            TEST_ROOM_ID,
        )

    else:
        room_config = the_installation.get_room_config.return_value

        if w_miss == "quiz":
            room_config.quiz_map = {}

            with pytest.raises(fastapi.HTTPException) as exc:
                await quizzes_views.get_quiz(
                    request=request,
                    room_id=TEST_ROOM_ID,
                    quiz_id=TEST_QUIZ_ID,
                    the_installation=the_installation,
                    the_authz_policy=the_authz_policy,
                    the_user_claims=THE_USER_CLAIMS,
                    the_logger=the_logger,
                )

            assert exc.value.status_code == 404
            the_logger.exception.assert_called_once_with(
                loggers.QUIZ_UNKNOWN_QUIZ_ID,
                TEST_QUIZ_ID,
            )

        else:
            room_config.quiz_map = {TEST_QUIZ_ID: test_quiz}

            found = await quizzes_views.get_quiz(
                request=request,
                room_id=TEST_ROOM_ID,
                quiz_id=TEST_QUIZ_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

            expected = models.Quiz.from_config(test_quiz)
            assert found == expected

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        user=THE_USER_CLAIMS,
        the_authz_policy=the_authz_policy,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(loggers.QUIZ_GET_QUIZ)


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", [None, "room", "quiz", "question"])
@mock.patch("soliplex.quizzes.check_answer")
async def test_post_quiz_question(ca, test_quiz, w_miss):
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)
    answer = models.QuizAnswer(text="Answer")

    if w_miss == "room":
        the_installation.get_room_config.side_effect = KeyError("no room")

        with pytest.raises(fastapi.HTTPException) as exc:
            await quizzes_views.post_quiz_question(
                request=request,
                room_id=TEST_ROOM_ID,
                quiz_id=TEST_QUIZ_ID,
                question_uuid=QA_QUESTION_UUID,
                answer=answer,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            TEST_ROOM_ID,
        )

    else:
        room_config = the_installation.get_room_config.return_value

        if w_miss == "quiz":
            room_config.quiz_map = {}

            with pytest.raises(fastapi.HTTPException) as exc:
                await quizzes_views.post_quiz_question(
                    request=request,
                    room_id=TEST_ROOM_ID,
                    quiz_id=TEST_QUIZ_ID,
                    question_uuid=QA_QUESTION_UUID,
                    answer=answer,
                    the_installation=the_installation,
                    the_authz_policy=the_authz_policy,
                    the_user_claims=THE_USER_CLAIMS,
                    the_logger=the_logger,
                )

            assert exc.value.status_code == 404
            the_logger.exception.assert_called_once_with(
                loggers.QUIZ_UNKNOWN_QUIZ_ID,
                TEST_QUIZ_ID,
            )

            ca.assert_not_called()

        else:
            room_config.quiz_map = {TEST_QUIZ_ID: test_quiz}

            if w_miss == "question":
                ca.side_effect = quizzes.QuestionNotFound(
                    TEST_QUIZ_ID,
                    QA_QUESTION_UUID,
                )

                with pytest.raises(fastapi.HTTPException) as exc:
                    await quizzes_views.post_quiz_question(
                        request=request,
                        room_id=TEST_ROOM_ID,
                        quiz_id=TEST_QUIZ_ID,
                        question_uuid=QA_QUESTION_UUID,
                        answer=answer,
                        the_installation=the_installation,
                        the_authz_policy=the_authz_policy,
                        the_user_claims=THE_USER_CLAIMS,
                        the_logger=the_logger,
                    )

                assert exc.value.status_code == 404
                the_logger.exception.assert_called_once_with(
                    loggers.QUIZ_UNKNOWN_QUESTION_UUID,
                    QA_QUESTION_UUID,
                )

            else:  # hit
                found = await quizzes_views.post_quiz_question(
                    request,
                    room_id=TEST_ROOM_ID,
                    quiz_id=TEST_QUIZ_ID,
                    question_uuid=QA_QUESTION_UUID,
                    answer=answer,
                    the_installation=the_installation,
                    the_authz_policy=the_authz_policy,
                    the_user_claims=THE_USER_CLAIMS,
                    the_logger=the_logger,
                )

                assert found is ca.return_value

            ca.assert_called_once_with(
                test_quiz,
                QA_QUESTION_UUID,
                answer.text,
            )

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        user=THE_USER_CLAIMS,
        the_authz_policy=the_authz_policy,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(loggers.QUIZ_POST_QUIZ_QUESTION)
