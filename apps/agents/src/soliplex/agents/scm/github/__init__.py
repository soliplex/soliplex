"""GitHub SCM provider implementation."""

import logging
from typing import Any

import aiohttp

from soliplex.agents.config import settings
from soliplex.agents.scm import GitHubAPIError
from soliplex.agents.scm import SCMException
from soliplex.agents.scm.base import BaseSCMProvider

logger = logging.getLogger(__name__)


class GitHubProvider(BaseSCMProvider):
    """GitHub implementation of SCM provider."""

    def get_default_owner(self) -> str:
        """Get the default owner from settings."""
        return settings.gh_owner

    def get_base_url(self) -> str:
        """Get the base API URL for GitHub."""
        return "https://api.github.com"

    def get_auth_token(self) -> str:
        """Get the GitHub authentication token."""
        return settings.gh_token

    def get_last_updated(self, rec: dict[str, Any]) -> str | None:
        """
        Extract last updated timestamp from GitHub file record.

        GitHub API doesn't provide last updated timestamp in the contents API,
        so this returns None.
        """
        return None

    async def validate_response(self, response: aiohttp.ClientResponse, resp: dict | list) -> None:
        """
        Validate GitHub API response.

        Args:
            response: HTTP response
            resp: Parsed JSON response

        Raises:
            SCMException: If response indicates an error
        """
        if response.status != 200:
            if isinstance(resp, dict) and "message" in resp:
                raise SCMException(str(resp["message"]))
            logger.error(f"GitHub API error: status {response.status}")
            raise GitHubAPIError

        if isinstance(resp, dict) and "errors" in resp:
            raise SCMException(str(resp))

    async def get_file_content(
        self, rec: dict[str, Any], session: aiohttp.ClientSession, owner: str, repo: str
    ) -> dict[str, Any]:
        """
        Get file content, fetching blob if content is empty.

        GitHub sometimes returns empty content for large files,
        requiring a separate blob API call.

        Args:
            rec: File record
            session: HTTP session
            owner: Repository owner
            repo: Repository name

        Returns:
            Updated file record with content
        """
        if "content" not in rec or rec["content"] is None or len(rec["content"]) == 0:
            rec["content"] = await self.get_blob(repo, owner, rec, session)
        return rec

    async def get_blob(self, repo: str, owner: str, rec: dict[str, Any], session: aiohttp.ClientSession) -> bytes:
        """
        Fetch blob content from GitHub API.

        Args:
            repo: Repository name
            owner: Repository owner
            rec: File record with 'sha' field
            session: HTTP session

        Returns:
            Blob content as bytes
        """
        sha = rec["sha"]
        url = self.build_url(f"/repos/{owner}/{repo}/git/blobs/{sha}")
        logger.debug(f"Fetching blob from {url}")

        async with session.get(url) as response:
            response.raise_for_status()
            return await response.read()
