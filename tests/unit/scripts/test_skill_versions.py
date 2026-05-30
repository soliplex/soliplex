"""Unit tests for the bundled ``scripts/skill_versions.py`` helper.

The script ships inside the generated ``soliplex-docs`` skill and is not part
of the importable ``soliplex`` package, so it is loaded here by file path.
Tests are hermetic: published versions are served from local ``file://``
tarballs and the GitHub-facing seams are replaced with mock fixtures (see
``Fixtures`` below) -- no network.

Each test is laid out in three blank-line-separated phases -- setup, then the
single call under test (the "act"), then the assertions -- and performs that
act exactly once (cases that would repeat it are parametrized or split).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import pathlib
import tarfile
from unittest import mock

import pytest

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "scripts"
    / "docs_skill_template"
    / "scripts"
    / "skill_versions.py"
)
_spec = importlib.util.spec_from_file_location("skill_versions", _MODULE_PATH)
sv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sv)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _write_skill(
    root: pathlib.Path,
    *,
    commit: str,
    refs: dict[str, str],
) -> pathlib.Path:
    """Build a skill tree at ``root`` and return it."""
    references = root / "references"
    references.mkdir(parents=True)
    for name, text in refs.items():
        (references / name).write_text(text, encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "skill_versions.py").write_text("# stub\n", encoding="utf-8")
    (root / "SKILL.md").write_text(
        "---\n"
        "name: soliplex-docs\n"
        "metadata:\n"
        f'  source_commit: "{commit}"\n'
        "---\n"
        "# Soliplex documentation\n",
        encoding="utf-8",
    )
    return root


def _make_tarball(tarball: pathlib.Path, skill_dir: pathlib.Path) -> str:
    """Pack ``skill_dir`` under its own name; return a ``file://`` URL."""
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(skill_dir, arcname=skill_dir.name)
    return tarball.as_uri()


# --------------------------------------------------------------------------
# Fixtures
#
# Each installs a Mock at a seam in the module under test and returns it, so a
# test configures its ``return_value`` / ``side_effect`` and asserts the call.
# --------------------------------------------------------------------------
@pytest.fixture
def urlopen(monkeypatch):
    urlopen = mock.MagicMock()
    monkeypatch.setattr(sv.urllib_request, "urlopen", urlopen)
    return urlopen


@pytest.fixture
def get(monkeypatch):
    get = mock.Mock()
    monkeypatch.setattr(sv, "_get", get)
    return get


@pytest.fixture
def list_releases(monkeypatch):
    list_releases = mock.Mock()
    monkeypatch.setattr(sv, "_list_releases", list_releases)
    return list_releases


@pytest.fixture
def versions(monkeypatch):
    versions = mock.Mock()
    monkeypatch.setattr(sv, "_versions", versions)
    return versions


@pytest.fixture
def installed_commit(monkeypatch):
    installed_commit = mock.Mock()
    monkeypatch.setattr(sv, "_installed_commit", installed_commit)
    return installed_commit


@pytest.fixture
def read_pointer(monkeypatch):
    read_pointer = mock.Mock()
    monkeypatch.setattr(sv, "_read_pointer", read_pointer)
    return read_pointer


@pytest.fixture
def fetch_references(monkeypatch):
    fetch_references = mock.Mock()
    monkeypatch.setattr(sv, "_fetch_references", fetch_references)
    return fetch_references


@pytest.fixture
def fetch_skill(monkeypatch):
    fetch_skill = mock.Mock()
    monkeypatch.setattr(sv, "_fetch_skill", fetch_skill)
    return fetch_skill


@pytest.fixture
def references(tmp_path, monkeypatch):
    """An installed ``references/`` directory, wired to ``sv._REFERENCES``."""
    references = tmp_path / "references"
    references.mkdir()
    monkeypatch.setattr(sv, "_REFERENCES", references)
    return references


