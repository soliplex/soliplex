import contextlib
import dataclasses
import pathlib

import pytest
import yaml
from haiku.rag import config as hr_config_module

from soliplex.config import exceptions as config_exc
from soliplex.config import rag as config_rag

rdb_stem_and_override = pytest.raises(config_rag.RagDbStemAndOverrideConflict)
rde_requires_db = pytest.raises(config_rag.RagDbEntryRequiresDatabase)
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
        (False, "testing", "/dev/null", rdb_stem_and_override, None),
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
                "database_names": [expected.resolve().stem],
            }
            assert rdb_config.get_extra_parameters() == expected_ep
        else:
            exc = rlp_which.value
            w_missing = rdb_config.get_extra_parameters()
            (err,) = w_missing["database_names"]
            assert err == f"MISSING: {exc.rag_db_filename.stem}"


def test__rdb_override_path_expands_user(db_rag_path, monkeypatch):
    """A '~' in an override path names the user's home directory.

    Without expansion it would be resolved against the room directory as
    a literal '~', which is never a database.
    """
    # 'expanduser' reads a different variable per platform: 'HOME' on
    # POSIX, 'USERPROFILE' (then 'HOMEDRIVE' + 'HOMEPATH') on Windows,
    # where 'HOME' is ignored outright. Set both so '~' resolves to the
    # fixture directory rather than the real home on either platform.
    monkeypatch.setenv("HOME", str(db_rag_path))
    monkeypatch.setenv("USERPROFILE", str(db_rag_path))
    db_override_path = db_rag_path / "test.lancedb"
    db_override_path.mkdir()

    rdb_config = config_rag._RAGDatabaseBase(
        rag_lancedb_override_path=pathlib.Path("~/test.lancedb"),
        _config_path=db_rag_path / "rooms" / "test" / "room_config.yaml",
    )

    assert rdb_config.rag_lancedb_path == db_override_path.resolve()


@dataclasses.dataclass(kw_only=True)
class _MultiDBConfig(config_rag._RAGConfigBase, config_rag._RAGDatabaseBase):
    """Mirror the bases a real RAG skill / tool config mixes in"""


@pytest.fixture
def stem_environ(installation_config, db_rag_path):
    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_path)}
    installation_config.get_environment = ic_environ.get
    return installation_config


@pytest.fixture
def make_entry(stem_environ, db_rag_path):
    def _make_entry(name, stem=None, mkdir=True):
        stem = name if stem is None else stem

        if mkdir:
            (db_rag_path / f"{stem}.lancedb").mkdir()

        return config_rag.RAGDatabaseEntry(
            name=name,
            rag_lancedb_stem=stem,
            _installation_config=stem_environ,
        )

    return _make_entry


def test__rde_ctor_w_stem(stem_environ, db_rag_path):
    entry = config_rag.RAGDatabaseEntry(
        name="papers",
        rag_lancedb_stem="papers",
        _installation_config=stem_environ,
    )
    expected = db_rag_path / "papers.lancedb"
    expected.mkdir()

    assert isinstance(entry, config_rag.SingleRAGDatabaseProtocol)
    assert entry.rag_lancedb_path == expected.resolve()


@pytest.mark.parametrize("name", [None, "", "   "])
def test__rde_ctor_wo_name(name):
    with pytest.raises(config_rag.RagDbEntryRequiresName):
        config_rag.RAGDatabaseEntry(name=name, rag_lancedb_stem="papers")


def test__rde_ctor_w_nested_databases():
    with pytest.raises(config_rag.RagDbNestedDatabases):
        config_rag.RAGDatabaseEntry(
            name="papers",
            rag_lancedb_stem="papers",
            rag_databases=[
                config_rag.RAGDatabaseEntry(
                    name="wiki",
                    rag_lancedb_stem="wiki",
                ),
            ],
        )


def test__rde_ctor_wo_stem_or_override():
    with rde_requires_db:
        config_rag.RAGDatabaseEntry(name="papers")


@pytest.mark.parametrize(
    "stem, override",
    [
        ("papers", None),
        (None, "../papers.lancedb"),
    ],
)
def test__rde_yaml_roundtrip(installation_config, temp_dir, stem, override):
    config_path = temp_dir / "rooms" / "test" / "room_config.yaml"
    entry_yaml = {"name": "papers"}

    if stem is not None:
        entry_yaml["rag_lancedb_stem"] = stem
    else:
        entry_yaml["rag_lancedb_override_path"] = override

    entry = config_rag.RAGDatabaseEntry.from_yaml(
        installation_config,
        config_path,
        entry_yaml,
    )

    assert entry.name == "papers"
    assert entry._config_path == config_path
    assert entry._installation_config is installation_config

    if override is not None:
        assert entry.rag_lancedb_override_path == pathlib.Path(override)

    assert entry.as_yaml == entry_yaml


