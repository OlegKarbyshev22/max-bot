from pathlib import Path
import yaml
from agent.src.config.models import (RolesConfig, RoutesConfig)

BASE_DIR = Path(__file__).resolve().parent

def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not data:
        raise ValueError(f"Config file is empty: {path}")

    return data

def load_routes_config() -> RoutesConfig:
    raw = _load_yaml(BASE_DIR / "routes.yml")
    return RoutesConfig.model_validate(raw)

def load_roles_config() -> RolesConfig:
    raw = _load_yaml(BASE_DIR / "roles.yml")
    return RolesConfig.model_validate(raw)