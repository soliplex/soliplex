"""Gitea SCM provider implementation."""

import logging
from typing import Any

from soliplex.agents.config import settings
from soliplex.agents.scm.base import BaseSCMProvider

logger = logging.getLogger(__name__)


class GiteaProvider(BaseSCMProvider):
    """Gitea implementation of SCM provider."""

    def get_default_owner(self) -> str:
        """Get the default owner from settings."""
        return settings.gitea_owner

    def get_base_url(self) -> str:
        """Get the base API URL for Gitea."""
        return settings.gitea_url

    def get_auth_token(self) -> str:
        """Get the Gitea authentication token."""
        return settings.gitea_token

    def get_last_updated(self, rec: dict[str, Any]) -> str | None:
        """Extract last updated timestamp from Gitea file record."""
        return rec.get("last_committer_date")