@pytest.mark.parametrize("rag_databases", [None, []])
def test_adjust_yaml_rag_databases_wo_entries(
    installation_config,
    temp_dir,
    rag_databases,
):
    """An empty or omitted 'rag_databases' leaves the field at its default"""
    config_dict = {"rag_databases": rag_databases}

    config_rag.adjust_yaml_rag_databases(
        installation_config,
        temp_dir / "room_config.yaml",
        config_dict,
    )

    assert (
        config_rag._RAGDatabaseBase(
            rag_lancedb_stem="papers",
            **config_dict,
        ).rag_databases
        == []
    )


def test_adjust_yaml_rag_databases_w_entries(
    installation_config,
    temp_dir,
    db_rag_path,
):
    (db_rag_path / "papers.lancedb").mkdir()
    config_dict = {
        "rag_databases": [{"name": "papers", "rag_lancedb_stem": "papers"}],
    }

    config_rag.adjust_yaml_rag_databases(
        installation_config,
        temp_dir / "room_config.yaml",
        config_dict,
    )

    (entry,) = config_dict["rag_databases"]
    assert isinstance(entry, config_rag.RAGDatabaseEntry)
    assert entry.name == "papers"


def test__rdb_ctor_w_databases_and_stem(make_entry):
    with pytest.raises(config_rag.RagDbSingleAndMultiConflict):
        config_rag._RAGDatabaseBase(
            rag_lancedb_stem="papers",
            rag_databases=[make_entry("papers")],
        )


def test__rdb_ctor_w_duplicate_database_names(make_entry):
    with pytest.raises(config_rag.RagDbDuplicateDatabaseName):
        config_rag._RAGDatabaseBase(
            rag_databases=[
                make_entry("papers"),
                make_entry("papers", stem="wiki"),
            ],
        )


def test__rdb_lancedb_path_w_databases(make_entry):
    """The single-database path is not a thing when several are named"""
    rdb_config = config_rag._RAGDatabaseBase(
        rag_databases=[make_entry("papers")],
    )

    with pytest.raises(config_rag.RagDbNamesSeveralDatabases):
        _ = rdb_config.rag_lancedb_path


def test__rdb_audit_path_w_single_database(stem_environ, db_rag_path):
    expected = db_rag_path / "papers.lancedb"
    expected.mkdir()
    rdb_config = config_rag._RAGDatabaseBase(
        rag_lancedb_stem="papers",
        _installation_config=stem_environ,
    )

    assert rdb_config.rag_db_audit_path == f"papers={expected.resolve()}"


def test__rdb_audit_path_w_databases(make_entry, db_rag_path):
    papers = db_rag_path / "papers.lancedb"
    wiki = db_rag_path / "wiki.lancedb"
    rdb_config = config_rag._RAGDatabaseBase(
        rag_databases=[make_entry("papers"), make_entry("wiki")],
    )

    assert rdb_config.rag_db_audit_path == (
        f"papers={papers.resolve()}, wiki={wiki.resolve()}"
    )


def test__rdb_extra_parameters_w_databases(make_entry):
    """Every database is named, and a missing one says so"""
    rdb_config = config_rag._RAGDatabaseBase(
        rag_databases=[
            make_entry("papers"),
            make_entry("wiki", mkdir=False),
        ],
    )

    assert rdb_config.get_extra_parameters() == {
        "database_names": ["papers", "MISSING: wiki"],
    }


def test__rdb_lancedb_databases_w_stem(stem_environ, db_rag_path):
    """A config with no 'rag_databases' names its database for the stem"""
    expected = db_rag_path / "papers.lancedb"
    expected.mkdir()
    rdb_config = config_rag._RAGDatabaseBase(
        rag_lancedb_stem="papers",
        _installation_config=stem_environ,
    )

    assert rdb_config.rag_lancedb_databases == {"papers": expected.resolve()}
    assert rdb_config.get_extra_parameters() == {
        "database_names": ["papers"],
    }


def test__rdb_lancedb_databases_w_databases(make_entry, db_rag_path):
    rdb_config = config_rag._RAGDatabaseBase(
        rag_databases=[make_entry("papers"), make_entry("wiki")],
    )

    assert rdb_config.rag_lancedb_databases == {
        "papers": (db_rag_path / "papers.lancedb").resolve(),
        "wiki": (db_rag_path / "wiki.lancedb").resolve(),
    }


def test__rcb_haiku_rag_config_w_databases(
    stem_environ,
    make_entry,
    temp_dir,
    db_rag_path,
):
    installation_hr_config = hr_config_module.AppConfig()
    stem_environ.haiku_rag_config = installation_hr_config
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    papers = db_rag_path / "papers.lancedb"
    wiki = db_rag_path / "wiki.lancedb"

    config = _MultiDBConfig(
        rag_databases=[make_entry("papers"), make_entry("wiki")],
        _installation_config=stem_environ,
        _config_path=room_config_dir / "room_config.yaml",
    )

    found = config.haiku_rag_config

    assert found.lancedb.databases == {
        "papers": str(papers.resolve()),
        "wiki": str(wiki.resolve()),
    }
    # The installation's own config is never mutated in place.
    assert installation_hr_config.lancedb.databases == {}
    assert config.haiku_rag_config is found


