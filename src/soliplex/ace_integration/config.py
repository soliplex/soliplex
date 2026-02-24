import dataclasses


@dataclasses.dataclass(kw_only=True)
class ACERoomConfig:
    """ACE learning configuration for a room."""

    enabled: bool = False
    learning_model: str = "gpt-4o-mini"
    auto_learn_on_feedback: bool = True
