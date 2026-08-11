import typing
from collections import abc

from soliplex import secrets as soliplex_secrets
from soliplex.config import skills as config_skills
from soliplex.config import tools as config_tools


class DummyModelClass:
    pass


def dummy_tool(query: str):  # pragma: NO COVER (registered, not called)
    pass


class DummyToolConfig(config_tools.ToolConfig):
    tool_name = "_test_metaconfig.dummy_tool"
    kind = "DummyToolConfig"


class DummyMCP_ToolsetConfig:
    kind = "dummy"


class DummyMCPWrapper:
    func: abc.Callable[..., typing.Any]
    tool_config: config_tools.ToolConfig

    def __call__(
        self,
        tweedle: str,
    ):  # pragma: NO COVER (registered, not called)
        return self.func(tweedle, tool_config=self.tool_config)


class DummySkillConfig(config_skills.SkillConfig):
    skill_name = "_test_metaconfig.DummySkillConfig"
    name = "test_skiil"
    description = "Test Skill"
    kind = "DummySkillConfig"


class DummyAgentCapability:
    dotted_name = "foo.bar"


class DummyAgentConfig:
    kind = "dummy"


def dummy_secret_getter(source):  # pragma: NO COVER (registered, not called)
    raise soliplex_secrets.UnknownSecret("dummy")


class DummySecretSource:
    kind = "dummy"


class DummyConfigClass:
    pass


class DummyWrapperClass:
    pass


def dummy_jsonpath_func():  # pragma: NO COVER (registered, not called)
    pass
