import os
import pathlib
import subprocess

from soliplex import config


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


def get_env_var_secret(source: config.EnvVarSecretSource):
    try:
        return os.environ[source.env_var_name]
    except KeyError as exc:
        raise SecretEnvVarNotFound(
            source.secret_name,
            source.env_var_name,
        ) from exc


config.SECRET_GETTERS_BY_KIND[config.EnvVarSecretSource.kind] = (
    get_env_var_secret
)


def get_file_path_secret(source: config.FilePathSecretSource):
    file_path = pathlib.Path(source.file_path)
    if not file_path.is_absolute():
        file_path = source._config_path.parent / source.file_path

    try:
        return file_path.read_text()
    except OSError as exc:
        raise SecretFilePathNotFound(
            source.secret_name,
            file_path,
        ) from exc


config.SECRET_GETTERS_BY_KIND[config.FilePathSecretSource.kind] = (
    get_file_path_secret
)


def get_subprocess_secret(source: config.SubprocessSecretSource):
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


config.SECRET_GETTERS_BY_KIND[config.SubprocessSecretSource.kind] = (
    get_subprocess_secret
)


def get_random_chars_secret(source: config.RandomCharsSecretSource):
    return os.urandom(source.n_chars).hex()


config.SECRET_GETTERS_BY_KIND[config.RandomCharsSecretSource.kind] = (
    get_random_chars_secret
)


def get_secret(secret_config: config.SecretConfig) -> str:
    excs = []
    sources = secret_config.sources
    while secret_config.resolved is None and sources:
        source, *sources = sources
        getter = config.SECRET_GETTERS_BY_KIND[source.kind]
        try:
            secret_config._resolved = getter(source)
        except SecretError as exc:
            excs.append(exc)

    if secret_config.resolved is None:
        raise SecretSourcesFailed(secret_config.secret_name, excs)

    return secret_config.resolved


def resolve_secrets(secret_configs: list[config.SecretConfig]) -> None:
    failed_names = []
    excs = []

    for secret_config in secret_configs:
        try:
            get_secret(secret_config)
        except SecretError as exc:
            failed_names.append(secret_config.secret_name)
            excs.append(exc)

    if failed_names:
        raise SecretsNotFound(",".join(failed_names), excs)
