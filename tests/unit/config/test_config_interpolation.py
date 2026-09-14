import dataclasses
from unittest import mock

import pytest

from soliplex.config import interpolation as config_interpolation

MK = config_interpolation.MarkerKind
MA = config_interpolation.MarkerArity
VS = config_interpolation.ValueShape
KEY = config_interpolation.INTERPOLATION_KEY


@dataclasses.dataclass
class _FauxBase:
    inherited_marked: str = config_interpolation.env_embedded_field(
        default=None,
    )
    inherited_plain: str = None


@dataclasses.dataclass
class _FauxDerived(_FauxBase):
    own_marked: str = config_interpolation.secret_whole_field(default=None)
    own_plain: str = None


@dataclasses.dataclass
class _FauxRedeclares(_FauxBase):
    inherited_marked: str = config_interpolation.no_interpolation_field(
        default=None,
    )


@dataclasses.dataclass
class _FauxDeclaresNothing(_FauxBase):
    pass


def test_markerkind_both_is_secret_plus_environment():
    found = MK.SECRET | MK.ENVIRONMENT

    assert found is MK.BOTH


def test_interpolationspec_defaults():
    found = config_interpolation.InterpolationSpec()

    assert found.kinds is None
    assert found.arity is None
    assert found.shape is None
    assert found.public_name is None
    assert found.accessor is None


def test_interpolationspec_config_key():
    found = config_interpolation.InterpolationSpec(public_name="owner")

    assert found.config_key == "owner"


@pytest.mark.parametrize(
    "kinds, arity, shape",
    [
        (None, None, None),
        (MK.BOTH, MA.EMBEDDED, VS.SCALAR),
        (MK.BOTH, MA.EMBEDDED, VS.MAPPING),
        (MK.SECRET, MA.WHOLE_REQUIRED, VS.SCALAR),
        (MK.SECRET, MA.WHOLE_OPTIONAL, VS.SCALAR),
        (MK.SECRET, MA.EMBEDDED, VS.SCALAR),
        (MK.ENVIRONMENT, MA.WHOLE_OPTIONAL, VS.SCALAR),
        (MK.ENVIRONMENT, MA.EMBEDDED, VS.SEQUENCE),
    ],
)
def test_interpolationspec_w_reachable_combination(kinds, arity, shape):
    found = config_interpolation.InterpolationSpec(
        kinds=kinds,
        arity=arity,
        shape=shape,
    )

    assert found.kinds is kinds
    assert found.arity is arity
    assert found.shape is shape


@pytest.mark.parametrize("arity", list(MA))
def test_interpolationspec_literal_w_arity(arity):
    with pytest.raises(
        config_interpolation.LiteralFieldCannotTakeArity
    ) as exc_info:
        config_interpolation.InterpolationSpec(arity=arity)

    assert exc_info.value.arity is arity


@pytest.mark.parametrize("shape", list(VS))
def test_interpolationspec_literal_w_shape(shape):
    with pytest.raises(
        config_interpolation.LiteralFieldCannotTakeShape
    ) as exc_info:
        config_interpolation.InterpolationSpec(shape=shape)

    assert exc_info.value.shape is shape


@pytest.mark.parametrize("kinds", list(MK))
def test_interpolationspec_w_kinds_wo_arity(kinds):
    with pytest.raises(
        config_interpolation.InterpolatedFieldRequiresArity
    ) as exc_info:
        config_interpolation.InterpolationSpec(kinds=kinds)

    assert exc_info.value.kinds is kinds


@pytest.mark.parametrize("kinds", list(MK))
def test_interpolationspec_w_kinds_wo_shape(kinds):
    with pytest.raises(
        config_interpolation.InterpolatedFieldRequiresShape
    ) as exc_info:
        config_interpolation.InterpolationSpec(
            kinds=kinds,
            arity=MA.EMBEDDED,
        )

    assert exc_info.value.kinds is kinds


@pytest.mark.parametrize("arity", [MA.WHOLE_REQUIRED, MA.WHOLE_OPTIONAL])
def test_interpolationspec_w_both_kinds_and_whole_arity(arity):
    with pytest.raises(
        config_interpolation.WholeFieldsCannotSpecifyBothKinds
    ) as exc_info:
        config_interpolation.InterpolationSpec(
            kinds=MK.BOTH,
            arity=arity,
            shape=VS.SCALAR,
        )

    assert exc_info.value.arity is arity


def test_interpolated_field_defaults():
    found = config_interpolation.interpolated_field()

    spec = found.metadata[KEY]
    assert spec.kinds is None
    assert spec.arity is None
    assert spec.shape is None
    assert found.default is dataclasses.MISSING


def test_interpolated_field_forwards_dataclass_kw():
    found = config_interpolation.interpolated_field(default=None, repr=False)

    assert found.default is None
    assert found.repr is False


def test_interpolated_field_w_names():
    found = config_interpolation.interpolated_field(
        public_name="owner",
        accessor="owner",
    )

    spec = found.metadata[KEY]
    assert spec.public_name == "owner"
    assert spec.accessor == "owner"


