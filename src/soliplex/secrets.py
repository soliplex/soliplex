from __future__ import annotations  # forward refs in typing decls

import os
import pathlib
import subprocess


class SecretError(ValueError):
    pass


class UnknownSecret(SecretError):
    def __init__(self, secret_name: str):
        self.secret_name = secret_name
        super().__init__(f"Unknown secret: {secret_name}")


class SecretEnvVarNotFound(SecretError):
    def __init__(self, secret_name: str, env_var: str):
        self.secret_name = secret_name
        self.env_var = env_var
        super().__init__(
            f"Environment variable '{env_var}' "
            f"not set for secret: {secret_name}"
        )


class SecretFilePathNotFound(SecretError):
    def __init__(self, secret_name: str, file_path: pathlib.Path):
        self.secret_name = secret_name
        self.file_path = file_path
        super().__init__(
            f"File path (file_path) not found for secret: {secret_name}",
        )


class SecretSubprocessError(SecretError):
    def __init__(self, secret_name: str, command_line: list[str]):
        self.secret_name = secret_name
        self.command_line = command_line
        super().__init__(
            f"Subprocess command '{command_line}' "
            f"failed for secret: {secret_name}",
        )


class SecretSourcesFailed(ExceptionGroup, SecretError):
    def __init__(self, secret_name, excs):
        self.secret_name = secret_name
        super().__init__(
            f"Could not find secret: {secret_name}",
            excs,
        )


class SecretsNotFound(ExceptionGroup, SecretError):
    def __init__(self, secret_names, excs):
        self.secret_names = secret_names
        super().__init__(
            f"Secrets not found: {secret_names}",
            excs,
        )


def get_env_var_secret(
    source: config_secrets.EnvVarSecretSource,  # noqa F821 avoid cycle
):
    if source._installation_config is not None:
        from_dotenv = source._installation_config.from_dotenv
    else:
        from_dotenv = {}

    merged = os.environ | from_dotenv

    try:
        return merged[source.env_var_name]
    except KeyError as exc:
        raise SecretEnvVarNotFound(
            source.secret_name,
            source.env_var_name,
        ) from exc


def get_file_path_secret(
    source: config_secrets.FilePathSecretSource,  # noqa F821 avoid cycle
):
    file_path = pathlib.Path(source.file_path)
    if not file_path.is_absolute():
        file_path = source._config_path.parent / source.file_path

    try:
        # Strip leading / trailing whitespace
        return file_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SecretFilePathNotFound(
            source.secret_name,
            file_path,
        ) from exc


def get_subprocess_secret(
    source: config_secrets.SubprocessSecretSource,  # noqa F821 avoid cycle
):
    try:
        found = subprocess.check_output(
            [source.command, *source.args],
            encoding="utf8",
        )
    except OSError as exc:
        raise SecretSubprocessError(
            source.secret_name,
            source.command_line,
        ) from exc

    if not found:
        raise SecretSubprocessError(
            source.secret_name,
            source.command_line,
        )

    return found.strip()


def get_random_chars_secret(
    source: config_secrets.RandomCharsSecretSource,  # noqa F821 avoid cycle
):
    return os.urandom(source.n_chars).hex()
