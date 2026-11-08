"""Verify filesystem skill validation and live room publication."""

import hashlib
import os
import shutil
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import pytest

from soliplex import installation
from soliplex.config import exceptions as config_exc
from soliplex.config import installation as config_installation
from soliplex.config import skills as config_skills
from tests.unit.config import test_config_installation as test_installation


def write_skill(root, name, instructions="Follow these instructions."):
    """Write a valid filesystem skill under the discovery path."""
    path = root / "skills" / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Describing {name}\n---\n"
        f"{instructions}\n",
        encoding="utf-8",
    )
    return path


def write_room(root, names):
    """Write a room that binds the requested installation skills."""
    path = root / "rooms" / "foo"
    path.mkdir(parents=True, exist_ok=True)
    (path / "room_config.yaml").write_text(
        test_installation._room_config_yaml("foo")
        + "\nskills:\n  installation_skill_names:\n"
        + "".join(f"    - {name}\n" for name in names)
        + "  skill_configs:\n    - kind: bubble-sandbox\n",
        encoding="utf-8",
    )


@pytest.fixture
def loaded_skills_config(tmp_path):
    """Load an installation with two filesystem skills and one room."""
    write_skill(tmp_path, "alpha")
    write_skill(tmp_path, "beta")
    write_room(tmp_path, ["alpha"])
    config = config_installation.InstallationConfig(
        id="reload-skills",
        _config_path=tmp_path / "installation.yaml",
        environment=test_installation.BARE_INSTALLATION_CONFIG_ENVIRONMENT,
        oidc_paths=[],
    )
    config.reload_configurations()
    return config


@pytest.mark.anyio
async def test_reload_discovers_added_skill(loaded_skills_config, tmp_path):
    config = loaded_skills_config
    write_skill(tmp_path, "gamma")
    config.reload_room_configs()
    assert "gamma" not in config.skill_configs
    assert "gamma" not in config.room_configs["foo"].skill_configs
    write_room(tmp_path, ["alpha", "gamma"])
    with pytest.raises(config_exc.FromYamlException):
        config.reload_room_configs()

    result = await installation.Installation(
        config
    ).reload_skill_and_room_configs()

    assert result.added == result.removed == ()
    assert result.changed == ("foo",)
    assert result.skills == installation.SkillConfigsReloaded(
        added=("gamma",), removed=(), changed=()
    )
    room = config.room_configs["foo"]
    assert "gamma" in room.skill_configs
    snapshot = room._installation_config
    assert snapshot is not config
    assert room.agent_config._installation_config is snapshot
    assert room.skills._installation_config is snapshot
    assert (
        room.skills._skill_configs[
            config_skills.BwrapSandboxSkillConfig.name
        ]._installation_config
        is snapshot
    )
    assert config.filesystem_skills_paths == [tmp_path / "skills"]


@pytest.mark.anyio
async def test_reload_removes_skill(loaded_skills_config, tmp_path):
    config = loaded_skills_config
    shutil.rmtree(tmp_path / "skills" / "beta")

    result = await installation.Installation(
        config
    ).reload_skill_and_room_configs()

    assert result.skills == installation.SkillConfigsReloaded(
        added=(), removed=("beta",), changed=()
    )
    assert set(config.skill_configs) == {"alpha"}
    assert set(config.available_filesystem_skill_configs) == {"alpha"}


@pytest.mark.parametrize(
    "failure",
    ["room", "enabled-skill", "discovery", "fingerprint"],
)
def test_reload_failure_preserves_caches(
    loaded_skills_config, tmp_path, failure, monkeypatch
):
    config = loaded_skills_config
    rooms = config._room_configs
    available = config._available_filesystem_skill_configs
    enabled = config._resolved_skill_configs
    fingerprints = config._skill_fingerprints
    write_skill(tmp_path, "gamma")
    if failure == "room":
        write_room(tmp_path, ["missing"])
        expected = config_exc.FromYamlException
    elif failure == "enabled-skill":
        config._skill_configs = [
            {"kind": "filesystem", "skill_name": "missing"}
        ]
        expected = KeyError
    else:
        target = (
            "_load_filesystem_skill_configs"
            if failure == "discovery"
            else "_skill_fingerprint"
        )
        monkeypatch.setattr(
            config_installation,
            target,
            mock.Mock(side_effect=ValueError("Cannot validate skills")),
        )
        expected = ValueError

    with pytest.raises(expected):
        config.reload_skill_and_room_configs()

    assert config._room_configs is rooms
    assert config._available_filesystem_skill_configs is available
    assert config._resolved_skill_configs is enabled
    assert config._skill_fingerprints is fingerprints
    assert "gamma" not in config.skill_configs
    assert "alpha" in config.room_configs["foo"].skill_configs


