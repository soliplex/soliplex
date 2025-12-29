import logging
import os

import typer

import soliplex.agents.fs.cli as fs
import soliplex.agents.scm.cli as scm

logger = logging.getLogger(__name__)


def init():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


cli = typer.Typer(no_args_is_help=True, callback=init)

cli.add_typer(fs.cli, name="fs")
cli.add_typer(scm.cli, name="scm")