def test__rcb_haiku_rag_config_w_missing_database(
    stem_environ,
    make_entry,
    temp_dir,
):
    stem_environ.haiku_rag_config = hr_config_module.AppConfig()
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)

    config = _MultiDBConfig(
        rag_databases=[make_entry("papers", mkdir=False)],
        _installation_config=stem_environ,
        _config_path=room_config_dir / "room_config.yaml",
    )

    with rdb_not_found:
        _ = config.haiku_rag_config


def _hr_config_naming(**databases):
    return hr_config_module.AppConfig(
        lancedb=hr_config_module.LanceDBConfig(databases=databases),
    )


def _deferring_config(stem_environ, temp_dir, hr_config, **kw):
    stem_environ.haiku_rag_config = hr_config
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True, exist_ok=True)

    return _MultiDBConfig(
        _installation_config=stem_environ,
        _config_path=room_config_dir / "room_config.yaml",
        **kw,
    )


def test__rdb_ctor_wo_stem_or_override():
    """Naming no database defers placement to the haiku.rag config"""
    rdb_config = config_rag._RAGDatabaseBase()

    assert rdb_config.rag_databases == []

    with pytest.raises(config_rag.RagDbNamesNoDatabase):
        _ = rdb_config.rag_lancedb_path


def test__rcb_deferred_databases(stem_environ, temp_dir):
    """A config naming nothing reports what its haiku.rag config places"""
    config = _deferring_config(
        stem_environ,
        temp_dir,
        _hr_config_naming(medic="s3://bucket/medic.lancedb"),
    )

    assert config.rag_lancedb_databases == {
        "medic": "s3://bucket/medic.lancedb",
    }
    assert config.rag_database_names == ["medic"]
    assert config.rag_db_audit_path == "medic=s3://bucket/medic.lancedb"
    assert config.get_extra_parameters() == {"database_names": ["medic"]}


def test__rcb_deferred_databases_several(stem_environ, temp_dir):
    config = _deferring_config(
        stem_environ,
        temp_dir,
        _hr_config_naming(
            medic="s3://bucket/medic.lancedb",
            papers="/data/papers.lancedb",
        ),
    )

    assert config.rag_database_names == ["medic", "papers"]
    assert config.rag_db_audit_path == (
        "medic=s3://bucket/medic.lancedb, papers=/data/papers.lancedb"
    )


def test__rcb_deferred_databases_leaves_config_alone(stem_environ, temp_dir):
    """Placing nothing of its own, the config is passed through as it is"""
    hr_config = _hr_config_naming(medic="s3://bucket/medic.lancedb")
    config = _deferring_config(stem_environ, temp_dir, hr_config)

    assert config.haiku_rag_config.lancedb.databases == {
        "medic": "s3://bucket/medic.lancedb",
    }


def test__rcb_deferred_default_database(stem_environ, temp_dir):
    """Placing nothing anywhere, haiku.rag's default database is the one"""
    hr_config = hr_config_module.AppConfig()
    config = _deferring_config(stem_environ, temp_dir, hr_config)

    expected = hr_config.storage.data_dir / "haiku.rag.lancedb"

    assert config.rag_lancedb_databases == {"haiku.rag": expected}
    assert config.rag_database_names == ["haiku.rag"]


def _placing_config(stem_environ, temp_dir, **kw):
    stem_environ.haiku_rag_config = _hr_config_naming(
        medic="s3://bucket/medic.lancedb"
    )
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True, exist_ok=True)

    return _MultiDBConfig(
        _installation_config=stem_environ,
        _config_path=room_config_dir / "room_config.yaml",
        **kw,
    )


@pytest.mark.parametrize("w_override", [False, True])
def test__rcb_two_placements(stem_environ, db_rag_path, temp_dir, w_override):
    """Naming a database beside a configured one is two placements

    The two sets need not overlap, so both are named.
    """
    (db_rag_path / "blank.lancedb").mkdir()

    if w_override:
        kw = {"rag_lancedb_override_path": str(db_rag_path / "blank.lancedb")}
    else:
        kw = {"rag_lancedb_stem": "blank"}

    config = _placing_config(stem_environ, temp_dir, **kw)

    with pytest.raises(config_rag.RagDbTwoPlacements) as exc_info:
        _ = config.haiku_rag_config

    message = str(exc_info.value)
    assert "blank" in message
    assert "medic" in message
    assert "lancedb.databases" in message


def test__rcb_two_placements_wo_local_file(stem_environ, temp_dir):
    """Two placements is the diagnosis even when the named path is absent

    The database named beside a configured one is typically a placeholder
    that was never created, so resolving it first answers the wrong
    question.
    """
    config = _placing_config(stem_environ, temp_dir, rag_lancedb_stem="blank")

    with pytest.raises(config_rag.RagDbTwoPlacements):
        _ = config.haiku_rag_config


def test__rcb_two_placements_w_entries(stem_environ, make_entry, temp_dir):
    config = _placing_config(
        stem_environ, temp_dir, rag_databases=[make_entry("papers")]
    )

    with pytest.raises(config_rag.RagDbTwoPlacements) as exc_info:
        _ = config.haiku_rag_config

    assert "papers" in str(exc_info.value)