@pytest.fixture
def install_target(tmp_path, monkeypatch):
    """Factory: build an installed skill at ``commit`` and wire it up."""

    def _install(commit):
        installed = _write_skill(
            tmp_path / "inst" / "soliplex-docs",
            commit=commit,
            refs={"index.md": "old\n", "orphan.md": "o\n"},
        )
        monkeypatch.setattr(sv, "_SKILL_ROOT", installed)
        monkeypatch.setattr(sv, "_SKILL_MD", installed / "SKILL.md")
        return installed

    return _install


@pytest.fixture
def temp_dest(tmp_path, monkeypatch):
    """Pin ``_temp_dest`` to a known directory"""
    dest = tmp_path / "dest"
    dest.mkdir()
    temp_dest = mock.MagicMock()
    temp_dest.return_value.__enter__.return_value = dest
    temp_dest.return_value.__exit__.return_value = False
    monkeypatch.setattr(sv, "_temp_dest", temp_dest)
    return dest


@pytest.fixture
def skill_tarball(tmp_path):
    """A one-doc skill packaged as a tarball; return its path."""
    skill = _write_skill(
        tmp_path / "src" / "soliplex-docs",
        commit="abc1234",
        refs={"index.md": "hi\n"},
    )
    tarball = tmp_path / "skill.tar.gz"
    _make_tarball(tarball, skill)
    return tarball


@pytest.fixture
def bare_tarball(tmp_path):
    """A skill tarball lacking a ``references/`` tree; return its path."""
    bare = tmp_path / "src" / "soliplex-docs"
    bare.mkdir(parents=True)
    (bare / "SKILL.md").write_text("x\n", encoding="utf-8")
    tarball = tmp_path / "skill.tar.gz"
    _make_tarball(tarball, bare)
    return tarball


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, None),
        ({"GH_TOKEN": "gh"}, "gh"),
        ({"GITHUB_TOKEN": "github", "GH_TOKEN": "gh"}, "github"),
    ],
)
def test_token(monkeypatch, env, expected):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    assert sv._token() == expected


def test_asset_url():
    assert sv._asset_url("tag", "name.tar.gz").endswith("/tag/name.tar.gz")


@pytest.mark.parametrize(
    "release, expected",
    [
        ({"assets": [{"name": "a"}]}, True),
        ({}, False),
    ],
)
def test_has_asset(release, expected):
    assert sv._has_asset(release, "a") is expected


def test_classify_rolling():
    release = {"tag_name": "docs-2026.05.29-abc1234", "target_commitish": "x"}

    assert sv._classify(release) == ("rolling", "abc1234")


def test_classify_release_with_hex_commit():
    release = {"tag_name": "v1.0.0", "target_commitish": "a" * 40}

    assert sv._classify(release) == ("release", "a" * 7)


def test_classify_release_without_hex_commit():
    release = {"tag_name": "v1.0.0", "target_commitish": "main"}

    assert sv._classify(release) == ("release", "-")


def test_classify_uses_tagname_key():
    assert sv._classify({"tagName": "docs-2026.05.29-abc1234"}) == (
        "rolling",
        "abc1234",
    )


@pytest.mark.parametrize(
    "contents, expected",
    [
        (None, None),
        ("name: x\nno commit here\n", None),
        ('  source_commit: "abcdef0123"\n', "abcdef0"),
    ],
)
def test_commit_of(tmp_path, contents, expected):
    skill_md = tmp_path / "SKILL.md"
    if contents is not None:
        skill_md.write_text(contents, encoding="utf-8")

    assert sv._commit_of(skill_md) == expected


