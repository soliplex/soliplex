from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum

import pydantic

from . import agents as config_agents

# ============================================================================
#   AGUI feature configuration types
# ============================================================================


class AGUI_FeatureSource(enum.StrEnum):
    CLIENT = "client"
    SERVER = "server"
    EITHER = "either"


@dataclasses.dataclass(kw_only=True)
class AGUI_Feature:
    """Registration of schema and semantics defining a Soliplex AGUI feature

    Features define a contract between the Soliplex client and the Soliplex
    server, describing the schema of a portion of the AG-UI protocol's
    'state' mapping.
    """

    name: str
    """Key within the AG-UI state in which the feature's data is stored"""

    model_klass: type
    """Pydantic model class defining schema for the feature's data"""

    source: AGUI_FeatureSource = AGUI_FeatureSource.EITHER
    """Parties allowed to write to the feature's data in the AG-UI 'state'"""

    @property
    def description(self) -> str:
        schema = self.model_klass.model_json_schema()
        if "description" not in schema:
            return self.model_klass.__name__
        else:
            return schema["description"]

    @property
    def as_yaml(self):
        return {
            "name": self.name,
            "description": self.description,
            "source": str(self.source),
        }

    @property
    def json_schema(self):
        return self.model_klass.model_json_schema()


THINKING_FEATURE_NAME = "thinking"


class ThinkingState(pydantic.BaseModel):
    """How hard the client asks this run's model to think.

    The first feature a client owns rather than reads.  Which levels a
    given room accepts is not here:  it belongs to the model, and the
    room reports it with the rest of the agent.  This says only what
    was asked for, and the run rejects a level its room does not offer.
    """

    level: config_agents.ThinkingLevelName | None = None
    """The level this run is to think at.

    None asks for nothing, which is what leaves the room's own default
    in force.  It is also the value a new thread starts at, so a client
    that never sets one behaves exactly as before the feature existed.
    """


AGUI_FEATURES_BY_NAME = {
    agui_feature.name: agui_feature
    for agui_feature in [
        AGUI_Feature(
            name=THINKING_FEATURE_NAME,
            model_klass=ThinkingState,
            source=AGUI_FeatureSource.CLIENT,
        ),
    ]
}
