"""Declare explicit interpolation contracts for dataclass fields

Config values may carry markers which the installation resolves:
``secret:NAME`` from the installation secrets, and ``env:NAME`` from the
installation environment.

The contract defines for a dataclass field:
- which markers a field interpolates
- whether the interpolation applies to the whole value or segments within it

This module makes that contract a property of the field itself, carried in
``dataclasses.field(metadata=...)``.
"""

import dataclasses
import enum
import functools
import re

#: Key under which an ``InterpolationSpec`` rides in a field's metadata.
#: Namespaced, since ``metadata`` is a shared mapping.
INTERPOLATION_KEY = "soliplex.config.interpolation"

SECRET_PREFIX = "secret:"
SECRET_PATTERN = rf"{SECRET_PREFIX}(?P<secret_name>\w+)"
SECRET_RE = re.compile(SECRET_PATTERN)

ENVIRONMENT_PREFIX = "env:"
ENVIRONMENT_PATTERN = rf"{ENVIRONMENT_PREFIX}(?P<env_name>\w+)"
ENVIRONMENT_RE = re.compile(ENVIRONMENT_PATTERN)


class MarkerKind(enum.Flag):
    """Which marker styles a field honors

    Fields which opt out of interpolation explicitly use ``kinds=None``.
    """

    SECRET = enum.auto()
    ENVIRONMENT = enum.auto()
    BOTH = SECRET | ENVIRONMENT


class MarkerArity(enum.StrEnum):
    """How much of a field's value a marker may occupy"""

    # Zero or more markers may appear anywhere within the value.
    EMBEDDED = "embedded"

    # The whole value must be a single marker; anything else is rejected.
    WHOLE_REQUIRED = "whole_required"

    # The whole value may be a single marker; anything else is a literal.
    WHOLE_OPTIONAL = "whole_optional"


class ValueShape(enum.StrEnum):
    """Where, within a field's value, interpolation applies."""

    # Interpolate a single string value.
    SCALAR = "scalar"

    # Interpolate items in a sequence of strings.
    SEQUENCE = "sequence"

    # Interpolate mapping values; keys are not interpolated.
    MAPPING = "mapping"


class LiteralFieldCannotTakeArity(ValueError):
    def __init__(self, arity: MarkerArity):
        self.arity = arity
        super().__init__("Literal fields cannot take an arity")


class LiteralFieldCannotTakeShape(ValueError):
    def __init__(self, shape: ValueShape):
        self.shape = shape
        super().__init__("Literal fields cannot take a shape")


class WholeFieldsCannotSpecifyBothKinds(ValueError):
    def __init__(self, arity: MarkerArity):
        self.arity = arity
        super().__init__("WHOLE fields cannot take BOTH kinds")


class InterpolatedFieldRequiresArity(ValueError):
    def __init__(self, kinds: MarkerKind):
        self.kinds = kinds
        super().__init__("Interpolated fields require an arity")


class InterpolatedFieldRequiresShape(ValueError):
    def __init__(self, kinds: MarkerKind):
        self.kinds = kinds
        super().__init__("Interpolated fields require a shape")


class FieldDeclaresNoInterpolation(ValueError):
    def __init__(self, klass, field_name):
        self.klass = klass
        self.field_name = field_name
        super().__init__(
            f"No interpolation declared for '{klass.__name__}.{field_name}'"
        )


