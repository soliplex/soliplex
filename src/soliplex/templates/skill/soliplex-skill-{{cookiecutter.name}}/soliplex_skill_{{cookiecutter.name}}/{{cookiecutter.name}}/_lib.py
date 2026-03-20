from pathlib import Path

_SKILL_DIR = Path(__file__).parent
DB_PATH = _SKILL_DIR / "assets" / "{{ cookiecutter.name }}.lancedb"


def get_config():
    config_path = _SKILL_DIR / "assets" / "haiku.rag.yaml"
    if config_path.exists():
        from haiku.rag.config import AppConfig

        return AppConfig.from_yaml(config_path)
    return None
