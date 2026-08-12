"""Database-URI helpers shared by 'tests/unit' and 'tests/functional'.

A plain module rather than a 'conftest.py' because both suites need the
*function*, and importing one conftest from another risks pytest holding
a second, separate instance of that module. 'tests/' is importable as a
namespace package thanks to 'pythonpath = ["."]' in 'pyproject.toml'.

The fixture wrappers ('authz_dburi_sync' / 'authz_dburi_async') live in
'tests/conftest.py'.
"""

import pathlib


def sqlite_dburi(db_path: pathlib.Path, driver: str = "") -> str:
    """Build an absolute 'sqlite[<driver>]:///<abs>' URI for 'db_path'.

    An absolute URI (four leading slashes once the leading '/' of a POSIX
    path is included) keeps the database independent of the process
    working directory.

    The path is spelled POSIX-style because these URIs get written into a
    double-quoted YAML scalar, where a Windows path's backslashes are
    escape sequences: 'C:\\Users\\...' fails to parse ('\\U' wants eight
    hex digits) and e.g. '\\t' would silently become a tab. SQLAlchemy's
    sqlite dialect accepts 'sqlite:///C:/...' on Windows.
    """
    return f"sqlite{driver}:///{db_path.as_posix()}"
