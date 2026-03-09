"""Soliplex configuration package"""

from soliplex.config.agents import (  # noqa F401 API
    AgentConfig,
    AgentConfigMap,
    FactoryAgentConfig,
    LLMProviderType,
)
from soliplex.config.agui import (  # noqa F401 API
    AGUI_FeatureSource,
)
from soliplex.config.authsystem import (  # noqa F401 API
    OIDCAuthSystemConfig,
)
from soliplex.config.completions import (  # noqa F401 API
    CompletionConfig,
)
from soliplex.config.installation import (  # noqa F401 API
    InstallationConfig,
    load_installation,
)
from soliplex.config.logfire import (  # noqa F401 API
    LogfireConfig,
)
from soliplex.config.quizzes import (  # noqa F401 API
    QuizConfig,
    QuizQuestion,
    QuizQuestionMetadata,
    QuizQuestionType,
)
from soliplex.config.rooms import (  # noqa F401 API
    RoomConfig,
    RoomConfigMap,
)
from soliplex.config.secrets import (  # noqa F401 API
    EnvVarSecretSource,
    FilePathSecretSource,
    SubprocessSecretSource,
    RandomCharsSecretSource,
    SecretConfig,
    SecretSource,
)
from soliplex.config.skills import (  # noqa F401 API
    SkillConfigTypes,
)
from soliplex.config.tools import (  # noqa F401 API
    MCP_ClientToolsetConfig,
    MCP_ClientToolsetConfigMap,
    ToolConfig,
    ToolConfigMap,
    ToolRequires,
)
