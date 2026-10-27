"""Project persistence (.platekit.json) and application configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from i18n import detect_system_language
from plate_core.mastermix import MixRecipe
from plate_core.models import Plate
from plate_core.normalization import NormalizationConfig
from plate_core.presets import builtin_recipes

CONFIG_PATH = Path.home() / ".config" / "platekit" / "config.json"


@dataclass
class AppConfig:
    language: str = field(default_factory=detect_system_language)
    theme: str = "dark"
    color_mode: str = "assay"
    recent_files: list[str] = field(default_factory=list)

    def add_recent(self, path: str | Path, max_items: int = 10) -> None:
        p = str(Path(path).resolve())
        self.recent_files = [x for x in self.recent_files if x != p]
        self.recent_files.insert(0, p)
        self.recent_files = self.recent_files[:max_items]

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "theme": self.theme,
            "color_mode": self.color_mode,
            "recent_files": list(self.recent_files),
        }

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        raw_lang = data.get("language")
        lang = str(raw_lang) if raw_lang in ("ru", "en") else detect_system_language()
        return cls(
            language=lang,
            theme=str(data.get("theme", "dark")),
            color_mode=str(data.get("color_mode", "assay")),
            recent_files=[str(x) for x in data.get("recent_files", [])],
        )


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return AppConfig.from_dict(data)
    except Exception:
        pass
    return AppConfig()


def save_config(cfg: AppConfig, path: Path = CONFIG_PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


@dataclass
class PlateProject:
    plate: Plate = field(default_factory=Plate)
    recipe: MixRecipe = field(default_factory=lambda: builtin_recipes()["pcr_standard"].clone())
    norm_config: NormalizationConfig = field(default_factory=NormalizationConfig)

    def to_dict(self) -> dict:
        return {
            "version": "1.0",
            "plate": self.plate.to_dict(),
            "recipe": self.recipe.to_dict(),
            "norm_config": self.norm_config.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> PlateProject:
        plate = Plate.from_dict(data.get("plate", {}))
        recipe_data = data.get("recipe")
        recipe = (
            MixRecipe.from_dict(recipe_data)
            if recipe_data
            else builtin_recipes()["pcr_standard"].clone()
        )
        norm_data = data.get("norm_config")
        norm_config = (
            NormalizationConfig.from_dict(norm_data)
            if norm_data
            else NormalizationConfig()
        )
        return cls(plate=plate, recipe=recipe, norm_config=norm_config)


def save_project(project: PlateProject, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_project(path: str | Path) -> PlateProject:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return PlateProject.from_dict(data)
