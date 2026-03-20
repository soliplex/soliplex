from pathlib import Path

from haiku.rag.skills import rag as hr_rag
from haiku.skills.models import Skill

_TOOL_NAMES = {{ cookiecutter.tool_names.split()|tojson }}
_SKILL_DIR = Path(__file__).parent / "{{ cookiecutter.name }}"
_DB_PATH = _SKILL_DIR / "assets" / "{{ cookiecutter.name }}.lancedb"


def create_skill() -> Skill:
    config = None
    config_path = _SKILL_DIR / "assets" / "haiku.rag.yaml"
    if config_path.exists():
        from haiku.rag.config import AppConfig

        config = AppConfig.from_yaml(config_path)

    skill = hr_rag.create_skill(db_path=_DB_PATH, config=config)
    skill.tools = [
        t for t in skill.tools if t.__name__ in _TOOL_NAMES
    ]
    skill.metadata.name = "{{ cookiecutter.name }}"
    skill.metadata.description = "{{ cookiecutter.description }}"
    skill.path = _SKILL_DIR
    return skill
