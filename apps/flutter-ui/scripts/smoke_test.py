#!/usr/bin/env python3
"""
Smoke test harness for validating Soliplex API endpoints.

This script validates the API endpoints match the expected structure
as defined in SOLIPLEX.md and the Flutter UrlBuilder utility.

Usage:
    python scripts/smoke_test.py [--base-url URL] [--room-id ROOM] [--verbose]

Examples:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --base-url https://api.example.com
    python scripts/smoke_test.py --base-url http://localhost:8000 \
        --room-id genui --verbose
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from enum import Enum

try:
    import requests
except ImportError:
    print(
        "Error: 'requests' package required. "
        "Install with: pip install requests"
    )
    sys.exit(1)


class TestStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    WARN = "WARN"


@dataclass
class TestResult:
    name: str
    status: TestStatus
    message: str
    duration_ms: float
    response_code: int | None = None
    details: str | None = None


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    GRAY = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Colors.RESET}"


class SmokeTestHarness:
    """Smoke test harness for Soliplex API endpoints."""

    def __init__(
        self,
        base_url: str,
        room_id: str = "genui",
        auth_token: str | None = None,
        verbose: bool = False,
        timeout: int = 10,
    ):
        self.base_url = self._normalize_url(base_url)
        self.api_base = f"{self.base_url}/api/v1"
        self.room_id = room_id
        self.auth_token = auth_token
        self.verbose = verbose
        self.timeout = timeout
        self.results: list[TestResult] = []

        # State for dependent tests
        self.thread_id: str | None = None
        self.run_id: str | None = None

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to bare server format (no /api suffix)."""
        url = url.strip().rstrip("/")
        # Strip /api and version suffix
        import re

        url = re.sub(r"/api(/v\d+)?$", "", url)
        return url

    def _get_headers(self) -> dict:
        """Get request headers including auth if available."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _log(self, message: str, level: str = "info"):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            prefix = {
                "info": colorize("[INFO]", Colors.BLUE),
                "debug": colorize("[DEBUG]", Colors.GRAY),
                "warn": colorize("[WARN]", Colors.YELLOW),
                "error": colorize("[ERROR]", Colors.RED),
            }.get(level, "[INFO]")
            print(f"  {prefix} {message}")

    def _run_test(
        self,
        name: str,
        method: str,
        endpoint: str,
        expected_codes: list[int],
        body: dict | None = None,
        skip_if: str | None = None,
    ) -> tuple[TestResult, dict | None]:
        """Run a single endpoint test. Returns (result, response_json)."""
        if skip_if:
            return TestResult(
                name=name,
                status=TestStatus.SKIP,
                message=f"Skipped: {skip_if}",
                duration_ms=0,
            ), None

        url = f"{self.api_base}{endpoint}"
        self._log(f"{method} {url}", "debug")

        start_time = time.time()
        response_json = None
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                json=body,
                timeout=self.timeout,
            )
            duration_ms = (time.time() - start_time) * 1000

            # Try to parse JSON response
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                pass

            if response.status_code in expected_codes:
                status = TestStatus.PASS
                message = f"HTTP {response.status_code}"
            elif response.status_code == 401:
                status = TestStatus.WARN
                message = (
                    "Auth required (401) - endpoint exists but needs token"
                )
            elif response.status_code == 404:
                status = TestStatus.FAIL
                message = "Endpoint not found (404)"
            else:
                status = TestStatus.FAIL
                message = f"Unexpected HTTP {response.status_code}"

            # Format details for verbose output
            details = None
            if self.verbose and response.text:
                try:
                    details = json.dumps(response.json(), indent=2)[:500]
                except json.JSONDecodeError:
                    details = response.text[:200]

            return TestResult(
                name=name,
                status=status,
                message=message,
                duration_ms=duration_ms,
                response_code=response.status_code,
                details=details,
            ), response_json

        except requests.exceptions.ConnectionError:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                name=name,
                status=TestStatus.FAIL,
                message="Connection refused - is server running?",
                duration_ms=duration_ms,
            ), None
        except requests.exceptions.Timeout:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                name=name,
                status=TestStatus.FAIL,
                message=f"Timeout after {self.timeout}s",
                duration_ms=duration_ms,
            ), None
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                name=name,
                status=TestStatus.FAIL,
                message=f"Error: {str(e)}",
                duration_ms=duration_ms,
            ), None

    def test_server_reachable(self) -> TestResult:
        """Test if server is reachable at all."""
        url = f"{self.base_url}/api/login"
        self._log(f"Testing server reachability: {url}", "debug")

        start_time = time.time()
        try:
            response = requests.get(url, timeout=self.timeout)
            duration_ms = (time.time() - start_time) * 1000

            # Any response means server is up
            return TestResult(
                name="Server Reachable",
                status=TestStatus.PASS,
                message=f"Server responded with HTTP {response.status_code}",
                duration_ms=duration_ms,
                response_code=response.status_code,
            )
        except requests.exceptions.ConnectionError:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                name="Server Reachable",
                status=TestStatus.FAIL,
                message=f"Cannot connect to {self.base_url}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                name="Server Reachable",
                status=TestStatus.FAIL,
                message=str(e),
                duration_ms=duration_ms,
            )

    def test_rooms_list(self) -> TestResult:
        """Test GET /api/v1/rooms

        - List all rooms.
        """
        result, _ = self._run_test(
            name="GET /rooms",
            method="GET",
            endpoint="/rooms",
            expected_codes=[200],
        )
        return result

    def test_room_details(self) -> TestResult:
        """Test GET /api/v1/rooms/{room_id}

        - Get room details.
        """
        result, _ = self._run_test(
            name=f"GET /rooms/{self.room_id}",
            method="GET",
            endpoint=f"/rooms/{self.room_id}",
            expected_codes=[200],
        )
        return result

    def test_room_threads(self) -> TestResult:
        """Test GET /api/v1/rooms/{room_id}/agui

        - List threads in room.
        """
        result, _ = self._run_test(
            name=f"GET /rooms/{self.room_id}/agui",
            method="GET",
            endpoint=f"/rooms/{self.room_id}/agui",
            expected_codes=[200],
        )
        return result

    def test_create_thread(self) -> TestResult:
        """Test POST /api/v1/rooms/{room_id}/agui

        - Create thread.
        """
        result, data = self._run_test(
            name=f"POST /rooms/{self.room_id}/agui",
            method="POST",
            endpoint=f"/rooms/{self.room_id}/agui",
            expected_codes=[200, 201],
            body={},
        )

        # Extract thread_id and run_id for subsequent tests
        if result.status == TestStatus.PASS and data:
            self.thread_id = data.get("thread_id")
            runs = data.get("runs", {})
            if runs:
                self.run_id = list(runs.keys())[0]
            self._log(
                f"Created thread: {self.thread_id}, run: {self.run_id}", "info"
            )

        return result

    def test_get_thread(self) -> TestResult:
        """Test GET /api/v1/rooms/{room_id}/agui/{thread_id}

        - Get thread details.
        """
        skip_reason = (
            None if self.thread_id else "No thread_id from previous test"
        )

        result, _ = self._run_test(
            name=f"GET /rooms/{self.room_id}/agui/{{thread_id}}",
            method="GET",
            endpoint=f"/rooms/{self.room_id}/agui/{self.thread_id}"
            if self.thread_id
            else "",
            expected_codes=[200],
            skip_if=skip_reason,
        )
        return result

    def test_create_run(self) -> TestResult:
        """Test POST /api/v1/rooms/{room_id}/agui/{thread_id}

        - Create run.
        """
        skip_reason = (
            None if self.thread_id else "No thread_id from previous test"
        )

        result, data = self._run_test(
            name=f"POST /rooms/{self.room_id}/agui/{{thread_id}}",
            method="POST",
            endpoint=f"/rooms/{self.room_id}/agui/{self.thread_id}"
            if self.thread_id
            else "",
            expected_codes=[200, 201],
            body={},
            skip_if=skip_reason,
        )

        # Extract new run_id
        if result.status == TestStatus.PASS and data:
            new_run_id = data.get("run_id")
            if new_run_id:
                self.run_id = new_run_id
                self._log(f"Created run: {self.run_id}", "info")

        return result

    def test_get_run(self) -> TestResult:
        """Test GET /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}

        - Get run details.
        """
        skip_reason = None
        if not self.thread_id:
            skip_reason = "No thread_id from previous test"
        elif not self.run_id:
            skip_reason = "No run_id from previous test"

        result, _ = self._run_test(
            name=f"GET /rooms/{self.room_id}/agui/{{thread_id}}/{{run_id}}",
            method="GET",
            endpoint=f"/rooms/{self.room_id}/agui/{self.thread_id}/{self.run_id}"
            if self.thread_id and self.run_id
            else "",
            expected_codes=[200],
            skip_if=skip_reason,
        )
        return result

    def test_cancel_run(self) -> TestResult:
        """Test POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/cancel

        - Cancel run.
        """
        skip_reason = None
        if not self.thread_id:
            skip_reason = "No thread_id from previous test"
        elif not self.run_id:
            skip_reason = "No run_id from previous test"

        result, _ = self._run_test(
            name="POST .../{thread_id}/{run_id}/cancel",
            method="POST",
            endpoint=f"/rooms/{self.room_id}/agui/{self.thread_id}/{self.run_id}/cancel"
            if self.thread_id and self.run_id
            else "",
            expected_codes=[
                200,
                204,
                404,
            ],  # 404 is ok if run already finished
            body={},
            skip_if=skip_reason,
        )
        return result

    def run_all_tests(self) -> list[TestResult]:
        """Run all smoke tests in sequence."""
        print(f"\n{Colors.BOLD}Soliplex API Smoke Tests{Colors.RESET}")
        print(f"Base URL: {self.base_url}")
        print(f"API Base: {self.api_base}")
        print(f"Room ID:  {self.room_id}")
        print("-" * 60)

        tests = [
            self.test_server_reachable,
            self.test_rooms_list,  # GET /rooms
            self.test_room_details,  # GET /rooms/{id}
            self.test_room_threads,  # GET /rooms/{id}/agui (list threads)
            self.test_create_thread,  # POST /rooms/{id}/agui
            self.test_get_thread,  # GET /rooms/{id}/agui/{thread_id}
            self.test_create_run,  # POST /rooms/{id}/agui/{thread_id}
            self.test_get_run,  # GET /rooms/{id}/agui/{thread_id}/{run_id}
            self.test_cancel_run,  # POST .../cancel
        ]

        for test_fn in tests:
            result = test_fn()
            self.results.append(result)
            self._print_result(result)

            # Stop early if server is unreachable
            if (
                result.name == "Server Reachable"
                and result.status == TestStatus.FAIL
            ):
                abort_text = colorize(
                    "Aborting: Server not reachable",
                    Colors.RED,
                )
                print(f"\n{abort_text}")
                break

        return self.results

    def _print_result(self, result: TestResult):
        """Print a single test result."""
        status_colors = {
            TestStatus.PASS: Colors.GREEN,
            TestStatus.FAIL: Colors.RED,
            TestStatus.SKIP: Colors.GRAY,
            TestStatus.WARN: Colors.YELLOW,
        }
        status_str = colorize(
            f"[{result.status.value}]", status_colors[result.status]
        )
        duration_str = colorize(f"({result.duration_ms:.0f}ms)", Colors.GRAY)

        print(f"  {status_str} {result.name}: {result.message} {duration_str}")

        if self.verbose and result.details:
            for line in result.details.split("\n")[:10]:
                print(colorize(f"         {line}", Colors.GRAY))

    def print_summary(self):
        """Print test summary."""
        print("-" * 60)

        passed = sum(1 for r in self.results if r.status == TestStatus.PASS)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAIL)
        warned = sum(1 for r in self.results if r.status == TestStatus.WARN)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIP)
        total = len(self.results)

        summary_parts = []
        if passed:
            summary_parts.append(colorize(f"{passed} passed", Colors.GREEN))
        if failed:
            summary_parts.append(colorize(f"{failed} failed", Colors.RED))
        if warned:
            summary_parts.append(colorize(f"{warned} warnings", Colors.YELLOW))
        if skipped:
            summary_parts.append(colorize(f"{skipped} skipped", Colors.GRAY))

        print(f"\nResults: {', '.join(summary_parts)} ({total} total)")

        total_time = sum(r.duration_ms for r in self.results)
        print(f"Total time: {total_time:.0f}ms")

        if failed > 0:
            print(f"\n{colorize('SMOKE TEST FAILED', Colors.RED)}")
            return 1
        elif warned > 0:
            warn_txt = colorize(
                "SMOKE TEST PASSED WITH WARNINGS",
                Colors.YELLOW,
            )
            print(f"\n{warn_txt}")
            return 0
        else:
            print(f"\n{colorize('SMOKE TEST PASSED', Colors.GREEN)}")
            return 0


def main():
    parser = argparse.ArgumentParser(
        description="Smoke test harness for Soliplex API endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--room-id",
        default="genui",
        help="Room ID to test (default: genui)",
    )
    parser.add_argument(
        "--auth-token",
        help="Bearer token for authenticated endpoints",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output with response details",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds (default: 10)",
    )

    args = parser.parse_args()

    harness = SmokeTestHarness(
        base_url=args.base_url,
        room_id=args.room_id,
        auth_token=args.auth_token,
        verbose=args.verbose,
        timeout=args.timeout,
    )

    harness.run_all_tests()
    exit_code = harness.print_summary()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
