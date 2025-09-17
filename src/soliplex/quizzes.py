import dataclasses
import os

import fastapi
import pydantic_ai
from fastapi import security
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import ollama as ollama_providers

from soliplex import auth
from soliplex import config
from soliplex import installation
from soliplex import models
from soliplex import util

router = fastapi.APIRouter()


class QuestionNotFound(ValueError):
    def __init__(self, quiz_id, question_uuid):
        self.quiz_id = quiz_id
        self.question_uuid = question_uuid
        super().__init__(
            f"Question '{question_uuid}' not found for quiz '{quiz_id}'"
        )


ANSWER_EQUIVALENCE_MODEL = "gpt-oss:20b"  # XXX which model?
ANSWER_EQUIVALENCE_RUBRIC = """You are evaluating whether two answers to the same question are semantically equivalent.

EVALUATION CRITERIA:
Rate as EQUIVALENT if:
✓ Answer contain minor typos
✓ Both answers contain the same core factual information
✓ Both directly address the question asked
✓ The key claims and conclusions are consistent
✓ Any additional detail in one answer doesn't contradict the other

Rate as NOT EQUIVALENT if:
✗ Factual contradictions exist between the answers
✗ One answer fails to address the core question
✗ Key information is missing that changes the meaning
✗ The answers lead to different conclusions or implications

GUIDELINES:
- Ignore minor differences in phrasing, style, or formatting
- Focus on semantic meaning rather than exact wording
- Consider both answers correct if they convey the same essential information
- Be tolerant of different levels of detail if the core answer is preserved
- Evaluate based on what a person asking this question would need to know
/no_think"""  # noqa: E501 first line is important to the LLM.


def get_quiz_judge_agent(quiz: config.QuizConfig):
    provider_base_url = os.environ["OLLAMA_BASE_URL"]

    ollama_provider = ollama_providers.OllamaProvider(
        base_url=f"{provider_base_url}/v1", api_key="dummy"
    )

    ollama_model = openai_models.OpenAIChatModel(
        model_name=quiz.judge_agent_model,
        provider=ollama_provider,
    )

    # Create Pydantic AI agent
    return pydantic_ai.Agent(
        model=ollama_model,
        output_type=models.QuizLLMJudgeResponse,
        system_prompt=ANSWER_EQUIVALENCE_RUBRIC,
    )


async def check_answer_with_agent(
    quiz: config.QuizConfig,
    question: config.QuizQuestion,
    answer: str,
) -> bool:
    agent = get_quiz_judge_agent(quiz)

    prompt = f"""\
QUESTION: {question.inputs}

ANSWER: {answer}

EXPECTED ANSWER: {question.expected_output}"""

    result = await agent.run(prompt)
    return result.output.equivalent


async def check_answer(
    quiz: config.QuizConfig, question_uuid: str, answer: str,
) -> bool:

    try:
        question = quiz.get_question(question_uuid)
    except KeyError:
        raise QuestionNotFound(quiz.id, question_uuid) from None

    if question.metadata.type == config.QuizQuestionType.MULTIPLE_CHOICE:
        answer = answer.strip().lower()
        correct = (answer == question.expected_output.lower())

    else:
        correct = await check_answer_with_agent(quiz, question, answer)

    if correct:
        return {"correct": "true"}
    else:
        return {
            "correct": "false",
            "expected_output": question.expected_output,
        }



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
        return await check_answer(quiz, question_uuid, answer.text)
    except QuestionNotFound as e:
        raise fastapi.HTTPException(
            status_code=404, detail=str(e),
        ) from None
