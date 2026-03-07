from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum

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


AGUI_FEATURES_BY_NAME = {
    agui_feature.name: agui_feature
    for agui_feature in [
        # Add features here as needed
    ]
}
