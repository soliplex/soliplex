import asyncio
import json
import logging
from typing import Annotated

import typer

from ..config import SCM
from ..config import settings
from . import app as app

logger = logging.getLogger(__name__)


def init():
    logging.basicConfig(level=settings.log_level)


cli = typer.Typer(no_args_is_help=True)


@cli.command("list-issues")
def ingest_issues(scm: SCM, repo_name: str, owner: str = None):
    issues = asyncio.run(app.get_scm(scm).list_issues(repo_name, owner, add_comments=True))
    for issue in issues:
        print(issue["title"])
        print(issue["body"])


@cli.command("get-repo")
def get_repo(scm: SCM, repo_name: str, owner: str = None):
    print(asyncio.run(app.get_scm(scm).list_repo_files(repo_name, owner, settings.extensions)))


@cli.command("run-inventory")
def run_inventory(
    scm: Annotated[SCM, typer.Argument(help="scm provider")],
    repo_name: Annotated[str, typer.Argument(help="repo name")],
    owner: Annotated[str, typer.Argument(help="repo owner")],
    start_workflows: Annotated[bool, typer.Option(help="start workflows")] = True,
    workflow_definition_id: Annotated[str, typer.Option(help="workflow definition id")] = None,
    param_set_id: Annotated[str, typer.Option(help="param set id")] = None,
    priority: Annotated[int, typer.Option(help="workflow priority")] = 0,
    do_json: Annotated[bool, typer.Option(help="output json")] = False,
):
    res = asyncio.run(
        app.load_inventory(
            scm,
            repo_name,
            owner,
            start_workflows=start_workflows,
            workflow_definition_id=workflow_definition_id,
            param_set_id=param_set_id,
            priority=priority,
        )
    )
    if do_json:
        print(json.dumps(res, indent=2))
    else:
        if "errors" in res and len(res["errors"]) > 0:
            print(f"found {len(res['errors'])} errors:")
            for err in res["errors"]:
                print(err)
        else:
            print("no errors found")
            print(f"found {len(res['inventory'])} files")
            print(f"found {len(res['to_process'])} to process")
            print(f"{len(res['ingested'])} ingested")
            if start_workflows:
                print("workflow result")
                print(json.dumps(res["workflow_result"], indent=2))


if __name__ == "__main__":
    cli()
