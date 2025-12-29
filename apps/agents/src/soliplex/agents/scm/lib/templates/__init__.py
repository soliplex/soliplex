from pathlib import Path

import aiofiles
import jinja2

ISSUE_TEMPLATE_NAME = "issue.tpl"


async def get_template(name: str):
    base_dir = Path(__file__).parent
    async with aiofiles.open(base_dir / name) as f:
        tpl = await f.read()
        return jinja2.Template(tpl)


async def render_issue(issue, owner, repo):
    template = await get_template(ISSUE_TEMPLATE_NAME)
    rendered = template.render(issue=issue, owner=owner, repo=repo)
    return rendered
