"""Keep a '.env' in the checkout out of the unit tests.

'InstallationConfig.from_dotenv' reads the '.env' beside the installation
config, falling back to one in the cwd -- under pytest, the repo root.  A
developer's gitignored '.env' there overrides what a test configured: its
values win over 'os.environ' (see 'soliplex.secrets'), so e.g. a token a
test signed with its own 'SOLIPLEX_URL_SAFE_TOKEN_SECRET' fails to
verify.  CI has no such file, so the same tests pass there and fail
locally, with nothing pointing at the cause.

'tests/unit/conftest.py' wraps 'InstallationConfig._load_dotenv' with
'guard_load_dotenv' for every unit test:  a '.env' inside the checkout
is treated as absent, and reported with a 'RepoDotenvIgnoredWarning'
naming it, while a test's own '.env' (under a tmp dir) loads as usual.
"""

import pathlib
import warnings

# 'tests/unit/_dotenv_guard.py' -> parents[2] is the repo root.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

REPO_DOTENV_IGNORED = (
    "unit tests ignore {path}: a '.env' in the checkout would leak local "
    "settings into them (CI has none). A test needing a '.env' must "
    "write its own, under 'tmp_path'."
)


class RepoDotenvIgnoredWarning(UserWarning):
    """A '.env' in the checkout was skipped by the unit tests."""


def guard_load_dotenv(load_dotenv, repo_root: pathlib.Path):
    """Wrap 'load_dotenv' to skip any '.env' inside 'repo_root'"""

    def _load_dotenv(from_path: pathlib.Path):
        # Not 'pathlib.Path(from_path)':  some tests patch 'pathlib.Path'.
        resolved = from_path.resolve()

        if resolved.is_relative_to(repo_root):
            if resolved.is_file():
                warnings.warn(
                    REPO_DOTENV_IGNORED.format(path=resolved),
                    RepoDotenvIgnoredWarning,
                    stacklevel=2,
                )
            return None

        return load_dotenv(from_path)

    return _load_dotenv
