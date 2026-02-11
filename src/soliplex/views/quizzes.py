import fastapi

from soliplex import authn
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import models
from soliplex import quizzes
from soliplex import views

router = fastapi.APIRouter(tags=["quizzes"])

depend_the_installation = installation.depend_the_installation
depend_the_authz = authz_package.depend_the_authz_policy
depend_the_user_claims = views.depend_the_user_claims


@router.get("/v1/rooms/{room_id}/quiz/{quiz_id}")
async def get_quiz(
    request: fastapi.Request,
    room_id: str,
    quiz_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.Quiz:
    """Return a quiz as configured from a room"""
    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
        )
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
    answer: models.QuizAnswer,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.QuizQuestionResponse:
    """Check a user's response to a quiz question."""
    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
        )
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
