import contextlib

import pytest
import yaml
from haiku.rag import config as hr_config_module

from soliplex.config import exceptions as config_exc
from soliplex.config import rag as config_rag

rdb_exactly_one = pytest.raises(config_rag.RagDbExactlyOneOfStemOrOverride)
rdb_not_found = pytest.raises(config_rag.RagDbFileNotFound)
no_config_path = pytest.raises(config_exc.NoConfigPath)
ok_stem = contextlib.nullcontext("stem")
ok_ovr = contextlib.nullcontext("override")


@pytest.mark.parametrize(
    "base, derived, expected",
    [
        ({}, {}, {}),
        ({"foo": "bar"}, {}, {"foo": "bar"}),
        ({}, {"foo": "bar"}, {"foo": "bar"}),
        ({"foo": "bar"}, {"foo": "qux"}, {"foo": "qux"}),
        ({"foo": {"spam": "bar"}}, {}, {"foo": {"spam": "bar"}}),
        ({}, {"foo": {"spam": "bar"}}, {"foo": {"spam": "bar"}}),
        (
            {"foo": {"spam": "flotz"}},
            {"foo": {"spam": "bar"}},
            {"foo": {"spam": "bar"}},
        ),
        (
            {"foo": {"qux": "baz", "spam": "flotz"}, "gork": "naff"},
            {"foo": {"spam": "bar"}},
            {"foo": {"qux": "baz", "spam": "bar"}, "gork": "naff"},
        ),
    ],
)
def test__deep_merge(base, derived, expected):
    found = config_rag._deep_merge(base, derived)

    assert found == expected


@pytest.mark.parametrize(
    "w_already, w_config_path, w_hr_yaml",
    [
        (False, False, {}),
        (False, True, {}),
        (False, True, {"environment": "from_room"}),
        (False, True, {"prompts": {"domain_preamble": "from_room"}}),
        (True, False, {}),
        (True, True, {}),
        (True, True, {"environment": "from_room"}),
    ],
)
def test__rcb_haiku_rag_config(
    installation_config,
    temp_dir,
    w_already,
    w_config_path,
    w_hr_yaml,
):
    already = object()

    installation_config.haiku_rag_config = hr_config_module.AppConfig(
        environment="from_installation",
        prompts=hr_config_module.PromptsConfig(
            domain_preamble="from_installation",
            picture_description="from_installation",
        ),
    )
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    hr_config_path = room_config_dir / "haiku.rag.yaml"

    if w_hr_yaml:
        with hr_config_path.open("w") as stream:
            yaml.safe_dump(w_hr_yaml, stream)

    kw = {"_installation_config": installation_config}

    if w_already:
        kw["_haiku_rag_config"] = already

    if w_config_path:
        exp_room_config_path = room_config_dir / "room_config.yaml"
        kw["_config_path"] = exp_room_config_path
    else:
        exp_room_config_path = None

    rcb_config = config_rag._RAGConfigBase(**kw)
    assert isinstance(rcb_config, config_rag.RAGConfigProtocol)

    if w_already:
        assert rcb_config.haiku_rag_config is already

    else:
        if w_config_path:
            hr_config = rcb_config.haiku_rag_config

            if "environment" in w_hr_yaml:
                assert hr_config.environment == "from_room"
            else:
                assert hr_config.environment == "from_installation"

            if "prompts" in w_hr_yaml:
                assert hr_config.prompts.domain_preamble == "from_room"
            else:
                assert hr_config.prompts.domain_preamble == "from_installation"

            assert hr_config.prompts.picture_description == "from_installation"

        else:
            with no_config_path:
                _ = rcb_config.haiku_rag_config


@pytest.fixture
def db_rag_path(temp_dir):
    result = temp_dir / "db" / "rag"
    result.mkdir(parents=True)
    return result


@pytest.mark.parametrize(
    "w_config_path, stem, override, ctor_expectation, rlp_expectation",
    [
        (False, None, None, rdb_exactly_one, None),
        (False, "testing", "/dev/null", rdb_exactly_one, None),
        (False, "bogus", None, ok_stem, rdb_not_found),
        (False, "testing", None, ok_stem, ok_stem),
        (False, None, "./override", ok_ovr, rdb_not_found),
        (True, None, "./override", ok_ovr, ok_ovr),
    ],
)
def test__rdb_ctor(
    installation_config,
    temp_dir,
    db_rag_path,
    w_config_path,
    stem,
    override,
    ctor_expectation,
    rlp_expectation,
):
    if stem not in (None, "bogus"):
        from_stem = db_rag_path / f"{stem}.lancedb"
        from_stem.mkdir()
    else:
        from_stem = None

    if override is not None:
        from_override = temp_dir / "rooms" / "test" / override
        if not from_override.exists():
            from_override.mkdir(parents=True)
    else:
        from_override = None

    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_path)}
    installation_config.get_environment = ic_environ.get

    kw = {"_installation_config": installation_config}

    if w_config_path:
        exp_config_path = kw["_config_path"] = (
            temp_dir / "rooms" / "test" / "room_config.yaml"
        )
    else:
        exp_config_path = None

    if stem is not None:
        kw["rag_lancedb_stem"] = stem

    if override is not None:
        kw["rag_lancedb_override_path"] = override

    with ctor_expectation as ctor_which:
        rdb_config = config_rag._RAGDatabaseBase(**kw)

    if isinstance(ctor_which, str):
        assert isinstance(rdb_config, config_rag.SingleRAGDatabaseProtocol)

        if ctor_which == "stem":
            expected = from_stem
        else:
            expected = from_override

        assert rdb_config._config_path == exp_config_path

        with rlp_expectation as rlp_which:
            found = rdb_config.rag_lancedb_path

        if isinstance(rlp_which, str):
            assert found.resolve() == expected.resolve()

            expected_ep = {
                "rag_lancedb_path": expected.resolve(),
            }
            assert rdb_config.get_extra_parameters() == expected_ep
        else:
            w_missing = rdb_config.get_extra_parameters()
            assert w_missing["rag_lancedb_path"].startswith("MISSING:")