def test_interpolated_field_merges_supplied_metadata():
    found = config_interpolation.interpolated_field(
        metadata={"other": "kept"},
    )

    assert found.metadata["other"] == "kept"
    assert KEY in found.metadata


def test_no_interpolation_field():
    found = config_interpolation.no_interpolation_field(default="prose")

    spec = found.metadata[KEY]
    assert spec.kinds is None
    assert spec.arity is None
    assert spec.shape is None
    assert found.default == "prose"


@pytest.mark.parametrize(
    "factory_name, exp_kinds, exp_arity, exp_shape",
    [
        (
            "secret_whole_field",
            MK.SECRET,
            MA.WHOLE_REQUIRED,
            VS.SCALAR,
        ),
        (
            "secret_whole_or_literal_field",
            MK.SECRET,
            MA.WHOLE_OPTIONAL,
            VS.SCALAR,
        ),
        (
            "secret_embedded_field",
            MK.SECRET,
            MA.EMBEDDED,
            VS.SCALAR,
        ),
        (
            "env_whole_or_literal_field",
            MK.ENVIRONMENT,
            MA.WHOLE_OPTIONAL,
            VS.SCALAR,
        ),
        (
            "env_embedded_field",
            MK.ENVIRONMENT,
            MA.EMBEDDED,
            VS.SCALAR,
        ),
        (
            "both_embedded_field",
            MK.BOTH,
            MA.EMBEDDED,
            VS.SCALAR,
        ),
    ],
)
def test_field_shorthand(factory_name, exp_kinds, exp_arity, exp_shape):
    factory = getattr(config_interpolation, factory_name)

    found = factory(default=None)

    spec = found.metadata[KEY]
    assert spec.kinds is exp_kinds
    assert spec.arity is exp_arity
    assert spec.shape is exp_shape
    assert found.default is None


@pytest.mark.parametrize(
    "shape, default_factory",
    [
        (VS.SEQUENCE, list),
        (VS.MAPPING, dict),
    ],
)
def test_field_shorthand_overrides_scalar_shape(shape, default_factory):
    factory = config_interpolation.both_embedded_field

    found = factory(shape=shape, default_factory=default_factory)

    spec = found.metadata[KEY]
    assert spec.shape is shape
    assert spec.kinds is MK.BOTH
    assert spec.arity is MA.EMBEDDED
    assert found.default_factory is default_factory


def test__as_class_w_class():
    found = config_interpolation._as_class(_FauxDerived)

    assert found is _FauxDerived


def test__as_class_w_instance():
    found = config_interpolation._as_class(_FauxDerived())

    assert found is _FauxDerived


def test_spec_for_annotated_field():
    found = config_interpolation.spec_for(_FauxDerived, "own_marked")

    assert found.kinds is MK.SECRET
    assert found.arity is MA.WHOLE_REQUIRED


def test_spec_for_unannotated_field():
    found = config_interpolation.spec_for(_FauxDerived, "own_plain")

    assert found is None


def test_spec_for_w_instance():
    found = config_interpolation.spec_for(_FauxDerived(), "own_marked")

    assert found.kinds is MK.SECRET


def test_spec_for_unknown_field():
    with pytest.raises(config_interpolation.NoSuchField) as exc_info:
        config_interpolation.spec_for(_FauxDerived, "nonesuch")

    found = exc_info.value
    assert found.klass is _FauxDerived
    assert found.field_name == "nonesuch"
    assert "nonesuch" in str(found)


def test_iter_specs_includes_inherited():
    found = dict(config_interpolation.iter_specs(_FauxDerived))

    assert sorted(found) == ["inherited_marked", "own_marked"]


def test_iter_own_specs_skips_inherited():
    found = dict(config_interpolation.iter_own_specs(_FauxDerived))

    assert sorted(found) == ["own_marked"]


def test_iter_own_specs_counts_a_redeclared_field_as_own():
    found = dict(config_interpolation.iter_own_specs(_FauxRedeclares))

    assert sorted(found) == ["inherited_marked"]
    assert found["inherited_marked"].kinds is None


def test_iter_own_specs_w_class_declaring_nothing():
    found = dict(config_interpolation.iter_own_specs(_FauxDeclaresNothing))

    assert found == {}


def test__own_field_names():
    found = config_interpolation._own_field_names(_FauxDerived)

    assert found == {"own_marked", "own_plain"}


@dataclasses.dataclass
class _FauxOwned:
    """A config carrying an installation config, as child configs do."""

    secret_embedded: str = config_interpolation.secret_embedded_field(
        default=None,
    )
    secret_whole: str = config_interpolation.secret_whole_field(default=None)
    secret_or_literal: str = (
        config_interpolation.secret_whole_or_literal_field(default=None)
    )
    env_embedded: str = config_interpolation.env_embedded_field(default=None)
    env_or_literal: str = config_interpolation.env_whole_or_literal_field(
        default=None,
    )
    both_embedded: str = config_interpolation.both_embedded_field(
        default=None,
    )
    both_sequence: list = config_interpolation.both_embedded_field(
        shape=VS.SEQUENCE,
        default_factory=list,
    )
    both_mapping: dict = config_interpolation.both_embedded_field(
        shape=VS.MAPPING,
        default_factory=dict,
    )
    literal: str = config_interpolation.no_interpolation_field(default=None)
    unannotated: str = None
    _installation_config: object = None


