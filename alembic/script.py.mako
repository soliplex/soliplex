<%!
import re

%>"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
import typing

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: typing.Union[str, typing.Sequence[str], None] = ${repr(down_revision)}
branch_labels: typing.Union[str, typing.Sequence[str], None] = ${repr(branch_labels)}
depends_on: typing.Union[str, typing.Sequence[str], None] = ${repr(depends_on)}


def upgrade(engine_name: str) -> None:
    """Upgrade schema."""
    globals()[f"upgrade_{engine_name}"]()


def downgrade(engine_name: str) -> None:
    """Downgrade schema."""
    globals()[f"downgrade_{engine_name}"]()

<%
    db_names = config.get_main_option("databases")
%>

## generate an "upgrade_<xyz>() / downgrade_<xyz>()" function
## for each database name in the ini file.

% for db_name in re.split(r',\s*', db_names):

def upgrade_${db_name}() -> None:
    """Upgrade ${db_name} schema."""
    ${context.get("%s_upgrades" % db_name, "pass")}


def downgrade_${db_name}() -> None:
    """Downgrade ${db_name} schema."""
    ${context.get("%s_downgrades" % db_name, "pass")}

% endfor
