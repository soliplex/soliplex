import fastapi
from fastapi import Depends
from fastapi import security

from soliplex import auth
from soliplex import installation
from soliplex import models
from soliplex import quizzes

router = fastapi.APIRouter()

depend_the_installation = installation.depend_the_installation


@router.get("/v1/rooms/{room_id}/quiz/{quiz_id}")
async def get_quiz(
    request: fastapi.Request,
    room_id: str,
    quiz_id: str,
    the_installation: installation.Installation = depend_the_installation,
    user=Depends(auth.get_current_user),
) -> models.Quiz:

    try:
        room_config = the_installation.get_room_config(room_id, user=user)
    except ValueError as e:
        raise fastapi.HTTPException(
            status_code=404,
            detail=str(e),
        ) from None

    try:
        quiz = room_config.quiz_map[quiz_id]
    except KeyError as e:
        raise fastapi.HTTPException(
            status_code=404,
            detail=str(e),
        ) from None

    return models.Quiz.from_config(quiz)


@router.post("/v1/rooms/{room_id}/quiz/{quiz_id}/{question_uuid}")
async def post_quiz_question(
    request: fastapi.Request,
    room_id: str,
    quiz_id: str,
    question_uuid: str,
    answer: models.UserPromptClientMessage,
    the_installation: installation.Installation = depend_the_installation,
    user=Depends(auth.get_current_user),
) -> models.QuizQuestionResponse:

    try:
        room_config = the_installation.get_room_config(room_id, user=user)
    except ValueError as e:
        raise fastapi.HTTPException(
            status_code=404,
            detail=str(e),
        ) from None

    try:
        quiz = room_config.quiz_map[quiz_id]
    except KeyError as e:
        raise fastapi.HTTPException(
            status_code=404,
            detail=str(e),
        ) from None

    try:
        return await quizzes.check_answer(quiz, question_uuid, answer.text)
    except quizzes.QuestionNotFound as e:
        raise fastapi.HTTPException(
            status_code=404,
            detail=str(e),
        ) from None