@pytest.mark.parametrize(
    "w_kw, db_path_parent, db_path_name, expectation",
    [
        (
            {},
            None,
            None,
            pytest.raises(config_exc.FromYamlException),
        ),
        (
            {"rag_lancedb_stem": "stem"},
            "DB_RAG_PATH",
            "stem.lancedb",
            contextlib.nullcontext(),
        ),
        (
            {"rag_lancedb_override_path": "override.lancedb"},
            "TEMP_DIR",
            "override.lancedb",
            contextlib.nullcontext(),
        ),
    ],
)
def test_rdc_from_yaml(
    temp_dir,
    db_rag_path,
    installation_config,
    w_kw,
    db_path_parent,
    db_path_name,
    expectation,
):
    w_kw = w_kw.copy()

    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_path)}
    installation_config.get_environment = ic_environ.get

    if db_path_parent == "DB_RAG_PATH":
        exp_path = db_rag_path / db_path_name
    elif db_path_parent == "TEMP_DIR":
        exp_path = temp_dir / db_path_name
        w_kw["rag_lancedb_override_path"] = str(temp_dir / "override.lancedb")
    else:
        exp_path = None

    if exp_path is not None:
        exp_path.mkdir()

    with expectation as expected:
        found = config_rag.RAGDatabaseConfig.from_yaml(
            installation_config=installation_config,
            config_path=temp_dir,
            config_dict=w_kw,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found.rag_lancedb_path == exp_path


@pytest.mark.parametrize(
    "w_kw, db_path_parent, db_path_name",
    [
        ({"rag_lancedb_stem": "stem"}, "DB_RAG_PATH", "stem.lancedb"),
        (
            {"rag_lancedb_override_path": "override.lancedb"},
            "TEMP_DIR",
            "override.lancedb",
        ),
    ],
)
def test_rdc_as_yaml(
    temp_dir,
    db_rag_path,
    w_kw,
    db_path_parent,
    db_path_name,
):
    expected = w_kw.copy()
    w_kw = w_kw.copy()

    if db_path_parent == "DB_RAG_PATH":
        exp_path = db_rag_path / db_path_name
    else:  # TEMP_DIR
        exp_path = temp_dir / db_path_name
        real_override_path = temp_dir / "override.lancedb"
        w_kw["rag_lancedb_override_path"] = real_override_path
        expected["rag_lancedb_override_path"] = str(real_override_path)

    exp_path.mkdir()

    rdc = config_rag.RAGDatabaseConfig(**w_kw)

    found = rdc.as_yaml

    assert found == expected


def test__mrdb_ctor_wo_db_configs():
    mrdb_config = config_rag._MultiRAGDatabasesBase()

    assert isinstance(mrdb_config, config_rag.MultipleRAGDatabasesProtocol)
    assert mrdb_config.rag_lancedb_paths == []


def test__mrdb_ctor_w_db_configs(installation_config, temp_dir, db_rag_path):
    db_override_path = temp_dir / "override.lancedb"
    db_override_path.mkdir()
    db_stem_path = db_rag_path / "stem.lancedb"
    db_stem_path.mkdir()

    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_path)}
    installation_config.get_environment = ic_environ.get

    w_override = config_rag.RAGDatabaseConfig(
        rag_lancedb_override_path=db_override_path,
        _installation_config=installation_config,
        _config_path=temp_dir,
    )
    w_stem = config_rag.RAGDatabaseConfig(
        rag_lancedb_stem="stem",
        _installation_config=installation_config,
        _config_path=temp_dir,
    )
    mrdb_config = config_rag._MultiRAGDatabasesBase(
        db_configs=[w_override, w_stem],
    )

    assert isinstance(mrdb_config, config_rag.MultipleRAGDatabasesProtocol)
    assert mrdb_config.rag_lancedb_paths == [
        db_override_path,
        db_stem_path,
    ]
