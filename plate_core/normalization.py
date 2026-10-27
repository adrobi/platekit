"""DNA concentration normalization (C1*V1 = C2*V2) and per-reaction template calculator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from plate_core.editing import parse_sample_lines
from plate_core.models import Plate

NORM_MODES = ("dilution_plate", "per_reaction")
QC_STATUSES = ("ok", "too_concentrated", "too_dilute", "missing_conc")


@dataclass
class NormalizationConfig:
    mode: str = "per_reaction"
    target_conc_ng_ul: float = 10.0
    final_volume_ul: float = 20.0
    target_mass_ng: float = 20.0
    max_template_vol_ul: float = 5.0
    min_pipet_vol_ul: float = 0.5

    def __post_init__(self) -> None:
        if self.mode not in NORM_MODES:
            self.mode = "per_reaction"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "target_conc_ng_ul": self.target_conc_ng_ul,
            "final_volume_ul": self.final_volume_ul,
            "target_mass_ng": self.target_mass_ng,
            "max_template_vol_ul": self.max_template_vol_ul,
            "min_pipet_vol_ul": self.min_pipet_vol_ul,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NormalizationConfig:
        return cls(
            mode=str(data.get("mode", "per_reaction")),
            target_conc_ng_ul=float(data.get("target_conc_ng_ul", 10.0)),
            final_volume_ul=float(data.get("final_volume_ul", 20.0)),
            target_mass_ng=float(data.get("target_mass_ng", 20.0)),
            max_template_vol_ul=float(data.get("max_template_vol_ul", 5.0)),
            min_pipet_vol_ul=float(data.get("min_pipet_vol_ul", 0.5)),
        )


@dataclass
class NormalizationRow:
    sample: str
    wells: list[str]
    stock_conc_ng_ul: float | None
    predilution_factor: int
    dna_volume_ul: float
    diluent_volume_ul: float
    final_summary: str
    qc_status: str


def _choose_predilution(raw_vol_ul: float, min_pipet_ul: float, max_vol_ul: float) -> int:
    """Choose a clean laboratory pre-dilution factor (5, 10, 20, 50, 100)."""
    for factor in (5, 10, 20, 50, 100):
        adj = raw_vol_ul * factor
        if min_pipet_ul <= adj <= max_vol_ul:
            return factor
    for factor in (5, 10, 20, 50, 100):
        if raw_vol_ul * factor >= min_pipet_ul:
            return factor
    return 10


def calculate_single_sample(
    sample: str,
    wells: list[str],
    stock_conc: float | None,
    config: NormalizationConfig,
) -> NormalizationRow:
    if stock_conc is None or stock_conc <= 0:
        return NormalizationRow(
            sample=sample,
            wells=wells,
            stock_conc_ng_ul=stock_conc,
            predilution_factor=1,
            dna_volume_ul=0.0,
            diluent_volume_ul=0.0,
            final_summary="—",
            qc_status="missing_conc",
        )

    if config.mode == "dilution_plate":
        max_vol = max(1.0, config.final_volume_ul)
        target_c = max(0.01, config.target_conc_ng_ul)
        raw_v = (target_c * max_vol) / stock_conc

        if raw_v > max_vol + 1e-6:
            actual_c = stock_conc
            return NormalizationRow(
                sample=sample,
                wells=wells,
                stock_conc_ng_ul=stock_conc,
                predilution_factor=1,
                dna_volume_ul=round(max_vol, 2),
                diluent_volume_ul=0.0,
                final_summary=f"{actual_c:.1f} ng/µL (< {target_c:g})",
                qc_status="too_dilute",
            )

        if raw_v < config.min_pipet_vol_ul - 1e-6:
            factor = _choose_predilution(raw_v, config.min_pipet_vol_ul, max_vol)
            adj_v = min(max_vol, raw_v * factor)
            dil_v = max(0.0, max_vol - adj_v)
            return NormalizationRow(
                sample=sample,
                wells=wells,
                stock_conc_ng_ul=stock_conc,
                predilution_factor=factor,
                dna_volume_ul=round(adj_v, 2),
                diluent_volume_ul=round(dil_v, 2),
                final_summary=f"{target_c:g} ng/µL in {max_vol:g} µL (from 1:{factor})",
                qc_status="too_concentrated",
            )

        return NormalizationRow(
            sample=sample,
            wells=wells,
            stock_conc_ng_ul=stock_conc,
            predilution_factor=1,
            dna_volume_ul=round(raw_v, 2),
            diluent_volume_ul=round(max_vol - raw_v, 2),
            final_summary=f"{target_c:g} ng/µL in {max_vol:g} µL",
            qc_status="ok",
        )

    # Mode: per_reaction (fixed DNA mass in ng within max_template_vol_ul)
    max_tmpl = max(0.5, config.max_template_vol_ul)
    target_m = max(0.1, config.target_mass_ng)
    raw_v = target_m / stock_conc

    if raw_v > max_tmpl + 1e-6:
        delivered_ng = stock_conc * max_tmpl
        return NormalizationRow(
            sample=sample,
            wells=wells,
            stock_conc_ng_ul=stock_conc,
            predilution_factor=1,
            dna_volume_ul=round(max_tmpl, 2),
            diluent_volume_ul=0.0,
            final_summary=f"{delivered_ng:.1f} ng (< {target_m:g} ng)",
            qc_status="too_dilute",
        )

    if raw_v < config.min_pipet_vol_ul - 1e-6:
        factor = _choose_predilution(raw_v, config.min_pipet_vol_ul, max_tmpl)
        adj_v = min(max_tmpl, raw_v * factor)
        dil_v = max(0.0, max_tmpl - adj_v)
        return NormalizationRow(
            sample=sample,
            wells=wells,
            stock_conc_ng_ul=stock_conc,
            predilution_factor=factor,
            dna_volume_ul=round(adj_v, 2),
            diluent_volume_ul=round(dil_v, 2),
            final_summary=f"{target_m:g} ng in {max_tmpl:g} µL (from 1:{factor})",
            qc_status="too_concentrated",
        )

    return NormalizationRow(
        sample=sample,
        wells=wells,
        stock_conc_ng_ul=stock_conc,
        predilution_factor=1,
        dna_volume_ul=round(raw_v, 2),
        diluent_volume_ul=round(max_tmpl - raw_v, 2),
        final_summary=f"{target_m:g} ng in {max_tmpl:g} µL",
        qc_status="ok",
    )


def calculate_normalization(
    plate: Plate,
    config: NormalizationConfig,
    override_concs: dict[str, float | None] | None = None,
) -> list[NormalizationRow]:
    """Calculate normalization rows for all non-control samples on the plate."""
    sample_wells: dict[str, list[str]] = {}
    sample_conc: dict[str, float | None] = {}

    for w in plate.occupied_wells(direction="row"):
        if w.role in ("ntc", "pos", "std") and not w.sample:
            continue
        if w.role in ("ntc", "pos", "std") and w.sample.upper() in ("NTC", "POS") or w.role == "std":
            continue
        if not w.sample:
            continue
        sample_wells.setdefault(w.sample, []).append(w.coord)
        if sample_conc.get(w.sample) is None and w.concentration is not None:
            sample_conc[w.sample] = w.concentration

    if override_concs:
        for s_name, c_val in override_concs.items():
            if s_name not in sample_wells:
                sample_wells[s_name] = []
            sample_conc[s_name] = c_val

    rows: list[NormalizationRow] = []
    for s_name, w_list in sample_wells.items():
        c_val = sample_conc.get(s_name)
        rows.append(calculate_single_sample(s_name, w_list, c_val, config))
    return rows


def parse_concentration_table(text: str) -> dict[str, float]:
    """Parse sample concentrations from pasted or CSV text."""
    pairs = parse_sample_lines(text)
    return {name: conc for name, conc in pairs if conc is not None}


def import_concentrations_file(path: str | Path) -> dict[str, float]:
    content = Path(path).read_text(encoding="utf-8-sig")
    return parse_concentration_table(content)


def apply_concentrations_to_plate(plate: Plate, concs: dict[str, float]) -> int:
    """Update sample concentrations on all matching wells on the plate."""
    updated = 0
    for w in plate.iter_wells():
        if w.sample and w.sample in concs:
            w.concentration = float(concs[w.sample])
            updated += 1
    return updated
