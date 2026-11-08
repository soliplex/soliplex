"""Reload checks requiring POSIX FIFOs and unprivileged symlinks."""

import os

from soliplex.config import installation as config_installation
from tests import _platform
from tests.unit.config.test_reload_skills import (
    loaded_skills_config as loaded_skills_config,
)
from tests.unit.config.test_reload_skills import write_skill

pytestmark = _platform.requires_posix_symlinks


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
