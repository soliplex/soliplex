import pathlib

import pydantic

from soliplex import config

#=============================================================================
#   Public config models
#
#   Types returned from API methods describing the installation config
#   These models omit private / implementation fields
#=============================================================================

class Quiz(pydantic.BaseModel):
    """Metadata about a quiz"""
    id: str
    title: str
    randomize: bool
    max_questions: int | None = None

    @classmethod
    def from_config(cls, quiz_config: config.QuizConfig):
        return cls(
            id=quiz_config.id,
            title=quiz_config.title,
            randomize=quiz_config.randomize,
            max_questions=quiz_config.max_questions,
        )

ConfiguredQuizzes = dict[str, Quiz]


class Room(pydantic.BaseModel):
    id: str
    name: str
    description: str
    welcome_message: str
    suggestions: list[str]
    enable_attachments: bool
    quizzes: ConfiguredQuizzes

    @classmethod
    def from_config(cls, room_config: config.RoomConfig):
        return cls(
            id=room_config.id,
            name=room_config.name,
            description=room_config.description,
            welcome_message=(
                room_config.welcome_message or room_config.description
            ),
            suggestions=room_config.suggestions,
            enable_attachments=room_config.enable_attachments,
            quizzes={
                quiz.id: Quiz.from_config(quiz)
                for quiz in room_config.quizzes
            },
        )

ConfiguredRooms = dict[str, Room]


class Installation(pydantic.BaseModel):
    """Configuration for a set of rooms, completions, etc."""
    id: str
    secrets: list[str] = []
    environment: dict[str, str] = {}
    oidc_paths: list[pathlib.Path] = []
    room_paths: list[pathlib.Path] = []
    completions_paths: list[pathlib.Path] = []
    quizzes_paths: list[pathlib.Path] = []

    @classmethod
    def from_config(cls, installation_config: config.InstallationConfig):
        return cls(
            id=installation_config.id,
            secrets=installation_config.secrets,
            environment=installation_config.environment,
            oidc_paths=installation_config.oidc_paths,
            room_paths=installation_config.room_paths,
            completions_paths=installation_config.completions_paths,
            quizzes_paths=installation_config.quizzes_paths,
        )

#=============================================================================
#   API interaction models
#=============================================================================

class SearchResult(pydantic.BaseModel):
    content: str
    score: float
    document_uri: str | None = None
