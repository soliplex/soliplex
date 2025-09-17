import os

import pydantic_ai
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import ollama as ollama_providers

from soliplex import config
from soliplex import models


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

