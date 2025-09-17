import dataclasses

import fastapi
from fastapi import security

from soliplex import auth
from soliplex import installation
from soliplex import models
from soliplex import quizzes
from soliplex import util

router = fastapi.APIRouter()


@router.get("/v1/rooms/{room_id}/quiz/{quiz_id}", response_model=None)
async def get_quiz(
    request: fastapi.Request,
    room_id: str,
    quiz_id: str,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
):
    user = auth.authenticate(the_installation, token)

    try:
        room_config = the_installation.get_room_config(room_id, user=user)
    except ValueError as e:
        raise fastapi.HTTPException(
            status_code=404, detail=str(e),
        ) from None

    try:
        quiz = room_config.quiz_map[quiz_id]
    except KeyError as e:
        raise fastapi.HTTPException(
            status_code=404, detail=str(e),
        ) from None

    info = dataclasses.asdict(quiz)
    info["questions"] = [
        dataclasses.asdict(question)
        for question in quiz.get_questions()
    ]
    return util.scrub_private_keys(info)


@router.post(
    "/v1/rooms/{room_id}/quiz/{quiz_id}/{question_uuid}",
    response_model=models.QuizQuestionResponse,
)
async def post_quiz_question(
    request: fastapi.Request,
    room_id: str,
    quiz_id: str,
    question_uuid: str,
    answer: models.UserPromptClientMessage,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
):
    user = auth.authenticate(the_installation, token)

    try:
        room_config = the_installation.get_room_config(room_id, user=user)
    except ValueError as e:
        raise fastapi.HTTPException(
            status_code=404, detail=str(e),
        ) from None

    try:
        quiz = room_config.quiz_map[quiz_id]
    except KeyError as e:
        raise fastapi.HTTPException(
            status_code=404, detail=str(e),
        ) from None

    try:
        return await quizzes.check_answer(quiz, question_uuid, answer.text)
    except quizzes.QuestionNotFound as e:
        raise fastapi.HTTPException(
            status_code=404, detail=str(e),
        ) from None
