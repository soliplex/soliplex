import pathlib

import pytest

from soliplex.config import exceptions as config_exc
from soliplex.config import lti as config_lti

CONFIG_PATH = pathlib.Path("/fake/config.yaml")

BARE_CONFIG = {
    "id": "moodle-workplace",
    "issuer": "https://moodle.example.com",
    "client_id": "soliplex-lti-tool",
    "deployment_ids": ["1"],
    "auth_login_url": "https://moodle.example.com/mod/lti/auth.php",
    "auth_token_url": "https://moodle.example.com/mod/lti/token.php",
    "key_set_url": "https://moodle.example.com/mod/lti/certs.php",
    "default_room_id": "moodle-tools",
}

W_ALL_FIELDS_CONFIG = {
    **BARE_CONFIG,
    "deployment_ids": ["1", "2"],
    "course_room_map": {"101": "room-101"},
    "show_room_picker": True,
    "session_ttl": 7200,
}


def test_from_yaml_bare():
    found = config_lti.LTIPlatformConfig.from_yaml(
        CONFIG_PATH, dict(BARE_CONFIG)
    )

    assert found.id == BARE_CONFIG["id"]
    assert found.issuer == BARE_CONFIG["issuer"]
    assert found.client_id == BARE_CONFIG["client_id"]
    assert found.deployment_ids == ["1"]
    assert found.course_room_map == {}
    assert found.show_room_picker is False
    assert found.session_ttl == 3600
    assert found._config_path == CONFIG_PATH


def test_from_yaml_all_fields():
    found = config_lti.LTIPlatformConfig.from_yaml(
        CONFIG_PATH, dict(W_ALL_FIELDS_CONFIG)
    )

    assert found.deployment_ids == ["1", "2"]
    assert found.course_room_map == {"101": "room-101"}
    assert found.show_room_picker is True
    assert found.session_ttl == 7200


def test_from_yaml_error():
    bad_config = dict(BARE_CONFIG) | {"unknown_field": "bogus"}

    with pytest.raises(config_exc.FromYamlException) as exc_info:
        config_lti.LTIPlatformConfig.from_yaml(CONFIG_PATH, bad_config)

    assert exc_info.value._config_path == CONFIG_PATH


def test_from_yaml_rejects_empty_deployment_ids():
    """Empty deployment_ids silently breaks every launch — fail loud."""
    bad_config = dict(BARE_CONFIG) | {"deployment_ids": []}

    with pytest.raises(config_exc.FromYamlException) as exc_info:
        config_lti.LTIPlatformConfig.from_yaml(CONFIG_PATH, bad_config)

    assert exc_info.value._config_path == CONFIG_PATH
    cause = exc_info.value.__cause__
    assert isinstance(cause, ValueError)
    assert "deployment_ids" in str(cause)


def test_from_yaml_rejects_missing_deployment_ids():
    """deployment_ids defaults to [] — same rejection as explicit []."""
    bad_config = dict(BARE_CONFIG)
    del bad_config["deployment_ids"]

    with pytest.raises(config_exc.FromYamlException):
        config_lti.LTIPlatformConfig.from_yaml(CONFIG_PATH, bad_config)
