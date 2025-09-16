import os
import pathlib
import subprocess
import traceback
import typing


def scrub_private_keys(
    json_dict: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    """Return a copy of 'json_dict' with private keys removed

    'json_dict'
        the dict to be copied
    """
    scrubbed = {}
    for key, value in json_dict.items():
        if not key.startswith("_"):
            if isinstance(value, dict):
                value = scrub_private_keys(value)
            if isinstance(value, list):
                if value and isinstance(value[0], dict):
                    value = [
                        scrub_private_keys(item) for item in value
                    ]
            scrubbed[key] = value
    return scrubbed


def interpolate_env_vars(source: str) -> str:
    """Interplate environment variables into a string

    'source'
        the string containing potential format replacements to be
        filled using environment variables
    """
    if not source.startswith("env:"):
        return source

    stripped = source[len("env:"):]

    return stripped.format(**os.environ)


def get_git_hash_for_file(file_path: str):
    file_path = pathlib.Path(file_path)
    repo_dir = file_path.parent
    hash_path = repo_dir / "git-hash.txt"

    if hash_path.is_file():
        return hash_path.read_text().strip()

    try:
        return subprocess.check_output(
            ['git', '-C', repo_dir, 'rev-parse', 'HEAD']
        ).decode('utf-8').strip()
    except Exception:
        traceback.print_exc()
        return 'unknown'
