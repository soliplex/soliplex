"""Abstract base class for SCM (Source Control Management) providers."""

import asyncio
import logging
import mimetypes
import random
from abc import ABC
from abc import abstractmethod
from collections.abc import AsyncIterator
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import aiohttp

from soliplex.agents.config import settings
from soliplex.agents.scm import APIFetchError
from soliplex.agents.scm import SCMException
from soliplex.agents.scm.lib.utils import compute_file_hash
from soliplex.agents.scm.lib.utils import decode_base64_if_needed
from soliplex.agents.scm.lib.utils import flatten_list

logger = logging.getLogger(__name__)


class BaseSCMProvider(ABC):
    """Abstract base class for SCM providers (GitHub, Gitea, etc.)."""

    def __init__(self, owner: str | None = None):
        """
        Initialize SCM provider.

        Args:
            owner: Default repository owner
        """
        self.owner = owner or self.get_default_owner()

    @abstractmethod
    def get_default_owner(self) -> str:
        """Get the default owner from settings."""
        pass  # pragma: no cover

    @abstractmethod
    def get_base_url(self) -> str:
        """Get the base API URL for this provider."""
        pass  # pragma: no cover

    @abstractmethod
    def get_auth_token(self) -> str:
        """Get the authentication token from settings."""
        pass  # pragma: no cover

    @asynccontextmanager
    async def get_session(self):
        """Create an authenticated HTTP session."""
        headers = {"Authorization": f"token {self.get_auth_token()}"}
        async with aiohttp.ClientSession(headers=headers) as session:
            yield session

    def build_url(self, path: str) -> str:
        """
        Build full URL from base URL and path.

        Args:
            path: API endpoint path

        Returns:
            Full URL
        """
        base_url = self.get_base_url().rstrip("/")
        path = path.lstrip("/")
        return f"{base_url}/{path}"

    async def paginate(
        self, url_template: str, owner: str, repo: str, process_response: Callable | None = None
    ) -> list[dict[str, Any]]:
        """
        Paginate through API responses.

        Args:
            url_template: URL template with {page} placeholder
            owner: Repository owner
            repo: Repository name
            process_response: Optional function to process each response

        Returns:
            List of all items from all pages
        """
        ret = []
        items = []
        page = 1

        while len(items) != 0 or page == 1:
            url = url_template.format(owner=owner, repo=repo, page=page)
            logger.info(f"fetching page={page} {owner}/{repo}")

            async with self.get_session() as session:
                async with session.get(url) as response:
                    if response.status == 404:
                        msg = f"repo {owner}/{repo} not found"
                        raise SCMException(msg)

                    items = await response.json()

                    if response.status != 200:
                        if "errors" in items:
                            raise SCMException(str(items["errors"]))
                        logger.error(f"Failed to fetch from {url}: {items}")
                        raise APIFetchError

                    if process_response:
                        items = process_response(items)

                    logger.info(f"found {len(items)} items on page {page}")
                    ret.extend(items)
                    page += 1

        return ret

    async def list_issues(self, repo: str, owner: str | None = None, add_comments: bool = False) -> list[dict[str, Any]]:
        """
        List all issues for a repository.

        Args:
            repo: Repository name
            owner: Repository owner (defaults to instance owner)
            add_comments: Whether to include comments for each issue

        Returns:
            List of issue dictionaries
        """
        owner = owner or self.owner
        url_template = self.build_url("/repos/{owner}/{repo}/issues?page={page}&status=all")
        issues = await self.paginate(url_template, owner, repo)

        if add_comments:
            comments = await self.list_repo_comments(owner, repo)
            for issue in issues:
                issue["comments"] = [comment["body"] for comment in comments if comment["issue_url"] == issue["url"]]
                issue["comment_count"] = len(issue["comments"])

        return issues

    async def list_repo_comments(self, owner: str | None, repo: str) -> list[dict[str, Any]]:
        """
        List all issue comments for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            List of comment dictionaries
        """
        owner = owner or self.owner
        url_template = self.build_url("/repos/{owner}/{repo}/issues/comments?page={page}")
        return await self.paginate(url_template, owner, repo)

    def parse_file_rec(self, rec: dict[str, Any]) -> dict[str, Any]:
        """
        Parse a file record from the API response.

        Args:
            rec: File record from API

        Returns:
            Normalized file dictionary with metadata
        """
        file_bytes = decode_base64_if_needed(rec["content"])
        file_hash = compute_file_hash(file_bytes)
        uri = rec["path"]

        return {
            "name": rec["name"],
            "url": rec["url"],
            "uri": uri,
            "path": uri,
            "file_bytes": file_bytes,
            "sha256": file_hash,
            "content-type": mimetypes.guess_type(rec["name"])[0],
            "last_updated": self.get_last_updated(rec),
        }

    @abstractmethod
    def get_last_updated(self, rec: dict[str, Any]) -> str | None:
        """
        Extract last updated timestamp from file record.

        Args:
            rec: File record from API

        Returns:
            Last updated timestamp or None if not available
        """
        pass  # pragma: no cover

    async def get_file_content(
        self, rec: dict[str, Any], session: aiohttp.ClientSession, owner: str, repo: str
    ) -> dict[str, Any]:
        """
        Get file content, handling special cases like empty content.

        Default implementation returns the record as-is. Override for provider-specific behavior.

        Args:
            rec: File record
            session: HTTP session
            owner: Repository owner
            repo: Repository name

        Returns:
            Updated file record with content
        """
        return rec

    async def get_data_from_url(
        self, url: str, session: aiohttp.ClientSession, owner: str | None = None, repo: str | None = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Recursively fetch data from API URL.

        Args:
            url: API URL to fetch
            session: HTTP session
            owner: Repository owner (optional, for provider-specific handling)
            repo: Repository name (optional, for provider-specific handling)

        Returns:
            Parsed file record or list of records
        """
        logger.debug(f"get_data_from_url = {url}")

        # Add small sleep to avoid rate limiting
        await asyncio.sleep(random.randint(1, 5) * 0.01)

        try:
            async with session.get(url) as response:
                response.raise_for_status()
                res = await response.json()

                if isinstance(res, dict):
                    # This is a file, fetch content if needed and parse
                    if owner and repo:
                        res = await self.get_file_content(res, session, owner, repo)
                    return self.parse_file_rec(res)
                else:
                    # This is a directory, recursively fetch all files
                    parsed = []
                    for r in res:
                        logger.debug(f"fetching file in dir for url = {r['url']}")
                        parsed.append(await self.get_data_from_url(r["url"], session, owner, repo))
                    return parsed

        except aiohttp.ClientError as e:
            logger.exception(f"Error fetching from {url}")
            return {"error": str(e)}

    async def list_repo_files(
        self,
        repo: str,
        owner: str | None = None,
        allowed_extensions: list[str] | None = None,
        branch: str = "main",
    ) -> list[dict[str, Any]]:
        """
        List all files in a repository.

        Args:
            repo: Repository name
            owner: Repository owner (defaults to instance owner)
            allowed_extensions: List of allowed file extensions
            branch: Branch name

        Returns:
            List of file dictionaries
        """
        owner = owner or self.owner
        allowed_extensions = allowed_extensions or settings.extensions
        url = self.build_url(f"/repos/{owner}/{repo}/contents?ref={branch}")

        logger.debug(f"url = {url}")

        async with self.get_session() as session:
            async with session.get(url) as response:
                resp = await response.json()

                await self.validate_response(response, resp)

                files = [x for x in resp if x["type"] == "file"]
                dirs = [x for x in resp if x["type"] == "dir"]
                logger.debug(f"dirs={[(x['name'], x['type']) for x in resp]}")

                tasks = [
                    self.get_data_from_url(file["url"], session, owner, repo)
                    for file in files
                    if file["name"].split(".")[-1] in allowed_extensions
                ]
                for dir in dirs:
                    tasks.append(self.get_data_from_url(dir["url"], session, owner, repo))

                ret = await asyncio.gather(*tasks)
                ret = flatten_list(ret)
                logger.info(f"found {len(ret)} files in {repo}")
                return ret

    async def iter_repo_files(self, repo: str, owner: str | None = None, branch: str = "main") -> AsyncIterator[dict[str, Any]]:
        """
        Iterate through repository files.

        Args:
            repo: Repository name
            owner: Repository owner (defaults to instance owner)
            branch: Branch name

        Yields:
            File dictionaries
        """
        owner = owner or self.owner
        url = self.build_url(f"/repos/{owner}/{repo}/contents?ref={branch}")

        logger.debug(f"url = {url}")

        async with self.get_session() as session:
            async with session.get(url) as response:
                resp = await response.json()

                await self.validate_response(response, resp)

                files = [x for x in resp if x["type"] == "file"]
                dirs = [x for x in resp if x["type"] == "dir"]
                logger.debug(f"dirs={[(x['name'], x['type']) for x in resp]}")

                tasks = [self.get_data_from_url(file["url"], session, owner, repo) for file in files]
                for dir in dirs:
                    tasks.append(self.get_data_from_url(dir["url"], session, owner, repo))

                ct = 0
                for task in tasks:
                    ret = await task
                    # Handle both single files and lists
                    items = ret if isinstance(ret, list) else [ret]
                    for item in flatten_list(items):
                        ct += 1
                        yield item

                logger.info(f"found {ct} files in {repo}")

    async def validate_response(self, response: aiohttp.ClientResponse, resp: dict | list) -> None:
        """
        Validate API response and raise exceptions if needed.

        Default implementation checks for 'errors' key. Override for provider-specific validation.

        Args:
            response: HTTP response
            resp: Parsed JSON response

        Raises:
            SCMException: If response indicates an error
        """
        if isinstance(resp, dict) and "errors" in resp:
            raise SCMException(str(resp))