@pytest.mark.anyio
async def test_repeated_reload_has_no_changes(loaded_skills_config):
    config = loaded_skills_config
    service = installation.Installation(config)
    for _ in range(3):
        result = await service.reload_skill_and_room_configs()
        assert result == installation.SkillAndRoomConfigsReloaded(
            added=(),
            removed=(),
            changed=(),
            skills=installation.SkillConfigsReloaded(
                added=(), removed=(), changed=()
            ),
        )
        assert "reload-skills" in repr(config)
        assert "foo" in repr(config.room_configs)
        assert (
            config.room_configs["foo"].skills._installation_config
            is not config
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "edit", ["instructions", "description", "bytes", "add", "remove", "rename"]
)
async def test_reload_reports_only_edited_skill(
    loaded_skills_config, tmp_path, edit
):
    config = loaded_skills_config
    resource = tmp_path / "skills" / "alpha" / "resources" / "data.bin"
    resource.parent.mkdir()
    resource.write_bytes(b"before")
    service = installation.Installation(config)
    await service.reload_skill_and_room_configs()
    if edit == "instructions":
        write_skill(tmp_path, "alpha", "Changed instructions.")
    elif edit == "description":
        path = resource.parent.parent / "SKILL.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "Describing alpha", "Changed description"
            ),
            encoding="utf-8",
        )
    elif edit == "bytes":
        resource.write_bytes(b"after!")
    elif edit == "add":
        resource.with_name("new.bin").write_bytes(b"before")
    elif edit == "remove":
        resource.unlink()
    else:
        resource.rename(resource.with_name("renamed.bin"))

    result = await service.reload_skill_and_room_configs()

    assert result.added == result.removed == result.changed == ()
    assert result.skills == installation.SkillConfigsReloaded(
        added=(), removed=(), changed=("alpha",)
    )
    assert (await service.reload_skill_and_room_configs()).skills.changed == ()


def test_reload_keeps_skill_enablement(loaded_skills_config, tmp_path):
    config = loaded_skills_config
    config._skill_configs = [{"kind": "filesystem", "skill_name": "alpha"}]
    write_skill(tmp_path, "gamma")
    config.reload_skill_and_room_configs()
    assert set(config.skill_configs) == {"alpha"}
    assert set(config.available_filesystem_skill_configs) == {
        "alpha",
        "beta",
        "gamma",
    }


