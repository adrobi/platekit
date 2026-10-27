"""Master Mix calculation engine with dead-volume modes and per-assay breakdowns."""

from __future__ import annotations

from dataclasses import dataclass, field

from plate_core.models import Plate

OVERFILL_MODES = ("percent", "extra_rxn", "multichannel")


@dataclass
class MixComponent:
    name: str
    stock_conc: str = ""
    final_conc: str = ""
    vol_per_rxn_ul: float = 1.0

    def clone(self) -> MixComponent:
        return MixComponent(
            name=self.name,
            stock_conc=self.stock_conc,
            final_conc=self.final_conc,
            vol_per_rxn_ul=float(self.vol_per_rxn_ul),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "stock_conc": self.stock_conc,
            "final_conc": self.final_conc,
            "vol_per_rxn_ul": self.vol_per_rxn_ul,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MixComponent:
        return cls(
            name=str(data.get("name", "Component")),
            stock_conc=str(data.get("stock_conc", "")),
            final_conc=str(data.get("final_conc", "")),
            vol_per_rxn_ul=float(data.get("vol_per_rxn_ul", 0.0)),
        )


@dataclass
class MixLine:
    component: str
    stock_conc: str
    final_conc: str
    vol_1x_ul: float
    vol_total_ul: float
    is_water: bool = False


@dataclass
class AssayMixCalculation:
    assay: str
    well_count: int
    effective_rxns: float
    reaction_volume_ul: float
    template_volume_ul: float
    dispense_per_well_ul: float
    total_mix_volume_ul: float
    lines: list[MixLine]
    exceeds_volume: bool = False


@dataclass
class MixRecipe:
    recipe_id: str = "custom"
    name: str = "Custom PCR Mix"
    reaction_volume_ul: float = 25.0
    template_volume_ul: float = 2.0
    overfill_mode: str = "percent"
    overfill_value: float = 10.0
    components: list[MixComponent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.overfill_mode not in OVERFILL_MODES:
            self.overfill_mode = "percent"

    @property
    def non_water_components_volume_ul(self) -> float:
        return sum(max(0.0, c.vol_per_rxn_ul) for c in self.components)

    @property
    def used_volume_ul(self) -> float:
        return self.non_water_components_volume_ul + max(0.0, self.template_volume_ul)

    @property
    def water_per_rxn_ul(self) -> float:
        rem = self.reaction_volume_ul - self.used_volume_ul
        return round(max(0.0, rem), 4)

    @property
    def dispense_per_well_ul(self) -> float:
        return round(max(0.0, self.reaction_volume_ul - self.template_volume_ul), 4)

    @property
    def exceeds_reaction_volume(self) -> bool:
        return self.used_volume_ul > self.reaction_volume_ul + 1e-6

    def effective_reactions(self, well_count: int) -> float:
        if well_count <= 0:
            return 0.0
        val = max(0.0, float(self.overfill_value))
        if self.overfill_mode == "extra_rxn":
            return round(well_count + val, 4)
        if self.overfill_mode == "multichannel":
            pct = well_count * (1.0 + val / 100.0)
            return round(max(pct, well_count + 2.0), 4)
        return round(well_count * (1.0 + val / 100.0), 4)

    def calculate_for_assay(
        self,
        assay: str,
        well_count: int,
        water_label: str = "Nuclease-free Water",
    ) -> AssayMixCalculation:
        eff = self.effective_reactions(well_count)
        lines: list[MixLine] = []
        water_1x = self.water_per_rxn_ul
        lines.append(
            MixLine(
                component=water_label,
                stock_conc="—",
                final_conc="to vol.",
                vol_1x_ul=water_1x,
                vol_total_ul=round(water_1x * eff, 2),
                is_water=True,
            )
        )
        for comp in self.components:
            v1 = round(max(0.0, comp.vol_per_rxn_ul), 4)
            lines.append(
                MixLine(
                    component=comp.name,
                    stock_conc=comp.stock_conc,
                    final_conc=comp.final_conc,
                    vol_1x_ul=v1,
                    vol_total_ul=round(v1 * eff, 2),
                    is_water=False,
                )
            )
        total_mix = round(sum(line.vol_total_ul for line in lines), 2)
        return AssayMixCalculation(
            assay=assay,
            well_count=well_count,
            effective_rxns=eff,
            reaction_volume_ul=self.reaction_volume_ul,
            template_volume_ul=self.template_volume_ul,
            dispense_per_well_ul=self.dispense_per_well_ul,
            total_mix_volume_ul=total_mix,
            lines=lines,
            exceeds_volume=self.exceeds_reaction_volume,
        )

    def clone(self) -> MixRecipe:
        return MixRecipe(
            recipe_id=self.recipe_id,
            name=self.name,
            reaction_volume_ul=float(self.reaction_volume_ul),
            template_volume_ul=float(self.template_volume_ul),
            overfill_mode=self.overfill_mode,
            overfill_value=float(self.overfill_value),
            components=[c.clone() for c in self.components],
        )

    def to_dict(self) -> dict:
        return {
            "recipe_id": self.recipe_id,
            "name": self.name,
            "reaction_volume_ul": self.reaction_volume_ul,
            "template_volume_ul": self.template_volume_ul,
            "overfill_mode": self.overfill_mode,
            "overfill_value": self.overfill_value,
            "components": [c.to_dict() for c in self.components],
        }

    @classmethod
    def from_dict(cls, data: dict) -> MixRecipe:
        return cls(
            recipe_id=str(data.get("recipe_id", "custom")),
            name=str(data.get("name", "Custom PCR Mix")),
            reaction_volume_ul=float(data.get("reaction_volume_ul", 25.0)),
            template_volume_ul=float(data.get("template_volume_ul", 2.0)),
            overfill_mode=str(data.get("overfill_mode", "percent")),
            overfill_value=float(data.get("overfill_value", 10.0)),
            components=[MixComponent.from_dict(c) for c in data.get("components", [])],
        )


def calculate_plate_mixes(
    plate: Plate,
    recipe: MixRecipe,
    water_label: str = "Nuclease-free Water",
) -> list[AssayMixCalculation]:
    """Calculate Master Mix tables for every occupied assay group on the plate."""
    counts = plate.counts_by_assay()
    results: list[AssayMixCalculation] = []
    for assay, count in counts.items():
        if count > 0:
            results.append(
                recipe.calculate_for_assay(assay, count, water_label=water_label)
            )
    return results
