from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import json
import os
import pathlib
import random

from . import _utils
from . import agents
from . import exceptions

_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_default_list_field = _utils._default_list_field
_default_dict_field = _utils._default_dict_field


# ============================================================================
#   Quiz-related configuration types
# ============================================================================


class QCExactlyOneOfStemOrOverride(TypeError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Configure exactly one of '_question_file_stem' or "
            f"'_question_file_override_path' "
            f"(configured in {_config_path})"
        )


class QuestionFileNotFoundWithStem(ValueError):
    def __init__(self, stem, quizzes_paths, _config_path):
        self.stem = stem
        self.quizzes_paths = quizzes_paths
        self._config_path = _config_path
        super().__init__(
            f"'{stem}.json' file not found on paths: "
            f"{','.join([str(qp) for qp in quizzes_paths])} "
            f"(configured in {_config_path})"
        )


class QuestionFileNotFoundWithOverride(ValueError):
    def __init__(self, override, _config_path):
        self.override = override
        self._config_path = _config_path
        super().__init__(
            f"'{override}' file not found (configured in {_config_path})"
        )


class QuizQuestionType(enum.StrEnum):
    QA = "qa"
    FILL_BLANK = "fill-blank"
    MULTIPLE_CHOICE = "multiple-choice"


@dataclasses.dataclass(kw_only=True)
class QuizQuestionMetadata:
    type: QuizQuestionType
    uuid: str
    options: list[str] = _default_list_field()


@dataclasses.dataclass(kw_only=True)
class QuizQuestion:
    inputs: str
    expected_output: str
    metadata: QuizQuestionMetadata


@dataclasses.dataclass(kw_only=True)
class QuizConfig:
    id: str
    question_file: dataclasses.InitVar[str] = None
    _question_file_stem: str = None
    _question_file_path_override: str = None
    _questions_map: dict[str, QuizQuestion] = None

    title: str = "Quiz"
    randomize: bool = False
    max_questions: int = None

    judge_agent: agents.AgentConfig | None = None

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycles
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            ja_config = config_dict.pop("judge_agent", None)
            if ja_config is not None:
                config_dict["judge_agent"] = agents.extract_agent_config(
                    installation_config,
                    config_path,
                    ja_config,
                )

            return cls(**config_dict)

        except exceptions.FromYamlException:  # pragma: NO COVER
            raise

        except Exception as exc:
            raise exceptions.FromYamlException(
                config_path,
                "quiz",
                config_dict,
            ) from exc

    def __post_init__(self, question_file):
        if question_file is not None:
            if os.sep in question_file or "/" in question_file:
                self._question_file_path_override = question_file
            else:
                if question_file.endswith(".json"):
                    question_file = question_file[: -len(".json")]

                self._question_file_stem = question_file
        if (
            self._question_file_stem is None
            and self._question_file_path_override is None
        ) or (
            self._question_file_stem is not None
            and self._question_file_path_override is not None
        ):
            raise QCExactlyOneOfStemOrOverride(self._config_path)

        if self.judge_agent is None:
            kwargs = {
                "id": f"quiz-{self.id}-judge",
                "model_name": "gpt-oss:20b",
            }
            if self._installation_config is not None:
                i_config = self._installation_config
                kwargs["provider_base_url"] = i_config.get_environment(
                    "OLLAMA_BASE_URL",
                )
            self.judge_agent = agents.AgentConfig(**kwargs)

    @property
    def question_file_path(self) -> pathlib.Path:
        if self._question_file_path_override is not None:
            return pathlib.Path(self._question_file_path_override)
        else:
            for quizzes_path in self._installation_config.quizzes_paths:
                qf_path = quizzes_path / f"{self._question_file_stem}.json"

                if qf_path.is_file():
                    return qf_path

    @staticmethod
    def _make_question(question: dict) -> QuizQuestion:
        metadata = QuizQuestionMetadata(
            uuid=question["metadata"]["uuid"],
            type=question["metadata"]["type"],
            options=question["metadata"].get("options", []),
        )
        return QuizQuestion(
            inputs=question["inputs"],
            expected_output=question["expected_output"],
            metadata=metadata,
        )

    def _load_questions_file(self) -> dict[str, QuizQuestion]:
        question_file = self.question_file_path

        if question_file is None:
            raise QuestionFileNotFoundWithStem(
                self._question_file_stem,
                self._installation_config.quizzes_paths,
                self._config_path,
            )

        if not question_file.is_file():
            raise QuestionFileNotFoundWithOverride(
                self._question_file_path_override,
                self._config_path,
            )

        quiz_json = json.loads(self.question_file_path.read_text())
        return {
            q_dict["metadata"]["uuid"]: self._make_question(q_dict)
            for q_dict in quiz_json["cases"]
        }

    def get_questions(self) -> list[QuizQuestion]:
        if self._questions_map is None:
            self._questions_map = self._load_questions_file()

        questions = list(self._questions_map.values())

        if self.randomize:
            random.shuffle(questions)

        if self.max_questions is not None:
            questions = questions[: self.max_questions]

        return questions

    def get_question(self, uuid: str) -> QuizQuestion:
        if self._questions_map is None:
            self._questions_map = self._load_questions_file()

        return self._questions_map[uuid]


QuizConfigMap = dict[str, QuizConfig]