@dataclasses.dataclass
class _FauxSelfOwned:
    """A config resolving its own fields, as InstallationConfig does."""

    both_embedded: str = config_interpolation.both_embedded_field(
        default=None,
    )


def _faux_installation_config():
    return mock.Mock(
        spec_set=[
            "get_environment",
            "get_secret",
            "interpolate",
            "interpolate_environment",
            "interpolate_secrets",
        ]
    )


def test_resolve_field_secret_embedded():
    i_config = _faux_installation_config()
    config = _FauxOwned(
        secret_embedded="pre secret:NAME post",
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "secret_embedded")

    assert found is i_config.interpolate_secrets.return_value
    i_config.interpolate_secrets.assert_called_once_with(
        "pre secret:NAME post"
    )


def test_resolve_field_secret_whole_required():
    i_config = _faux_installation_config()
    config = _FauxOwned(
        secret_whole="secret:NAME",
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "secret_whole")

    assert found is i_config.get_secret.return_value
    i_config.get_secret.assert_called_once_with("secret:NAME")


def test_resolve_field_secret_whole_optional_w_marker():
    i_config = _faux_installation_config()
    config = _FauxOwned(
        secret_or_literal="secret:NAME",
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "secret_or_literal")

    assert found is i_config.get_secret.return_value


def test_resolve_field_secret_whole_optional_wo_marker():
    i_config = _faux_installation_config()
    config = _FauxOwned(
        secret_or_literal="a literal secret",
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "secret_or_literal")

    assert found == "a literal secret"
    i_config.get_secret.assert_not_called()


def test_resolve_field_environment_embedded():
    i_config = _faux_installation_config()
    config = _FauxOwned(
        env_embedded="https://env:HOST/x",
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "env_embedded")

    assert found is i_config.interpolate_environment.return_value
    i_config.interpolate_environment.assert_called_once_with(
        "https://env:HOST/x"
    )


def test_resolve_field_environment_whole_optional_w_marker():
    i_config = _faux_installation_config()
    config = _FauxOwned(
        env_or_literal="env:SOME_NAME",
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "env_or_literal")

    assert found is i_config.get_environment.return_value
    i_config.get_environment.assert_called_once_with("SOME_NAME")


def test_resolve_field_environment_whole_optional_wo_marker():
    i_config = _faux_installation_config()
    config = _FauxOwned(
        env_or_literal="a literal value",
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "env_or_literal")

    assert found == "a literal value"
    i_config.get_environment.assert_not_called()


def test_resolve_field_both_embedded():
    i_config = _faux_installation_config()
    config = _FauxOwned(
        both_embedded="pg://u:secret:PW@env:HOST/db",
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "both_embedded")

    assert found is i_config.interpolate.return_value


def test_resolve_field_sequence_shape():
    i_config = _faux_installation_config()
    i_config.interpolate.side_effect = lambda value: f"<{value}>"
    config = _FauxOwned(
        both_sequence=["one", "two"],
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "both_sequence")

    assert found == ["<one>", "<two>"]


def test_resolve_field_mapping_shape_leaves_keys_alone():
    i_config = _faux_installation_config()
    i_config.interpolate.side_effect = lambda value: f"<{value}>"
    config = _FauxOwned(
        both_mapping={"env:KEY": "value"},
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "both_mapping")

    assert found == {"env:KEY": "<value>"}


def test_resolve_field_passes_non_str_through():
    i_config = _faux_installation_config()
    config = _FauxOwned(env_or_literal=5, _installation_config=i_config)

    found = config_interpolation.resolve_field(config, "env_or_literal")

    assert found == 5
    i_config.get_environment.assert_not_called()


def test_resolve_field_literal_field_is_untouched():
    i_config = _faux_installation_config()
    config = _FauxOwned(
        literal="mentions secret:NAME in prose",
        _installation_config=i_config,
    )

    found = config_interpolation.resolve_field(config, "literal")

    assert found == "mentions secret:NAME in prose"
    i_config.interpolate.assert_not_called()


def test_resolve_field_w_unannotated_field():
    config = _FauxOwned(unannotated="whatever")

    with pytest.raises(
        config_interpolation.FieldDeclaresNoInterpolation
    ) as exc_info:
        config_interpolation.resolve_field(config, "unannotated")

    found = exc_info.value
    assert found.klass is _FauxOwned
    assert found.field_name == "unannotated"


def test_resolve_field_wo_installation_config():
    config = _FauxSelfOwned(both_embedded="secret:NAME")

    found = config_interpolation.resolve_field(config, "both_embedded")

    assert found == "secret:NAME"


def test_resolve_field_w_explicit_installation_config():
    i_config = _faux_installation_config()
    config = _FauxSelfOwned(both_embedded="secret:NAME")

    found = config_interpolation.resolve_field(
        config,
        "both_embedded",
        installation_config=i_config,
    )

    assert found is i_config.interpolate.return_value
