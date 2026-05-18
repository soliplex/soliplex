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


@pytest.fixture(autouse=True)
def _no_aws_creds(monkeypatch):
    """Don't probe botocore from these tests.

    The default returns {} so the S3-URI tests don't accidentally
    populate storage_options from the dev machine's credentials.
    Tests that need a populated dict patch this fixture's target.
    """
    monkeypatch.setattr(
        "soliplex.aws_credentials.resolve_aws_storage_options",
        lambda: {},
    )


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


_S3_URI = "s3://enfold-lancedb-test/lancedb/soliplex_docs.lancedb"


@pytest.mark.parametrize(
    "uri",
    [
        "s3://bucket/path.lancedb",
        "gs://bucket/path.lancedb",
        "az://account/container/path.lancedb",
        "hdfs://namenode:9000/path.lancedb",
        "db://my-cloud-db",
    ],
)
def test__rcb_uri_override_skips_local_path_check(
    installation_config, temp_dir, uri
):
    """rag_lancedb_override_path with a URI scheme must not be resolved as
    a local path; rag_lancedb_path returns None and rag_lancedb_uri
    surfaces the URI for downstream display / config injection.
    """
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    config_path = room_config_dir / "room_config.yaml"

    rcb_config = config_rag._RAGConfigBase(
        rag_lancedb_override_path=uri,
        _installation_config=installation_config,
        _config_path=config_path,
    )

    assert rcb_config.rag_lancedb_uri == uri
    assert rcb_config.rag_lancedb_path is None
    assert rcb_config.get_extra_parameters() == {"rag_lancedb_path": uri}


def test__rcb_uri_override_injects_lancedb_uri_into_haiku_rag_config(
    installation_config, temp_dir
):
    """When override is a URI, haiku_rag_config.lancedb.uri must equal it,
    overlaid on top of the installation base config and any room-level
    haiku.rag.yaml.
    """
    installation_config.haiku_rag_config = hr_config_module.AppConfig(
        environment="from_installation",
    )
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    config_path = room_config_dir / "room_config.yaml"

    rcb_config = config_rag._RAGConfigBase(
        rag_lancedb_override_path=_S3_URI,
        _installation_config=installation_config,
        _config_path=config_path,
    )

    hr_config = rcb_config.haiku_rag_config
    assert hr_config.lancedb.uri == _S3_URI
    assert hr_config.environment == "from_installation"


@pytest.mark.parametrize(
    "base, expected",
    [
        (
            "s3://bucket/lancedbs",
            "s3://bucket/lancedbs/docs.lancedb",
        ),
        (
            "s3://bucket/lancedbs/",
            "s3://bucket/lancedbs/docs.lancedb",
        ),
        (
            "gs://bucket",
            "gs://bucket/docs.lancedb",
        ),
    ],
)
def test__rcb_stem_with_uri_rag_lance_db_path(
    installation_config, temp_dir, base, expected
):
    """When RAG_LANCE_DB_PATH is a URI base, stem mode joins onto it
    instead of resolving as a local path. rag_lancedb_path returns None;
    rag_lancedb_uri returns the joined URI.
    """
    installation_config.get_environment = {
        "RAG_LANCE_DB_PATH": base,
    }.get
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    config_path = room_config_dir / "room_config.yaml"

    rcb_config = config_rag._RAGConfigBase(
        rag_lancedb_stem="docs",
        _installation_config=installation_config,
        _config_path=config_path,
    )

    assert rcb_config.rag_lancedb_uri == expected
    assert rcb_config.rag_lancedb_path is None
    assert rcb_config.get_extra_parameters() == {"rag_lancedb_path": expected}


def test__rcb_stem_with_uri_injects_lancedb_uri_into_haiku_rag_config(
    installation_config, temp_dir
):
    installation_config.haiku_rag_config = hr_config_module.AppConfig(
        environment="from_installation",
    )
    installation_config.get_environment = {
        "RAG_LANCE_DB_PATH": "s3://bucket/lancedbs",
    }.get
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    config_path = room_config_dir / "room_config.yaml"

    rcb_config = config_rag._RAGConfigBase(
        rag_lancedb_stem="docs",
        _installation_config=installation_config,
        _config_path=config_path,
    )

    hr_config = rcb_config.haiku_rag_config
    assert hr_config.lancedb.uri == "s3://bucket/lancedbs/docs.lancedb"
    assert hr_config.environment == "from_installation"


def test__rcb_uri_override_wins_over_room_haiku_rag_yaml_lancedb_uri(
    installation_config, temp_dir
):
    installation_config.haiku_rag_config = hr_config_module.AppConfig()

    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    hr_config_path = room_config_dir / "haiku.rag.yaml"
    with hr_config_path.open("w") as stream:
        yaml.safe_dump(
            {
                "lancedb": {
                    "uri": "s3://different-bucket/old.lancedb",
                    "region": "us-west-2",
                }
            },
            stream,
        )
    config_path = room_config_dir / "room_config.yaml"

    rcb_config = config_rag._RAGConfigBase(
        rag_lancedb_override_path=_S3_URI,
        _installation_config=installation_config,
        _config_path=config_path,
    )

    hr_config = rcb_config.haiku_rag_config
    assert hr_config.lancedb.uri == _S3_URI
    # Other lancedb sub-fields from room yaml are preserved.
    assert hr_config.lancedb.region == "us-west-2"


_FAKE_CREDS = {
    "aws_access_key_id": "AK",
    "aws_secret_access_key": "SK",
    "region": "us-east-1",
}


