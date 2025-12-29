import hashlib
import logging

from soliplex.agents.scm.base import BaseSCMProvider

from .. import client
from ..config import SCM
from ..config import settings
from . import gitea
from . import github
from .lib import templates

logger = logging.getLogger(__name__)


def get_scm(scm) -> BaseSCMProvider:
    if scm == SCM.GITEA:
        return gitea.GiteaProvider()
    elif scm == SCM.GITHUB:
        return github.GitHubProvider()
    else:
        raise ValueError(scm)


async def load_inventory(
    scm: str,
    repo_name: str,
    owner: str = None,
    resume_batch: int | None = None,
    priority: int = 0,
    start_workflows: bool = False,
    workflow_definition_id: str | None = None,
    param_set_id: str | None = None,
):
    data = await get_data(scm, repo_name, owner)

    source = f"{scm.value}:{owner}:{repo_name}"
    to_process = await client.check_status(data, source)
    ret = {"inventory": data, "to_process": to_process}
    logger.info(f"found {len(to_process)} to process")
    if len(to_process) == 0:
        logger.info("nothing to process. exiting")
        return ret
    found_batch_id = client.find_batch_for_source(source)
    if found_batch_id:
        logger.info(f"found batch {found_batch_id} for {source}")
        batch_id = found_batch_id
    else:
        logger.info(f"no batch found for {source}. creating")
        batch_id = await client.create_batch(
            source,
            source,
        )
    logger.info(f"batch_id={batch_id}")
    errors = []
    ingested = []
    for row in to_process:
        meta = row["metadata"].copy()
        for k in [
            "path",
            "sha256",
            "size",
            "source",
            "batch_id",
            "source_uri",
        ]:
            if k in meta:
                del meta[k]
        logger.info(f"starting ingest for {row['uri']}")
        mime_type = None
        if "metadata" in row and "content-type" in row["metadata"]:
            mime_type = row["metadata"]["content-type"]
        res = await client.do_ingest(
            row["body"],
            row["uri"],
            meta,
            source,
            batch_id,
            mime_type,
        )
        if "error" in res:
            logger.error(f"Error ingesting {row['uri']}: {res['error']}")
            res["uri"] = row["uri"]
            res["source"] = source
            res["resumed_batch"] = resume_batch
            res["batch_id"] = batch_id
            errors.append(res)
        else:
            ingested.append(row["uri"])
    wf_res = None
    if len(errors) == 0 and start_workflows:
        wf_res = await client.do_start_workflows(
            batch_id,
            workflow_definition_id,
            param_set_id,
            priority,
        )
    ret["ingested"] = ingested
    ret["errors"] = errors
    ret["workflow_result"] = wf_res
    return ret


async def get_data(scm: str, repo_name: str, owner: str = None):
    impl = get_scm(scm)

    allowed_extensions = settings.extensions
    files = await impl.list_repo_files(repo_name, owner, allowed_extensions=allowed_extensions)

    issues = await impl.list_issues(repo=repo_name, owner=owner, add_comments=True)
    doc_data = []
    filtered_files = [x for x in files if x["name"].split(".")[-1] in allowed_extensions]
    for f in filtered_files:
        txt = f["file_bytes"]
        row = {
            "body": txt,
            "uri": f["uri"],
            "sha256": f["sha256"],
            "metadata": {
                "last_modified_date": f["last_updated"],
                "content-type": f["content-type"],
            },
        }
        doc_data.append(row)
    for issue in issues:
        txt = await templates.render_issue(issue, owner, repo_name)

        row = {
            "body": txt,
            "uri": f"/{owner}/{repo_name}/issues/{issue['number']}",
            "title": issue["title"],
            "metadata": {
                "date": issue["created_at"],
                "assignee": str(issue["assignee"]),
                "state": issue["state"],
                "comments": issue["comment_count"],
                "title": issue["title"],
                "content-type": "text/markdown",
            },
        }
        row["sha256"] = hashlib.sha256(row["body"].encode("utf-8")).hexdigest()

        doc_data.append(row)

    return doc_data