class NoSuchField(AttributeError):
    """A field name does not name a field of the given dataclass."""

    def __init__(self, klass, field_name):
        self.klass = klass
        self.field_name = field_name
        super().__init__(
            f"'{klass.__name__}' has no field named '{field_name}'"
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class InterpolationSpec:
    """How one config field participates in interpolation.

    ``kinds`` defines the types of interpolation a field supports.

    Free-form fields (e.g., a room description, a system prompt) set
    ``kinds==None`` as a positive declaration: "this field is literal text",
    opting out of being reported for text which merely resembles a marker.

    ``arity`` defines whether a field is interpolated in segments, or
    as a whole value (required), or a whole value (optional).

    ``shape`` defines what elements which are interpolated (a single
    scalar string, the elements of a list of strings, or the string
    values of a mapping).

    ``public_name`` is the YAML key, where it differs from the field name
    (fields may be private, exposed through a property).

    ``accessor`` names that property.

    ``public_name`` and `accessor`` are documentation for operators and
    audit messages; neither is consulted to resolve a value.
    """

    kinds: MarkerKind | None = None
    arity: MarkerArity | None = None
    shape: ValueShape | None = None
    public_name: str | None = None
    accessor: str | None = None

    def __post_init__(self):
        if self.kinds is None:
            if self.arity is not None:
                raise LiteralFieldCannotTakeArity(self.arity)

            if self.shape is not None:
                raise LiteralFieldCannotTakeShape(self.shape)

        else:
            if self.arity is None:
                raise InterpolatedFieldRequiresArity(self.kinds)

            if self.shape is None:
                raise InterpolatedFieldRequiresShape(self.kinds)

            if (
                self.kinds is MarkerKind.BOTH
                and self.arity is not MarkerArity.EMBEDDED
            ):
                raise WholeFieldsCannotSpecifyBothKinds(self.arity)

    @property
    def config_key(self) -> str | None:
        """The YAML key for this field, when it is known."""
        return self.public_name


def interpolated_field(
    *,
    kinds=None,
    arity=None,
    shape=None,
    public_name=None,
    accessor=None,
    **kw,
) -> dataclasses.Field:
    """Return a ``dataclasses.field()`` carrying an ``InterpolationSpec``.

    Remaining keywords are forwarded verbatim, so ``default``,
    ``default_factory``, ``repr`` and ``compare`` behave as usual and a
    field with no default stays required.
    """
    spec = InterpolationSpec(
        kinds=kinds,
        arity=arity,
        shape=shape,
        public_name=public_name,
        accessor=accessor,
    )
    metadata = {**kw.pop("metadata", {}), INTERPOLATION_KEY: spec}

    return dataclasses.field(metadata=metadata, **kw)


def no_interpolation_field(**kw) -> dataclasses.Field:
    """Declare a field as literal text: never resolved, never reported."""
    return interpolated_field(**kw)


# Shorthands for the combinations which actually occur, so declarations
# stay readable.  Each names its sites:
#
#   secret_whole_field       'provider_key', Logfire 'token'
#   secret_whole_or_literal  OIDC 'client_secret'
#   secret_embedded_field    third-party tool configs (e.g. concierge)
#   env_whole_or_literal     the seven Logfire 'env:' fields
#   env_embedded_field       'model_name', 'provider_base_url'
#   both_embedded_field      the four dburis, the MCP toolset fields
secret_whole_field = functools.partial(
    interpolated_field,
    kinds=MarkerKind.SECRET,
    arity=MarkerArity.WHOLE_REQUIRED,
    shape=ValueShape.SCALAR,
)
secret_whole_or_literal_field = functools.partial(
    interpolated_field,
    kinds=MarkerKind.SECRET,
    arity=MarkerArity.WHOLE_OPTIONAL,
    shape=ValueShape.SCALAR,
)
secret_embedded_field = functools.partial(
    interpolated_field,
    kinds=MarkerKind.SECRET,
    arity=MarkerArity.EMBEDDED,
    shape=ValueShape.SCALAR,
)
env_whole_or_literal_field = functools.partial(
    interpolated_field,
    kinds=MarkerKind.ENVIRONMENT,
    arity=MarkerArity.WHOLE_OPTIONAL,
    shape=ValueShape.SCALAR,
)
env_embedded_field = functools.partial(
    interpolated_field,
    kinds=MarkerKind.ENVIRONMENT,
    arity=MarkerArity.EMBEDDED,
    shape=ValueShape.SCALAR,
)
both_embedded_field = functools.partial(
    interpolated_field,
    kinds=MarkerKind.BOTH,
    arity=MarkerArity.EMBEDDED,
    shape=ValueShape.SCALAR,
)


def _as_class(klass_or_instance) -> type:
    if isinstance(klass_or_instance, type):
        return klass_or_instance

    return type(klass_or_instance)


def spec_for(klass_or_instance, field_name) -> InterpolationSpec | None:
    """Return the spec declared for ``field_name``, or ``None``

    Return ``None`` when the field carries no declaration at all,
    a distinct case from a declared-literal field (``kind==None``).

    Raise ``NoSuchField`` when the name does not name a field.
    """
    klass = _as_class(klass_or_instance)

    for field in dataclasses.fields(klass):
        if field.name == field_name:
            return field.metadata.get(INTERPOLATION_KEY)

    raise NoSuchField(klass, field_name)


def iter_specs(klass_or_instance):
    """Yield ``(field_name, spec)`` for each field declaring an interpolation

    Include fields inherited from base classes.
    """
    klass = _as_class(klass_or_instance)

    for field in dataclasses.fields(klass):
        spec = field.metadata.get(INTERPOLATION_KEY)

        if spec is not None:
            yield field.name, spec


def _own_field_names(klass) -> set[str]:
    """Return the names of the fields ``klass`` declares itself

    Skip fields defined in base dataclasses and not re-declared.
    """
    bases = [
        base for base in klass.__mro__[1:] if dataclasses.is_dataclass(base)
    ]

    return {
        field.name
        for field in dataclasses.fields(klass)
        if not any(
            field is base.__dataclass_fields__.get(field.name)
            for base in bases
        )
    }


def iter_own_specs(klass_or_instance):
    """Yield ``(field_name, spec)`` for fields the class declares itself.

    Skip inherited fields which are not re-declared.

    A dataclass which derives from a base which declares one or more
    interpolations is not checkable for interpolations until it declares
    one or more of them itself.
    """
    klass = _as_class(klass_or_instance)
    own = _own_field_names(klass)

    for field_name, spec in iter_specs(klass):
        if field_name in own:
            yield field_name, spec


def _resolve_secret_embedded(installation_config, value):
    return installation_config.interpolate_secrets(value)


def _resolve_secret_whole_required(installation_config, value):
    return installation_config.get_secret(value)


def _resolve_secret_whole_optional(installation_config, value):
    if value.startswith(SECRET_PREFIX):
        return installation_config.get_secret(value)
    else:
        return value


def _resolve_environment_embedded(installation_config, value):
    return installation_config.interpolate_environment(value)


def _resolve_environment_whole_optional(installation_config, value):
    if value.startswith(ENVIRONMENT_PREFIX):
        return installation_config.get_environment(
            value[len(ENVIRONMENT_PREFIX) :]
        )
    else:
        return value


def _resolve_both_embedded(installation_config, value):
    return installation_config.interpolate(value)


_RESOLVERS = {
    (MarkerKind.SECRET, MarkerArity.EMBEDDED): _resolve_secret_embedded,
    (MarkerKind.SECRET, MarkerArity.WHOLE_REQUIRED): (
        _resolve_secret_whole_required
    ),
    (MarkerKind.SECRET, MarkerArity.WHOLE_OPTIONAL): (
        _resolve_secret_whole_optional
    ),
    (MarkerKind.ENVIRONMENT, MarkerArity.EMBEDDED): (
        _resolve_environment_embedded
    ),
    (MarkerKind.ENVIRONMENT, MarkerArity.WHOLE_OPTIONAL): (
        _resolve_environment_whole_optional
    ),
    (MarkerKind.BOTH, MarkerArity.EMBEDDED): _resolve_both_embedded,
}


def _resolve_scalar(resolve, installation_config, value):
    """Resolve one string

    Pass any other value through untouched.
    """

    if not isinstance(value, str):
        return value

    return resolve(installation_config, value)


def _resolve_sequence(resolve, installation_config, value):
    """Resolve items in a sequence of strings

    Pass other items through untouched.
    """

    return [
        _resolve_scalar(resolve, installation_config, item) for item in value
    ]


def _resolve_mapping(resolve, installation_config, value):
    """Resolve string values of a mapping

    Pass other values through untouched.
    """

    return {
        key: _resolve_scalar(resolve, installation_config, item)
        for key, item in value.items()
    }


_RESOLVE_BY_SHAPE = {
    ValueShape.SCALAR: _resolve_scalar,
    ValueShape.SEQUENCE: _resolve_sequence,
    ValueShape.MAPPING: _resolve_mapping,
}


def resolve_field(
    config,
    field_name,
    *,
    installation_config=None,
):
    """Return the value of ``field_name``, with its markers resolved.

    Preserve the declared shape: a sequence field yields a list, a mapping
    field a dict with its keys untouched.  Leave the field itself alone, so
    the stored value keeps its markers.

    Return the stored value unchanged for a field declaring no markers, and
    for one whose config carries no installation config.

    Take ``installation_config`` explicitly for a config which is not a
    child of one -- ``InstallationConfig`` resolves its own fields.
    """
    spec = spec_for(config, field_name)

    if spec is None:
        raise FieldDeclaresNoInterpolation(_as_class(config), field_name)

    value = getattr(config, field_name)

    if spec.kinds is None:
        return value

    if installation_config is None:
        installation_config = getattr(config, "_installation_config", None)

    if installation_config is None:
        return value

    resolver = _RESOLVERS[(spec.kinds, spec.arity)]

    by_shape = _RESOLVE_BY_SHAPE[spec.shape]

    return by_shape(resolver, installation_config, value)
