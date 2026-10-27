"""Unit tests for plate_core.mastermix and plate_core.presets."""

from __future__ import annotations

import pytest

from plate_core.editing import build_demo_plate
from plate_core.mastermix import MixComponent, MixRecipe, calculate_plate_mixes
from plate_core.presets import builtin_recipes


def test_builtin_recipes_valid():
    presets = builtin_recipes()
    assert set(presets) >= {
        "pcr_standard",
        "qpcr_sybr",
        "qpcr_taqman",
        "rflp_digest",
        "sanger_bigdye",
    }
    for r in presets.values():
        assert not r.exceeds_reaction_volume
        assert r.water_per_rxn_ul >= 0.0
        assert r.dispense_per_well_ul == pytest.approx(
            r.reaction_volume_ul - r.template_volume_ul
        )


def test_overfill_modes():
    recipe = builtin_recipes()["pcr_standard"].clone()
    recipe.overfill_mode = "percent"
    recipe.overfill_value = 10.0
    assert recipe.effective_reactions(20) == pytest.approx(22.0)

    recipe.overfill_mode = "extra_rxn"
    recipe.overfill_value = 2.0
    assert recipe.effective_reactions(20) == pytest.approx(22.0)

    recipe.overfill_mode = "multichannel"
    recipe.overfill_value = 5.0
    # 10 wells * 1.05 = 10.5, but multichannel enforces at least +2 reactions -> 12.0
    assert recipe.effective_reactions(10) == pytest.approx(12.0)


def test_calculate_plate_mixes_and_volume_warning():
    plate = build_demo_plate()
    recipe = builtin_recipes()["qpcr_sybr"].clone()
    calcs = calculate_plate_mixes(plate, recipe)
    assert len(calcs) == 2
    by_assay = {c.assay: c for c in calcs}
    assert by_assay["ACTB_ref"].well_count == 28
    assert by_assay["BRCA1_ex11"].well_count == 20

    # Trigger volume exceeded warning
    bad = MixRecipe(
        reaction_volume_ul=10.0,
        template_volume_ul=5.0,
        components=[MixComponent("2x Mix", "2x", "1x", 8.0)],
    )
    assert bad.exceeds_reaction_volume
