"""Unit tests for plate_core.normalization."""

from __future__ import annotations

import pytest

from plate_core.editing import build_demo_plate
from plate_core.models import Plate
from plate_core.normalization import (
    NormalizationConfig,
    apply_concentrations_to_plate,
    calculate_normalization,
    calculate_single_sample,
    parse_concentration_table,
)


def test_per_reaction_normalization_qc_flags():
    cfg = NormalizationConfig(
        mode="per_reaction",
        target_mass_ng=20.0,
        max_template_vol_ul=5.0,
        min_pipet_vol_ul=0.5,
    )

    # Normal sample: 25 ng/uL -> 20 / 25 = 0.8 uL DNA + 4.2 uL water
    r_ok = calculate_single_sample("S_OK", ["A1"], 25.0, cfg)
    assert r_ok.qc_status == "ok"
    assert r_ok.predilution_factor == 1
    assert r_ok.dna_volume_ul == pytest.approx(0.8)
    assert r_ok.diluent_volume_ul == pytest.approx(4.2)

    # Too concentrated: 200 ng/uL -> 0.1 uL (< 0.5 uL) -> recommends pre-dilution
    r_high = calculate_single_sample("S_HIGH", ["A2"], 200.0, cfg)
    assert r_high.qc_status == "too_concentrated"
    assert r_high.predilution_factor >= 5
    assert r_high.dna_volume_ul >= cfg.min_pipet_vol_ul

    # Too dilute: 2.0 ng/uL -> needs 10 uL (> 5.0 uL max)
    r_low = calculate_single_sample("S_LOW", ["A3"], 2.0, cfg)
    assert r_low.qc_status == "too_dilute"
    assert r_low.dna_volume_ul == pytest.approx(5.0)
    assert r_low.diluent_volume_ul == pytest.approx(0.0)

    # Missing concentration
    r_miss = calculate_single_sample("S_MISS", ["A4"], None, cfg)
    assert r_miss.qc_status == "missing_conc"


def test_dilution_plate_mode():
    cfg = NormalizationConfig(
        mode="dilution_plate",
        target_conc_ng_ul=10.0,
        final_volume_ul=20.0,
        min_pipet_vol_ul=0.5,
    )
    # C1=50 ng/uL, C2=10 ng/uL, V2=20 uL -> V1 = 4.0 uL DNA + 16.0 uL water
    row = calculate_single_sample("S1", ["B1"], 50.0, cfg)
    assert row.qc_status == "ok"
    assert row.dna_volume_ul == pytest.approx(4.0)
    assert row.diluent_volume_ul == pytest.approx(16.0)


def test_plate_normalization_and_apply():
    plate = Plate(format_id="96")
    plate.set_well(0, 0, sample="S01", assay="ACTB")
    plate.set_well(0, 1, sample="S02", assay="ACTB")

    concs = parse_concentration_table("S01; 40.0\nS02; 20.0")
    updated = apply_concentrations_to_plate(plate, concs)
    assert updated == 2
    assert plate.get_well(0, 0).concentration == 40.0

    demo = build_demo_plate()
    rows = calculate_normalization(demo, NormalizationConfig())
    statuses = {r.sample: r.qc_status for r in rows}
    assert statuses["Sample_01"] == "ok"
    assert statuses["Sample_03"] == "too_concentrated"
    assert statuses["Sample_06"] == "too_dilute"
