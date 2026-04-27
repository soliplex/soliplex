import pathlib
import typing

import typer

installation_path_type = typing.Annotated[
    pathlib.Path,
    typer.Argument(
        envvar="SOLIPLEX_INSTALLATION_PATH",
        help="Soliplex installation path",
    ),
]