@pytest.mark.parametrize("combined", [False, True])
def test_concurrent_reloads_serialize(loaded_skills_config, combined):
    config = loaded_skills_config
    entered = threading.Event()
    release = threading.Event()
    second_attempt = threading.Event()
    second_entered = threading.Event()
    lock = config._reload_lock
    loads = []
    loader = config_installation.InstallationConfig._load_room_configs

    class ObservedLock:
        def __enter__(self):
            if entered.is_set():
                second_attempt.set()
            lock.acquire()

        def __exit__(self, *_args):
            lock.release()

    def load(candidate):
        loads.append(candidate)
        if len(loads) == 1:
            entered.set()
            assert release.wait(5)
        else:
            second_entered.set()
        return loader(candidate)

    with (
        mock.patch.object(config, "_reload_lock", ObservedLock()),
        mock.patch.object(
            config_installation.InstallationConfig,
            "_load_room_configs",
            load,
        ),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        first = pool.submit(config.reload_skill_and_room_configs)
        try:
            assert entered.wait(5)
            reload = (
                config.reload_skill_and_room_configs
                if combined
                else config.reload_room_configs
            )
            second = pool.submit(reload)
            assert second_attempt.wait(5)
            assert not second_entered.is_set()
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert len(loads) == 2


def test_published_rooms_retain_snapshot(loaded_skills_config):
    config = loaded_skills_config
    before_rooms, after_rooms, before_skills, after_skills = (
        config.reload_skill_and_room_configs()
    )
    room = after_rooms["foo"]
    snapshot = room._installation_config
    assert snapshot is not config
    assert snapshot.room_configs == after_rooms
    assert room.skills._installation_config is snapshot
    assert before_rooms["foo"] is not room
    assert before_skills == after_skills
    assert before_skills is not config._skill_fingerprints
    assert after_skills is not config._skill_fingerprints


def test_reload_initializes_caches_before_snapshots(loaded_skills_config):
    config = loaded_skills_config
    config._resolved_skill_configs = None
    config._room_configs = None

    before_rooms, after_rooms, before_skills, after_skills = (
        config.reload_skill_and_room_configs()
    )

    assert before_rooms == after_rooms
    assert before_skills == after_skills
    assert set(before_skills) == {"alpha", "beta"}


def test_reload_fingerprints_only_enabled_skills(
    loaded_skills_config, tmp_path, monkeypatch
):
    config = loaded_skills_config
    config._skill_configs = [{"kind": "filesystem", "skill_name": "alpha"}]
    resource = tmp_path / "skills" / "beta" / "unread.bin"
    resource.write_bytes(b"disabled")
    original = os.open

    def open_checked(path, *args, **kwargs):
        assert path != resource
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", open_checked)
    config.reload_skill_and_room_configs()
    assert set(config._skill_fingerprints) == {"alpha"}


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX special files")
def test_fingerprint_skips_special_files_and_symlinks(
    loaded_skills_config, tmp_path, monkeypatch
):
    config = loaded_skills_config
    root = tmp_path / "skills" / "alpha"
    fifo = root / "pipe"
    os.mkfifo(fifo)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_bytes(b"outside")
    link = root / "linked.txt"
    link.symlink_to(target)
    directory_link = root / "linked-dir"
    directory_link.symlink_to(outside, target_is_directory=True)
    original = os.open

    def open_checked(path, *args, **kwargs):
        assert path not in (fifo, link, target)
        assert directory_link not in path.parents
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", open_checked)
    before = config._skill_fingerprints.copy()
    config.reload_skill_and_room_configs()
    assert config._skill_fingerprints == before


@pytest.mark.parametrize("size_mib", [16, 17])
def test_fingerprint_bounds_resource_reads(
    loaded_skills_config, tmp_path, monkeypatch, size_mib
):
    config = loaded_skills_config
    resource = tmp_path / "skills" / "alpha" / "large.bin"
    content = b"x" * (size_mib * 1024 * 1024)
    resource.write_bytes(content)
    original = os.read
    reads = []
    inode = resource.stat().st_ino

    def read_checked(descriptor, size):
        if os.fstat(descriptor).st_ino == inode:
            reads.append(size)
        return original(descriptor, size)

    monkeypatch.setattr(os, "read", read_checked)
    config.reload_skill_and_room_configs()
    fingerprint = config._skill_fingerprints["alpha"]
    if size_mib == 16:
        assert ("large.bin", hashlib.sha256(content).hexdigest()) in (
            fingerprint[-1]
        )
        assert reads == [64 * 1024] * 256 + [1]
    else:
        assert ("large.bin", "skipped: larger than 16 MiB") in (
            fingerprint[-1]
        )
        assert reads == []

    resource.write_bytes(b"y" * len(content))
    config.reload_skill_and_room_configs()
    assert (config._skill_fingerprints["alpha"] == fingerprint) == (
        size_mib == 17
    )


def test_fingerprint_handles_type_race(
    loaded_skills_config, tmp_path, monkeypatch
):
    config = loaded_skills_config.skill_configs["alpha"]
    resource = tmp_path / "skills" / "alpha" / "swapped.bin"
    resource.write_bytes(b"before")
    original_open = os.open
    original_read = os.read

    def open_swapped(path, flags):
        if path == resource:
            assert flags & getattr(os, "O_NONBLOCK", 0) == getattr(
                os, "O_NONBLOCK", 0
            )
            assert flags & getattr(os, "O_NOFOLLOW", 0) == getattr(
                os, "O_NOFOLLOW", 0
            )
            assert flags & getattr(os, "O_CLOEXEC", 0) == getattr(
                os, "O_CLOEXEC", 0
            )
            swapped, writer = os.pipe()
            os.close(writer)
            return swapped
        return original_open(path, flags)

    def read_checked(descriptor, size):
        # A later regular file may reuse the closed pipe descriptor.
        assert stat.S_ISREG(os.fstat(descriptor).st_mode)
        return original_read(descriptor, size)

    monkeypatch.setattr(os, "open", open_swapped)
    monkeypatch.setattr(os, "read", read_checked)
    fingerprint = config_installation._skill_fingerprint(config)
    assert ("swapped.bin", "skipped: not a regular file") in fingerprint[-1]


def test_fingerprint_bounds_growing_file(
    loaded_skills_config, tmp_path, monkeypatch
):
    config = loaded_skills_config.skill_configs["alpha"]
    resource = tmp_path / "skills" / "alpha" / "growing.bin"
    resource.write_bytes(b"x")
    inode = resource.stat().st_ino
    original = os.read
    reads = []

    def read_growing(descriptor, size):
        if os.fstat(descriptor).st_ino == inode:
            if not reads:
                with resource.open("r+b") as stream:
                    stream.truncate(17 * 1024 * 1024)
            chunk = original(descriptor, size)
            reads.append(len(chunk))
            return chunk
        return original(descriptor, size)

    monkeypatch.setattr(os, "read", read_growing)
    fingerprint = config_installation._skill_fingerprint(config)
    assert ("growing.bin", "skipped: larger than 16 MiB") in fingerprint[-1]
    assert reads == [64 * 1024] * 256 + [1]
    assert sum(reads) == 16 * 1024 * 1024 + 1


def test_reload_fingerprints_placeholder_errors(
    loaded_skills_config, tmp_path
):
    config = loaded_skills_config
    skill_file = tmp_path / "skills" / "alpha" / "SKILL.md"
    skill_file.write_text("Invalid frontmatter", encoding="utf-8")

    _, _, before, after = config.reload_skill_and_room_configs()

    skill = config.skill_configs["alpha"]
    assert skill.errors == ["SKILL.md must start with YAML frontmatter"]
    assert after["alpha"] == (
        skill.kind,
        skill.name,
        tuple(sorted(skill.errors)),
    )
    assert before["alpha"] != after["alpha"]
    skill_file.write_text("Different invalid content", encoding="utf-8")
    _, _, before, after = config.reload_skill_and_room_configs()
    assert before == after


def test_placeholder_fingerprint_sorts_errors():
    config = mock.Mock(kind="filesystem", errors=["z error", "a error"])
    config.name = "alpha"
    assert config_installation._skill_fingerprint(config) == (
        "filesystem",
        "alpha",
        ("a error", "z error"),
    )
    assert config.mock_calls == []


@pytest.mark.parametrize("fail", [False, True])
def test_old_room_skills_survive_publication(
    loaded_skills_config, tmp_path, monkeypatch, fail
):
    config = loaded_skills_config
    old_room = config.room_configs["foo"]
    old_skill = old_room.skill_configs["alpha"]
    shutil.rmtree(tmp_path / "skills" / "alpha")
    write_room(tmp_path, ["beta"])
    loader = config_installation.InstallationConfig._load_room_configs

    def load(candidate):
        rooms = loader(candidate)

        def read_previous():
            assert old_room.skill_configs["alpha"] == old_skill
            assert "alpha" in config.room_configs["foo"].skill_configs

        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(read_previous).result(timeout=5)
        if fail:
            message = "validation failed"
            raise ValueError(message)
        return rooms

    monkeypatch.setattr(
        config_installation.InstallationConfig, "_load_room_configs", load
    )
    if fail:
        with pytest.raises(ValueError, match="validation failed"):
            config.reload_skill_and_room_configs()
        assert config.room_configs["foo"] is old_room
    else:
        config.reload_skill_and_room_configs()
        assert "alpha" not in config.skill_configs
        assert "beta" in config.room_configs["foo"].skill_configs
    assert old_room.skill_configs["alpha"] == old_skill


@pytest.mark.skipif(os.name == "nt", reason="Requires symlink support")
def test_discovery_preserves_symlink_name(tmp_path):
    target = write_skill(tmp_path, "alpha")
    renamed = target.with_name("release-v2")
    target.rename(renamed)
    target.symlink_to(renamed, target_is_directory=True)
    config = config_installation.InstallationConfig(
        id="symlink", filesystem_skills_paths=[target]
    )
    for _ in range(2):
        skills = config_installation._load_filesystem_skill_configs(config)
        assert set(skills) == {"alpha"}
        assert skills["alpha"].errors == []


@pytest.mark.parametrize("stage", ["stat", "open"])
def test_fingerprint_ignores_disappearing_file(
    loaded_skills_config, tmp_path, monkeypatch, stage
):
    from pathlib import Path

    skill = loaded_skills_config.skill_configs["alpha"]
    before = config_installation._skill_fingerprint(skill)
    resource = tmp_path / "skills" / "alpha" / "temporary.bin"
    resource.write_bytes(b"temporary")
    original = Path.lstat if stage == "stat" else os.open

    def disappear(path, *args, **kwargs):
        if path == resource:
            raise FileNotFoundError
        return original(path, *args, **kwargs)

    if stage == "stat":
        monkeypatch.setattr(Path, "lstat", disappear)
    else:
        monkeypatch.setattr(os, "open", disappear)
    assert config_installation._skill_fingerprint(skill) == before


def test_fingerprint_reports_unreadable_file(
    loaded_skills_config, tmp_path, monkeypatch
):
    skill = loaded_skills_config.skill_configs["alpha"]
    resource = tmp_path / "skills" / "alpha" / "unreadable.bin"
    resource.write_bytes(b"resource")
    original = os.open

    def denied(path, *args, **kwargs):
        if path == resource:
            message = "unreadable resource"
            raise PermissionError(message)
        return original(path, *args, **kwargs)

    os.close(denied(skill.path / "SKILL.md", os.O_RDONLY))
    monkeypatch.setattr(os, "open", denied)
    with pytest.raises(PermissionError, match="unreadable resource"):
        config_installation._skill_fingerprint(skill)


@pytest.mark.parametrize("error", [PermissionError, OSError])
def test_traversal_failure_preserves_caches(
    loaded_skills_config, tmp_path, monkeypatch, error
):
    config = loaded_skills_config
    resource = tmp_path / "skills" / "alpha" / "resources" / "data.bin"
    resource.parent.mkdir()
    resource.write_bytes(b"before")
    config.reload_skill_and_room_configs()
    rooms = config._room_configs
    available = config._available_filesystem_skill_configs
    enabled = config._resolved_skill_configs
    fingerprints = config._skill_fingerprints
    write_skill(tmp_path, "gamma")
    original = os.scandir

    def denied(path):
        if os.fspath(path) == os.fspath(resource.parent):
            message = "unreadable directory"
            raise error(message)
        return original(path)

    monkeypatch.setattr(os, "scandir", denied)
    with pytest.raises(error, match="unreadable directory"):
        config.reload_skill_and_room_configs()

    assert config._room_configs is rooms
    assert config._available_filesystem_skill_configs is available
    assert config._resolved_skill_configs is enabled
    assert config._skill_fingerprints is fingerprints
    assert "gamma" not in config.skill_configs


def test_fingerprint_ignores_disappearing_directory(
    loaded_skills_config, tmp_path, monkeypatch
):
    skill = loaded_skills_config.skill_configs["alpha"]
    before = config_installation._skill_fingerprint(skill)
    resource = tmp_path / "skills" / "alpha" / "resources"
    resource.mkdir()
    (resource / "data.bin").write_bytes(b"temporary")
    original = os.scandir

    def disappear(path):
        if os.fspath(path) == os.fspath(resource):
            raise FileNotFoundError
        return original(path)

    monkeypatch.setattr(os, "scandir", disappear)
    assert config_installation._skill_fingerprint(skill) == before


@pytest.mark.anyio
@pytest.mark.parametrize("empty_rooms", [False, True])
async def test_startup_baseline_without_room_skills(
    loaded_skills_config, tmp_path, empty_rooms
):
    config = loaded_skills_config
    if empty_rooms:
        shutil.rmtree(tmp_path / "rooms")
    else:
        (tmp_path / "rooms" / "foo" / "room_config.yaml").write_text(
            test_installation._room_config_yaml("foo"), encoding="utf-8"
        )
    resource = tmp_path / "skills" / "alpha" / "data.bin"
    resource.write_bytes(b"before")
    config.reload_configurations()
    resource.write_bytes(b"after!")

    result = await installation.Installation(
        config
    ).reload_skill_and_room_configs()

    assert result.skills == installation.SkillConfigsReloaded(
        added=(), removed=(), changed=("alpha",)
    )
    assert result.added == result.removed == result.changed == ()


@pytest.mark.anyio
async def test_skill_read_failure_preserves_published_caches(
    loaded_skills_config, tmp_path, monkeypatch
):
    from pathlib import Path

    config = loaded_skills_config
    service = installation.Installation(config)
    rooms = config._room_configs
    available = config._available_filesystem_skill_configs
    enabled = config._resolved_skill_configs
    fingerprints = config._skill_fingerprints
    old_skill = rooms["foo"].skill_configs["alpha"]
    write_skill(tmp_path, "gamma")
    write_room(tmp_path, ["beta", "gamma"])
    skill_file = tmp_path / "skills" / "alpha" / "SKILL.md"
    original = Path.read_text

    def denied(path, *args, **kwargs):
        if path == skill_file:
            message = "unreadable SKILL.md"
            raise PermissionError(message)
        return original(path, *args, **kwargs)

    assert "name: beta" in denied(
        tmp_path / "skills" / "beta" / "SKILL.md", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(PermissionError, match="unreadable SKILL.md"):
        await service.reload_skill_and_room_configs()

    assert config._room_configs is rooms
    assert config._available_filesystem_skill_configs is available
    assert config._resolved_skill_configs is enabled
    assert config._skill_fingerprints is fingerprints
    assert "gamma" not in config.skill_configs
    served_skill = config.room_configs["foo"].skill_configs["alpha"]
    assert served_skill is old_skill
    assert served_skill.errors == []
    assert served_skill.capability.instructions == "Follow these instructions."
