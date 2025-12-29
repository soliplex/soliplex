#


class SCMException(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)




class APIFetchError(SCMException):
    def __init__(self) -> None:
        super().__init__("Failed to fetch from API")


class GitHubAPIError(SCMException):
    def __init__(self) -> None:
        super().__init__("GitHub API error")


class UnexpectedResponseError(Exception):
    def __init__(self) -> None:
        super().__init__("Unexpected response status")
