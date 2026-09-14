"""Guard the declared interpolation inventory.

The declarations are inert until the resolver reads them, so nothing else
would notice a field annotated wrongly, annotated twice, or dropped.  These
tests pin the whole inventory against a literal table, and against the
operator-facing list in ``docs/config/installation.md``.
"""

import dataclasses
import importlib
import pathlib
import pkgutil

import soliplex.config
from soliplex.config import interpolation as config_interpolation

MK = config_interpolation.MarkerKind
MA = config_interpolation.MarkerArity
VS = config_interpolation.ValueShape

NONE = (None, None, None)
SECRET_WHOLE = (MK.SECRET, MA.WHOLE_REQUIRED, VS.SCALAR)
SECRET_WHOLE_OR_LITERAL = (MK.SECRET, MA.WHOLE_OPTIONAL, VS.SCALAR)
ENV_WHOLE_OR_LITERAL = (MK.ENVIRONMENT, MA.WHOLE_OPTIONAL, VS.SCALAR)
ENV_EMBEDDED = (MK.ENVIRONMENT, MA.EMBEDDED, VS.SCALAR)
BOTH_EMBEDDED = (MK.BOTH, MA.EMBEDDED, VS.SCALAR)
BOTH_EMBEDDED_SEQUENCE = (MK.BOTH, MA.EMBEDDED, VS.SEQUENCE)
BOTH_EMBEDDED_MAPPING = (MK.BOTH, MA.EMBEDDED, VS.MAPPING)

# Every interpolation declared under 'soliplex.config', keyed by
# '<module>.<class>.<field>'.  Adding or removing one is a deliberate,
# two-place edit.
EXPECTED = {
    "agents.AgentConfig.model_name": ENV_EMBEDDED,
    "agents.AgentConfig.provider_base_url": ENV_EMBEDDED,
    "agents.AgentConfig.provider_key": SECRET_WHOLE,
    "agents.AgentConfig._system_prompt_text": NONE,
    "authsystem.OIDCAuthSystemConfig.client_secret": (SECRET_WHOLE_OR_LITERAL),
    "installation.InstallationConfig._thread_persistence_dburi_sync": (
        BOTH_EMBEDDED
    ),
    "installation.InstallationConfig._thread_persistence_dburi_async": (
        BOTH_EMBEDDED
    ),
    "installation.InstallationConfig._authorization_dburi_sync": (
        BOTH_EMBEDDED
    ),
    "installation.InstallationConfig._authorization_dburi_async": (
        BOTH_EMBEDDED
    ),
    "logfire.LogfireConfig.token": SECRET_WHOLE,
    "logfire.LogfireConfig.service_name": ENV_WHOLE_OR_LITERAL,
    "logfire.LogfireConfig.service_version": ENV_WHOLE_OR_LITERAL,
    "logfire.LogfireConfig.environment": ENV_WHOLE_OR_LITERAL,
    "logfire.LogfireConfig.config_dir": ENV_WHOLE_OR_LITERAL,
    "logfire.LogfireConfig.data_dir": ENV_WHOLE_OR_LITERAL,
    "logfire.LogfireConfig.min_level": ENV_WHOLE_OR_LITERAL,
    "logfire.LogfireConfig.base_url": ENV_WHOLE_OR_LITERAL,
    "tools.Stdio_MCP_ClientToolsetConfig.command": BOTH_EMBEDDED,
    "tools.Stdio_MCP_ClientToolsetConfig.args": BOTH_EMBEDDED_SEQUENCE,
    "tools.Stdio_MCP_ClientToolsetConfig.env": BOTH_EMBEDDED_MAPPING,
    "tools.Stdio_MCP_ClientToolsetConfig.allowed_tools": NONE,
    "tools._Remote_MCP_ClientToolsetConfig.url": BOTH_EMBEDDED,
    "tools._Remote_MCP_ClientToolsetConfig.headers": (BOTH_EMBEDDED_MAPPING),
    "tools._Remote_MCP_ClientToolsetConfig.query_params": (
        BOTH_EMBEDDED_MAPPING
    ),
    "tools._Remote_MCP_ClientToolsetConfig.allowed_tools": NONE,
}

INSTALLATION_DOC = (
    pathlib.Path(__file__).parents[3] / "docs" / "config" / "installation.md"
)


def _iter_config_dataclasses():
    """Yield '(module_name, klass)' for each dataclass under the package."""
    for mod_info in sorted(
        pkgutil.iter_modules(soliplex.config.__path__),
        key=lambda info: info.name,
    ):
        module = importlib.import_module(f"soliplex.config.{mod_info.name}")

        for klass in vars(module).values():
            if not isinstance(klass, type):
                continue

            if not dataclasses.is_dataclass(klass):
                continue

            # skip a class imported from a sibling module
            if klass.__module__ != module.__name__:
                continue

            yield mod_info.name, klass


def _declared_inventory():
    """Return the inventory actually declared, in EXPECTED's shape."""
    found = {}

    for module_name, klass in _iter_config_dataclasses():
        for field_name, spec in config_interpolation.iter_own_specs(klass):
            key = f"{module_name}.{klass.__name__}.{field_name}"
            found[key] = (spec.kinds, spec.arity, spec.shape)

    return found


def _doc_token(key):
    """Return the name under which a field is documented."""
    module_name, klass_name, field_name = key.rsplit(".", 2)
    module = importlib.import_module(f"soliplex.config.{module_name}")
    klass = getattr(module, klass_name)
    spec = config_interpolation.spec_for(klass, field_name)

    return spec.accessor or field_name


def test_declared_inventory_matches_expected():
    found = _declared_inventory()

    assert found == EXPECTED


def test_interpolated_fields_are_documented():
    doc_text = INSTALLATION_DOC.read_text(encoding="utf-8")

    undocumented = sorted(
        _doc_token(key)
        for key, (kinds, _arity, _shape) in EXPECTED.items()
        if kinds is not None and f"`{_doc_token(key)}`" not in doc_text
    )

    assert undocumented == []
