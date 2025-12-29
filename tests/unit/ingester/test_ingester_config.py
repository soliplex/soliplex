import logging

import soliplex.ingester.lib.config as cfg

logger = logging.getLogger(__name__)


def test_config_settings(monkeypatch):
    logger.info("test_config_settings started")
    settings = cfg.get_settings()
    assert settings
    logger.info(f"settings={settings}")
