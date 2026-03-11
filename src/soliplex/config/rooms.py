from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import typing

from soliplex.agui import features as agui_features_module  # noqa F401

from . import _utils
from . import agents as config_agents
from . import exceptions as config_exc
from . import quizzes as config_quizzes
from . import skills as config_skills
from . import tools as config_tools

_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_default_list_field = _utils._default_list_field
_default_dict_field = _utils._default_dict_field

# ============================================================================
#   Room-related configuration types
# ============================================================================


@dataclasses.dataclass(kw_only=True)
class RoomConfig:
    """Configuration for a chat room"""

    #
    # Required room metadata
    #
    id: str
    name: str
    description: str
    agent_config: config_agents.AgentConfig

    #
    # Room UI options
    #
    _order: str = None  # defaults to 'id'
    welcome_message: str = None
    suggestions: list[str] = _default_list_field()
    enable_attachments: bool = False

    #
    # Tool options
    #
    tool_configs: config_tools.ToolConfigMap = _default_dict_field()
    mcp_client_toolset_configs: config_tools.MCP_ClientToolsetConfigMap = (
        _default_dict_field()
    )

    #
    # MCP options
    #
    allow_mcp: bool = False

    #
    # Skills options
    #
    skills: config_skills.RoomSkillsConfig = None

    #
    # Quiz-specific options
    #
    quizzes: list[config_quizzes.QuizConfig] = _default_list_field()
    _quiz_map: config_quizzes.QuizConfigMap = None

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    logo_image: dataclasses.InitVar[str] = None
    _logo_image: str = None

    _agui_feature_names: list[str] = _default_list_field()

    def __post_init__(self, logo_image: str | None):
        if logo_image is not None:
            self._logo_image = logo_image

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

            room_id = config_dict["id"]
            agent_config_yaml = config_dict.pop("agent")
            agent_config_yaml["id"] = f"room-{room_id}"

            config_dict["agent_config"] = config_agents.extract_agent_config(
                installation_config,
                config_path,
                agent_config_yaml,
            )

            config_dict["tool_configs"] = config_tools.extract_tool_configs(
                installation_config,
                config_path,
                config_dict,
            )

            config_dict["mcp_client_toolset_configs"] = (
                config_tools.extract_mcp_client_toolset_configs(
                    installation_config,
                    config_path,
                    config_dict,
                )
            )

            skills_config_yaml = config_dict.pop("skills", None)
            if skills_config_yaml is not None:
                config_dict["skills"] = (
                    config_skills.RoomSkillsConfig.from_yaml(
                        installation_config,
                        config_path,
                        skills_config_yaml,
                    )
                )

            quizzes_config_yaml = config_dict.pop("quizzes", None)
            if quizzes_config_yaml is not None:
                config_dict["quizzes"] = [
                    config_quizzes.QuizConfig.from_yaml(
                        installation_config,
                        config_path,
                        quiz_config_yaml,
                    )
                    for quiz_config_yaml in quizzes_config_yaml
                ]

            agui_feature_names = config_dict.pop("agui_feature_names", None)
            if agui_feature_names is not None:
                config_dict["_agui_feature_names"] = agui_feature_names

            logo_image = config_dict.pop("logo_image", None)
            config_dict["_logo_image"] = logo_image

            return cls(**config_dict)

        except config_exc.FromYamlException:  # pragma: NO COVER
            raise

        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "room",
                config_dict,
            ) from exc

    @property
    def sort_key(self):
        if self._order is not None:
            return self._order

        return self.id

    @property
    def skill_configs(self) -> config_skills.SkillConfigMap:
        return self.skills.skill_configs if self.skills is not None else {}

    @property
    def agui_feature_names(self) -> tuple[str]:
        agent_features = set(self.agent_config.agui_feature_names)
        room_features = set(self._agui_feature_names)
        tool_features = set()

        for tool_config in self.tool_configs.values():
            tool_features |= set(tool_config.agui_feature_names)

        skill_features = set()
        for skill_config in self.skill_configs.values():
            skill_features |= set(skill_config.agui_feature_names)

        return tuple(
            agent_features | tool_features | skill_features | room_features
        )

    @property
    def quiz_map(self) -> config_quizzes.QuizConfigMap:
        if self._quiz_map is None:
            self._quiz_map = {quiz.id: quiz for quiz in self.quizzes}

        return self._quiz_map

    def get_logo_image(self) -> pathlib.Path | None:
        if self._logo_image is not None:
            if self._config_path is None:
                raise config_exc.NoConfigPath()

            return self._config_path.parent / self._logo_image

    def list_haiku_rag_client_kw(
        self,
        include_source: bool = False,
    ) -> typing.Sequence[dict]:
        """List of kwargs to be passed to 'haiku.rag.client.HaikuRAG' ctor

        Candidates for producing these args include:
        - The room agent
        - Room skills (whether locally configured or via the installation)
        - Tool configs defined in the room

        For each candidate: if it derives from `config.rag._RAGConfigBase`
        (has `haiku_rag_config`/`rag_lancedb_path` attributes), return
        the corresponding kwargs dict.
        """
        candidates = (
            [("agent", self.agent_config)]
            + list(
                (
                    (f"skill:{key}", value)
                    for key, value in self.skills.skill_configs.items()
                )
                if self.skills is not None
                else ()
            )
            + list(
                (f"tool:{key}", value)
                for key, value in self.tool_configs.items()
            )
        )

        for source, cfg in candidates:
            hr_config = getattr(cfg, "haiku_rag_config", None)

            if hr_config is not None:
                hrc_kw = {
                    "db_path": cfg.rag_lancedb_path,
                    "config": hr_config,
                    "read_only": True,
                }

                if include_source:
                    hrc_kw["source"] = source

                yield hrc_kw


RoomConfigMap = dict[str, RoomConfig]