def _build_s3_rcb(installation_config, temp_dir):
    installation_config.haiku_rag_config = hr_config_module.AppConfig()
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    return config_rag._RAGConfigBase(
        rag_lancedb_override_path=_S3_URI,
        _installation_config=installation_config,
        _config_path=room_config_dir / "room_config.yaml",
    )


def test__rcb_s3_uri_overlays_storage_options_from_botocore(
    installation_config, temp_dir, monkeypatch
):
    """For an s3:// URI with no user-provided storage_options, AWS creds
    are resolved per access and overlaid as lancedb.storage_options.
    """
    monkeypatch.setattr(
        "soliplex.aws_credentials.resolve_aws_storage_options",
        lambda: _FAKE_CREDS,
    )

    rcb_config = _build_s3_rcb(installation_config, temp_dir)

    hr_config = rcb_config.haiku_rag_config
    assert hr_config.lancedb.uri == _S3_URI
    assert hr_config.lancedb.storage_options == _FAKE_CREDS


def test__rcb_s3_uri_no_creds_available_leaves_storage_options_empty(
    installation_config, temp_dir
):
    """When botocore yields {} (no creds, or extra not installed), the
    returned config has no storage_options. lance will then fall back to
    its own credential chain (env vars, IMDS).
    """
    # autouse _no_aws_creds already returns {}
    rcb_config = _build_s3_rcb(installation_config, temp_dir)

    hr_config = rcb_config.haiku_rag_config
    assert hr_config.lancedb.uri == _S3_URI
    assert hr_config.lancedb.storage_options == {}


def test__rcb_s3_uri_user_storage_options_not_overwritten(
    installation_config, temp_dir, monkeypatch
):
    """If the user has set storage_options in haiku.rag.yaml, soliplex
    does NOT overwrite them — the user retains full control over AWS
    credentials, endpoint, and other lance/object_store options.
    """
    user_storage = {
        "aws_access_key_id": "USER_KEY",
        "aws_secret_access_key": "USER_SECRET",
        "endpoint": "https://minio.example.com",
        "allow_http": "true",
    }
    installation_config.haiku_rag_config = hr_config_module.AppConfig()
    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)
    with (room_config_dir / "haiku.rag.yaml").open("w") as stream:
        yaml.safe_dump({"lancedb": {"storage_options": user_storage}}, stream)

    monkeypatch.setattr(
        "soliplex.aws_credentials.resolve_aws_storage_options",
        lambda: _FAKE_CREDS,
    )

    rcb_config = config_rag._RAGConfigBase(
        rag_lancedb_override_path=_S3_URI,
        _installation_config=installation_config,
        _config_path=room_config_dir / "room_config.yaml",
    )

    hr_config = rcb_config.haiku_rag_config
    assert hr_config.lancedb.uri == _S3_URI
    assert hr_config.lancedb.storage_options == user_storage


def test__rcb_non_s3_uri_does_not_resolve_aws_creds(
    installation_config, temp_dir
):
    """gs:// / az:// / hdfs:// / db:// URIs must NOT trigger the AWS
    credential resolver — they have their own credential mechanisms.
    """
    resolver = pytest.MonkeyPatch()
    calls = []
    resolver.setattr(
        "soliplex.aws_credentials.resolve_aws_storage_options",
        lambda: calls.append("called") or {},
    )

    try:
        installation_config.haiku_rag_config = hr_config_module.AppConfig()
        room_config_dir = temp_dir / "rooms" / "test"
        room_config_dir.mkdir(parents=True)
        rcb_config = config_rag._RAGConfigBase(
            rag_lancedb_override_path="gs://bucket/path.lancedb",
            _installation_config=installation_config,
            _config_path=room_config_dir / "room_config.yaml",
        )

        _ = rcb_config.haiku_rag_config
    finally:
        resolver.undo()

    assert calls == []


def test__rcb_s3_uri_creds_resolved_per_access(
    installation_config, temp_dir, monkeypatch
):
    """Each haiku_rag_config access re-resolves creds, so a refreshed
    botocore session (SSO/STS/IMDS) is picked up without rebuilding the
    config object.
    """
    sequence = [
        {
            "aws_access_key_id": "AK1",
            "aws_secret_access_key": "SK1",
        },
        {
            "aws_access_key_id": "AK2",
            "aws_secret_access_key": "SK2",
        },
    ]
    iter_seq = iter(sequence)
    monkeypatch.setattr(
        "soliplex.aws_credentials.resolve_aws_storage_options",
        lambda: next(iter_seq),
    )

    rcb_config = _build_s3_rcb(installation_config, temp_dir)

    first = rcb_config.haiku_rag_config
    second = rcb_config.haiku_rag_config

    assert first.lancedb.storage_options == sequence[0]
    assert second.lancedb.storage_options == sequence[1]


def test__rcb_haiku_rag_config_preset_object_skipped_for_overlay(
    installation_config, temp_dir
):
    """If '_haiku_rag_config' is pre-populated with something that has no
    'lancedb' attribute (existing test-fixture pattern), the cred overlay
    is skipped and the preset value is returned as-is.
    """
    already = object()

    room_config_dir = temp_dir / "rooms" / "test"
    room_config_dir.mkdir(parents=True)

    rcb_config = config_rag._RAGConfigBase(
        rag_lancedb_stem="stem",
        _installation_config=installation_config,
        _config_path=room_config_dir / "room_config.yaml",
        _haiku_rag_config=already,
    )

    assert rcb_config.haiku_rag_config is already
