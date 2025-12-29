import pathlib
import tempfile

import pytest

from soliplex import config


def _auth_systems(n_auth_systems):
    return [
        config.OIDCAuthSystemConfig(
            id=f"auth-system-{i_auth_system}",
            title=f"Auth System #{i_auth_system}",
            token_validation_pem=f"PEM {i_auth_system:3d}",
            server_url=f"http://auth{i_auth_system:03}.example.com/",
            client_id=f"AUTH_SYSTEM_{i_auth_system:03}",
        )
        for i_auth_system in range(n_auth_systems)
    ]


@pytest.fixture
def temp_dir() -> pathlib.Path:
    with tempfile.TemporaryDirectory() as td:
        yield pathlib.Path(td)


@pytest.fixture(params=[0, 1, 2])
def with_auth_systems(request):
    return _auth_systems(request.param)