def test_installed_commit(monkeypatch, tmp_path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text('  source_commit: "deadbeef"\n', encoding="utf-8")
    monkeypatch.setattr(sv, "_SKILL_MD", skill_md)

    assert sv._installed_commit() == "deadbee"


def test_sha256(tmp_path):
    blob = tmp_path / "blob"
    blob.write_bytes(b"contents")

    assert sv._sha256(blob) == hashlib.sha256(b"contents").hexdigest()


def test_markdown(tmp_path):
    (tmp_path / "a.md").write_text("l1\nl2\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "c.txt").write_text("ignore", encoding="utf-8")

    out = sv._markdown(tmp_path)

    assert out["a.md"] == ["l1", "l2"]
    assert out["sub/b.md"] == ["x"]
    assert "c.txt" not in out


def test_diff_trees_no_diff(capsys):
    tree = {"a.md": ["x"]}

    rc = sv._diff_trees(
        tree, dict(tree), left_label="L", right_label="R", name_only=False
    )

    assert rc == 0
    assert "No Markdown differences." in capsys.readouterr().out


def test_diff_trees_name_only(capsys):
    left = {"keep.md": ["x"], "gone.md": ["y"], "chg.md": ["a"]}
    right = {"keep.md": ["x"], "new.md": ["z"], "chg.md": ["b"]}

    rc = sv._diff_trees(
        left, right, left_label="L", right_label="R", name_only=True
    )

    out = capsys.readouterr().out
    assert rc == 1
    assert "removed: gone.md" in out
    assert "added:   new.md" in out
    assert "changed: chg.md" in out
    assert "@@" not in out


def test_diff_trees_full(capsys):
    left = {"chg.md": ["a"]}
    right = {"chg.md": ["b"]}

    rc = sv._diff_trees(
        left, right, left_label="L", right_label="R", name_only=False
    )

    out = capsys.readouterr().out
    assert rc == 1
    assert "-a" in out
    assert "+b" in out


# --------------------------------------------------------------------------
# _get / network layer
# --------------------------------------------------------------------------
def test_get_reads_file_url(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    target = tmp_path / "x.json"
    target.write_bytes(b"DATA")

    assert sv._get(target.as_uri()) == b"DATA"


def test_get_adds_token_header(monkeypatch, urlopen):
    urlopen.return_value.__enter__.return_value.read.return_value = b"OK"
    monkeypatch.setenv("GITHUB_TOKEN", "TKN")

    result = sv._get("https://api.example/x")

    assert result == b"OK"
    urlopen.assert_called_once()
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.example/x"
    assert request.get_header("Authorization") == "Bearer TKN"


def test_get_http_error(urlopen):
    urlopen.side_effect = sv.urllib_error.HTTPError("u", 404, "nf", {}, None)

    with pytest.raises(sv.GitHubAPIError) as excinfo:
        sv._get("https://x")

    assert excinfo.value.reason == "HTTP 404"
    assert urlopen.call_args.args[0].full_url == "https://x"


def test_get_url_error(urlopen):
    urlopen.side_effect = sv.urllib_error.URLError("dead")

    with pytest.raises(sv.GitHubAPIError) as excinfo:
        sv._get("https://x")

    assert excinfo.value.reason == "dead"
    assert urlopen.call_args.args[0].full_url == "https://x"


def test_get_rejects_unsupported_scheme(urlopen):
    with pytest.raises(sv.UnsupportedURLScheme) as excinfo:
        sv._get("ftp://example/x")

    assert excinfo.value.scheme == "ftp"
    urlopen.assert_not_called()


def test_list_releases_paginates(get):
    pages = [[{"id": i} for i in range(100)], [{"id": 100}]]
    get.side_effect = [json.dumps(page).encode() for page in pages]

    releases = sv._list_releases()

    assert len(releases) == 101
    assert get.call_count == 2
    get.assert_has_calls(
        [
            mock.call(f"{sv._API}/releases?per_page=100&page=1"),
            mock.call(f"{sv._API}/releases?per_page=100&page=2"),
        ]
    )


def test_list_releases_empty(get):
    get.return_value = b"[]"

    releases = sv._list_releases()

    assert releases == []
    get.assert_called_once_with(f"{sv._API}/releases?per_page=100&page=1")


def test_read_pointer_ok(get):
    get.return_value = b'{"tag": "t"}'

    pointer = sv._read_pointer()

    assert pointer == {"tag": "t"}
    get.assert_called_once_with(
        f"{sv._DL}/{sv.POINTER_TAG}/{sv.POINTER_MANIFEST}",
        accept="application/octet-stream",
    )


def test_read_pointer_request_failed(get):
    get.side_effect = sv.GitHubAPIError("u", "HTTP 404")

    pointer = sv._read_pointer()

    assert pointer is None
    get.assert_called_once_with(
        f"{sv._DL}/{sv.POINTER_TAG}/{sv.POINTER_MANIFEST}",
        accept="application/octet-stream",
    )


def test_read_pointer_bad_json(get):
    get.return_value = b"not json"

    pointer = sv._read_pointer()

    assert pointer is None
    get.assert_called_once_with(
        f"{sv._DL}/{sv.POINTER_TAG}/{sv.POINTER_MANIFEST}",
        accept="application/octet-stream",
    )


# --------------------------------------------------------------------------
# _versions
# --------------------------------------------------------------------------
def test_versions(list_releases):
    list_releases.return_value = [
        {
            "tag_name": sv.POINTER_TAG,
            "assets": [{"name": sv.ASSET_TARBALL}],
            "published_at": "2026-05-30T00:00:00Z",
            "prerelease": False,
            "target_commitish": "main",
        },
        {
            "tag_name": "docs-2026.05.29-abc1234",
            "assets": [{"name": sv.ASSET_TARBALL}],
            "published_at": "2026-05-29T00:00:00Z",
            "prerelease": True,
            "target_commitish": "main",
        },
        {
            "tag_name": "v1.0.0",
            "assets": [{"name": sv.ASSET_TARBALL}],
            "published_at": "2026-05-20T00:00:00Z",
            "prerelease": False,
            "target_commitish": "f" * 40,
        },
        {
            "tag_name": "no-asset",
            "assets": [],
            "published_at": "2026-05-25T00:00:00Z",
            "prerelease": False,
            "target_commitish": "main",
        },
    ]

    out = sv._versions()

    list_releases.assert_called_once_with()
    assert [v["tag"] for v in out] == ["docs-2026.05.29-abc1234", "v1.0.0"]
    assert out[0]["kind"] == "rolling"
    assert out[0]["commit"] == "abc1234"
    assert out[1]["kind"] == "release"
    assert out[1]["commit"] == "f" * 7


# --------------------------------------------------------------------------
# cmd_list
# --------------------------------------------------------------------------
_TWO_VERSIONS = [
    {
        "tag": "docs-2026.05.29-abc1234",
        "date": "2026-05-29",
        "kind": "rolling",
        "commit": "abc1234",
        "prerelease": True,
    },
    {
        "tag": "v1.0.0",
        "date": "2026-05-20",
        "kind": "release",
        "commit": "def5678",
        "prerelease": False,
    },
]


def test_cmd_list_text_marks(versions, installed_commit, read_pointer, capsys):
    versions.return_value = copy.deepcopy(_TWO_VERSIONS)
    installed_commit.return_value = "abc1234"
    read_pointer.return_value = {"tag": "docs-2026.05.29-abc1234"}

    rc = sv.cmd_list(argparse.Namespace(kind=None, json=False))

    out = capsys.readouterr().out
    assert rc == 0
    assert "installed" in out
    assert "latest" in out
    versions.assert_called_once_with()
    installed_commit.assert_called_once_with()
    read_pointer.assert_called_once_with()


def test_cmd_list_kind_filter(
    versions, installed_commit, read_pointer, capsys
):
    versions.return_value = copy.deepcopy(_TWO_VERSIONS)
    installed_commit.return_value = "x"
    read_pointer.return_value = {"tag": "docs-2026.05.29-abc1234"}

    rc = sv.cmd_list(argparse.Namespace(kind="release", json=False))

    out = capsys.readouterr().out
    assert rc == 0
    assert "v1.0.0" in out
    assert "docs-2026.05.29-abc1234" not in out
    versions.assert_called_once_with()


def test_cmd_list_json(versions, installed_commit, read_pointer, capsys):
    versions.return_value = copy.deepcopy(_TWO_VERSIONS)
    installed_commit.return_value = "abc1234"
    read_pointer.return_value = {"tag": "docs-2026.05.29-abc1234"}

    rc = sv.cmd_list(argparse.Namespace(kind=None, json=True))

    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data[0]["installed"] is True
    assert data[0]["latest"] is True
    assert data[1]["installed"] is False


def test_cmd_list_empty(versions, installed_commit, read_pointer, capsys):
    versions.return_value = []
    installed_commit.return_value = None
    read_pointer.return_value = None

    rc = sv.cmd_list(argparse.Namespace(kind=None, json=False))

    assert rc == 0
    assert "No published versions found." in capsys.readouterr().out
    versions.assert_called_once_with()
    read_pointer.assert_called_once_with()


# --------------------------------------------------------------------------
# download / extract
# --------------------------------------------------------------------------
def test_download_and_extract(skill_tarball, tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    sha = sv._sha256(skill_tarball)

    extract = sv._download_and_extract(
        "tag", dest, asset_url=skill_tarball.as_uri(), sha256=sha
    )

    assert (extract / "soliplex-docs" / "SKILL.md").is_file()


def test_fetch_references(skill_tarball, tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()

    refs = sv._fetch_references(
        "tag", dest, asset_url=skill_tarball.as_uri(), sha256=None
    )

    assert (refs / "index.md").read_text(encoding="utf-8") == "hi\n"


def test_fetch_skill(skill_tarball, tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()

    root = sv._fetch_skill(
        "tag", dest, asset_url=skill_tarball.as_uri(), sha256=None
    )

    assert (root / "SKILL.md").is_file()
    assert (root / "references").is_dir()


def test_download_checksum_mismatch(skill_tarball, tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()

    with pytest.raises(sv.ChecksumMismatch):
        sv._download_and_extract(
            "tag", dest, asset_url=skill_tarball.as_uri(), sha256="0" * 64
        )


def test_fetch_references_without_references(bare_tarball, tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()

    with pytest.raises(sv.NoSuchReference):
        sv._fetch_references(
            "tag", dest, asset_url=bare_tarball.as_uri(), sha256=None
        )


def test_fetch_skill_without_references(bare_tarball, tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()

    with pytest.raises(sv.NoSuchReference):
        sv._fetch_skill(
            "tag", dest, asset_url=bare_tarball.as_uri(), sha256=None
        )


def test_temp_dest():
    with sv._temp_dest() as dest:
        assert dest.is_dir()

    assert not dest.exists()


# --------------------------------------------------------------------------
# _resolve_target
# --------------------------------------------------------------------------
def test_resolve_target_explicit():
    assert sv._resolve_target("v1.0.0", None) == ("v1.0.0", None, None)


def test_resolve_target_latest_via_pointer(read_pointer):
    read_pointer.return_value = {"tag": "T", "asset_url": "U", "sha256": "S"}

    result = sv._resolve_target("latest", None)

    assert result == ("T", "U", "S")
    read_pointer.assert_called_once_with()


def test_resolve_target_latest_unavailable(read_pointer):
    read_pointer.return_value = None

    with pytest.raises(sv.PointerUnavailable) as excinfo:
        sv._resolve_target("latest", None)

    assert excinfo.value.tag == "latest"
    read_pointer.assert_called_once_with()


def test_resolve_target_latest_with_asset_url():
    assert sv._resolve_target("latest", "file://x") == (
        "latest",
        "file://x",
        None,
    )


# --------------------------------------------------------------------------
# _install_over
# --------------------------------------------------------------------------
def test_install_over(tmp_path):
    src = _write_skill(
        tmp_path / "src" / "soliplex-docs",
        commit="bbb",
        refs={"index.md": "new\n", "new.md": "n\n"},
    )
    (src / "extra").mkdir()
    (src / "extra" / "f.txt").write_text("e\n", encoding="utf-8")
    dst = _write_skill(
        tmp_path / "dst" / "soliplex-docs",
        commit="aaa",
        refs={"index.md": "old\n", "orphan.md": "o\n"},
    )

    sv._install_over(src, dst)

    assert (dst / "references" / "index.md").read_text() == "new\n"
    assert (dst / "references" / "new.md").is_file()
    assert not (dst / "references" / "orphan.md").exists()
    assert (dst / "extra" / "f.txt").is_file()
    assert sv._commit_of(dst / "SKILL.md") == "bbb"


# --------------------------------------------------------------------------
# cmd_diff
# --------------------------------------------------------------------------
def test_cmd_diff_no_installed_references(monkeypatch, tmp_path):
    monkeypatch.setattr(sv, "_REFERENCES", tmp_path / "missing")

    with pytest.raises(sv.NoSuchReference):
        sv.cmd_diff(
            argparse.Namespace(
                target="t", other=None, name_only=False, asset_url=None
            )
        )


def test_cmd_diff_against_installed(
    references, fetch_references, temp_dest, tmp_path
):
    (references / "index.md").write_text("old\n", encoding="utf-8")
    published = tmp_path / "pub"
    published.mkdir()
    (published / "index.md").write_text("new\n", encoding="utf-8")
    fetch_references.return_value = published

    rc = sv.cmd_diff(
        argparse.Namespace(
            target="sometag", other=None, name_only=True, asset_url=None
        )
    )

    assert rc == 1
    fetch_references.assert_called_once_with(
        "sometag", temp_dest, asset_url=None, sha256=None
    )


def test_cmd_diff_two_targets_via_latest(
    references, fetch_references, read_pointer, temp_dest, tmp_path
):
    (references / "index.md").write_text("inst\n", encoding="utf-8")
    tree_a = tmp_path / "a"
    tree_a.mkdir()
    (tree_a / "index.md").write_text("AAA\n", encoding="utf-8")
    tree_b = tmp_path / "b"
    tree_b.mkdir()
    (tree_b / "index.md").write_text("BBB\n", encoding="utf-8")
    fetch_references.side_effect = [tree_a, tree_b]
    read_pointer.return_value = {
        "tag": "resolved",
        "asset_url": None,
        "sha256": None,
    }

    rc = sv.cmd_diff(
        argparse.Namespace(
            target="latest", other="other", name_only=False, asset_url=None
        )
    )

    assert rc == 1
    read_pointer.assert_called_once_with()
    fetch_target, fetch_other = fetch_references.call_args_list
    assert fetch_target == mock.call(
        "resolved", temp_dest, asset_url=None, sha256=None
    )
    assert fetch_other == mock.call(
        "other", temp_dest, asset_url=None, sha256=None
    )


# --------------------------------------------------------------------------
# cmd_upgrade
# --------------------------------------------------------------------------
def test_cmd_upgrade_no_skill_root(monkeypatch, tmp_path):
    monkeypatch.setattr(sv, "_SKILL_ROOT", tmp_path / "missing")

    with pytest.raises(sv.NoSuchReference):
        sv.cmd_upgrade(
            argparse.Namespace(
                tag="t", force=False, dry_run=False, asset_url=None
            )
        )


def test_cmd_upgrade_dry_run(
    install_target, fetch_skill, temp_dest, tmp_path, capsys
):
    installed = install_target("aaaaaaa")
    new = _write_skill(
        tmp_path / "new" / "soliplex-docs",
        commit="bbbbbbb",
        refs={"index.md": "new\n"},
    )
    fetch_skill.return_value = new

    rc = sv.cmd_upgrade(
        argparse.Namespace(
            tag="newtag", force=False, dry_run=True, asset_url=None
        )
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "Would upgrade to newtag" in out
    assert (installed / "references" / "index.md").read_text() == "old\n"
    fetch_skill.assert_called_once_with(
        "newtag", temp_dest, asset_url=None, sha256=None
    )


def test_cmd_upgrade_installs(
    install_target, fetch_skill, temp_dest, tmp_path, capsys
):
    installed = install_target("aaaaaaa")
    new = _write_skill(
        tmp_path / "new" / "soliplex-docs",
        commit="bbbbbbb",
        refs={"index.md": "new\n"},
    )
    fetch_skill.return_value = new

    rc = sv.cmd_upgrade(
        argparse.Namespace(
            tag="newtag", force=False, dry_run=False, asset_url=None
        )
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "Upgraded soliplex-docs to newtag" in out
    assert (installed / "references" / "index.md").read_text() == "new\n"
    assert not (installed / "references" / "orphan.md").exists()
    assert sv._commit_of(installed / "SKILL.md") == "bbbbbbb"
    fetch_skill.assert_called_once_with(
        "newtag", temp_dest, asset_url=None, sha256=None
    )


def test_cmd_upgrade_already_current(
    install_target, fetch_skill, temp_dest, tmp_path, capsys
):
    installed = install_target("ccccccc")
    new = _write_skill(
        tmp_path / "new" / "soliplex-docs",
        commit="ccccccc",
        refs={"index.md": "new\n"},
    )
    fetch_skill.return_value = new

    rc = sv.cmd_upgrade(
        argparse.Namespace(tag="t", force=False, dry_run=False, asset_url=None)
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "Already up to date" in out
    assert (installed / "references" / "index.md").read_text() == "old\n"
    fetch_skill.assert_called_once_with(
        "t", temp_dest, asset_url=None, sha256=None
    )


def test_cmd_upgrade_force(install_target, fetch_skill, temp_dest, tmp_path):
    installed = install_target("ccccccc")
    new = _write_skill(
        tmp_path / "new" / "soliplex-docs",
        commit="ccccccc",
        refs={"index.md": "new\n"},
    )
    fetch_skill.return_value = new

    rc = sv.cmd_upgrade(
        argparse.Namespace(tag="t", force=True, dry_run=False, asset_url=None)
    )

    assert rc == 0
    assert (installed / "references" / "index.md").read_text() == "new\n"
    fetch_skill.assert_called_once_with(
        "t", temp_dest, asset_url=None, sha256=None
    )


def test_cmd_upgrade_new_without_commit(
    install_target, fetch_skill, temp_dest, tmp_path, capsys
):
    installed = install_target("aaaaaaa")
    new = tmp_path / "new" / "soliplex-docs"
    (new / "references").mkdir(parents=True)
    (new / "references" / "index.md").write_text("new\n", encoding="utf-8")
    fetch_skill.return_value = new

    rc = sv.cmd_upgrade(
        argparse.Namespace(tag="t", force=False, dry_run=False, asset_url=None)
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "commit unknown" in out
    assert (installed / "references" / "index.md").read_text() == "new\n"
    fetch_skill.assert_called_once_with(
        "t", temp_dest, asset_url=None, sha256=None
    )


# --------------------------------------------------------------------------
# main dispatch / argparse
# --------------------------------------------------------------------------
def test_main_requires_subcommand():
    with pytest.raises(SystemExit):
        sv.main([])


def test_main_list(versions, read_pointer, installed_commit):
    versions.return_value = []
    read_pointer.return_value = {}
    installed_commit.return_value = None

    assert sv.main(["list"]) == 0

    versions.assert_called_once_with()


def test_main_diff(references, fetch_references, temp_dest):
    (references / "index.md").write_text("a\n", encoding="utf-8")
    fetch_references.return_value = references

    assert sv.main(["diff", "sometag"]) == 0

    fetch_references.assert_called_once_with(
        "sometag", temp_dest, asset_url=None, sha256=None
    )


def test_main_upgrade_defaults_to_latest(monkeypatch, tmp_path, read_pointer):
    read_pointer.return_value = None
    monkeypatch.setattr(sv, "_SKILL_ROOT", tmp_path)

    with pytest.raises(sv.PointerUnavailable) as excinfo:
        sv.main(["upgrade"])

    assert excinfo.value.tag == "latest"
    read_pointer.assert_called_once_with()
