import pathlib
import typing

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


class Tool(pydantic.BaseModel):
    kind: str
    tool_name: str
    tool_description: str
    tool_requires: config.ToolRequires
    allow_mcp: bool
    extra_parameters: dict[str, typing.Any]

    @classmethod
    def from_config(cls, tool_config: config.ToolConfig):
        return cls(
            kind=tool_config.kind,
            tool_name=tool_config.tool_name,
            tool_description=tool_config.tool_description,
            tool_requires=tool_config.tool_requires,
            allow_mcp=tool_config.allow_mcp,
            extra_parameters=tool_config.get_extra_parameters(),
        )

ConfiguredTools = dict[str, Tool]


class Room(pydantic.BaseModel):
    id: str
    name: str
    description: str
    welcome_message: str
    suggestions: list[str]
    enable_attachments: bool
    tools: ConfiguredTools
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
            tools={
                key: Tool.from_config(tool_config)
                for (key, tool_config) in room_config.tool_configs.items()
            },
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
