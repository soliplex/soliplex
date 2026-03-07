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
def test__rcb_ctor(
    installation_config,
    temp_dir,
    w_config_path,
    stem,
    override,
    ctor_expectation,
    rlp_expectation,
):
    db_rag_path = temp_dir / "db" / "rag"
    db_rag_path.mkdir(parents=True)

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
        rcb_config = config_rag._RAGConfigBase(**kw)

    if isinstance(ctor_which, str):
        if ctor_which == "stem":
            expected = from_stem
        else:
            expected = from_override

        assert rcb_config._config_path == exp_config_path

        with rlp_expectation as rlp_which:
            found = rcb_config.rag_lancedb_path

        if isinstance(rlp_which, str):
            assert found.resolve() == expected.resolve()

            expected_ep = {
                "rag_lancedb_path": expected.resolve(),
            }
            assert rcb_config.get_extra_parameters() == expected_ep
        else:
            w_missing = rcb_config.get_extra_parameters()
            assert w_missing["rag_lancedb_path"].startswith("MISSING:")


@pytest.mark.parametrize(
    "w_already, w_config_path, w_hr_yaml",
    [
        (False, False, None),
        (False, True, None),
        (False, True, {"environment": "from_room"}),
        (True, False, None),
        (True, True, None),
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
    )
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    hr_config_path = room_config_dir / "haiku.rag.yaml"

    if w_hr_yaml:
        with hr_config_path.open("w") as stream:
            yaml.safe_dump(w_hr_yaml, stream)

    kw = {
        "rag_lancedb_stem": "stem",
        "_installation_config": installation_config,
    }
    if w_already:
        kw["_haiku_rag_config"] = already

    if w_config_path:
        exp_room_config_path = room_config_dir / "room_config.yaml"
        kw["_config_path"] = exp_room_config_path
    else:
        exp_room_config_path = None

    rcb_config = config_rag._RAGConfigBase(**kw)

    if w_already:
        assert rcb_config.haiku_rag_config is already

    else:
        if w_config_path:
            hr_config = rcb_config.haiku_rag_config

            if w_hr_yaml:
                assert hr_config.environment == "from_room"
            else:
                assert hr_config.environment == "from_installation"
        else:
            with no_config_path:
                _ = rcb_config.haiku_rag_config
