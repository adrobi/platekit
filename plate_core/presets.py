"""Built-in protocol presets for PCR, qPCR, PCR-RFLP and Sanger sequencing."""

from __future__ import annotations

from plate_core.mastermix import MixComponent, MixRecipe


def builtin_recipes() -> dict[str, MixRecipe]:
    return {
        "pcr_standard": MixRecipe(
            recipe_id="pcr_standard",
            name="Standard Taq PCR (25 µL)",
            reaction_volume_ul=25.0,
            template_volume_ul=2.0,
            overfill_mode="percent",
            overfill_value=10.0,
            components=[
                MixComponent("10× Taq Reaction Buffer", "10×", "1×", 2.5),
                MixComponent("MgCl₂", "25 mM", "2.0 mM", 2.0),
                MixComponent("dNTP Mix", "2.5 mM", "0.2 mM", 2.0),
                MixComponent("Forward Primer", "10 µM", "0.4 µM", 1.0),
                MixComponent("Reverse Primer", "10 µM", "0.4 µM", 1.0),
                MixComponent("Taq DNA Polymerase", "5 U/µL", "1.25 U", 0.25),
            ],
        ),
        "qpcr_sybr": MixRecipe(
            recipe_id="qpcr_sybr",
            name="qPCR SYBR Green 2× Mix (20 µL)",
            reaction_volume_ul=20.0,
            template_volume_ul=2.0,
            overfill_mode="percent",
            overfill_value=10.0,
            components=[
                MixComponent("2× SYBR Green qPCR MasterMix", "2×", "1×", 10.0),
                MixComponent("Forward Primer", "10 µM", "0.4 µM", 0.8),
                MixComponent("Reverse Primer", "10 µM", "0.4 µM", 0.8),
            ],
        ),
        "qpcr_taqman": MixRecipe(
            recipe_id="qpcr_taqman",
            name="qPCR TaqMan Probe 2× Mix (20 µL)",
            reaction_volume_ul=20.0,
            template_volume_ul=2.0,
            overfill_mode="percent",
            overfill_value=10.0,
            components=[
                MixComponent("2× Probe qPCR MasterMix", "2×", "1×", 10.0),
                MixComponent("Forward Primer", "10 µM", "0.4 µM", 0.8),
                MixComponent("Reverse Primer", "10 µM", "0.4 µM", 0.8),
                MixComponent("TaqMan Probe (FAM/BHQ1)", "10 µM", "0.2 µM", 0.4),
            ],
        ),
        "rflp_digest": MixRecipe(
            recipe_id="rflp_digest",
            name="PCR-RFLP Restriction Digest (15 µL)",
            reaction_volume_ul=15.0,
            template_volume_ul=5.0,
            overfill_mode="percent",
            overfill_value=10.0,
            components=[
                MixComponent("10× Restriction Buffer", "10×", "1×", 1.5),
                MixComponent("Restriction Endonuclease", "10 U/µL", "5 U", 0.5),
                MixComponent("100× BSA (optional)", "100×", "1×", 0.15),
            ],
        ),
        "sanger_bigdye": MixRecipe(
            recipe_id="sanger_bigdye",
            name="Sanger Sequencing BigDye v3.1 (10 µL)",
            reaction_volume_ul=10.0,
            template_volume_ul=2.0,
            overfill_mode="percent",
            overfill_value=10.0,
            components=[
                MixComponent("5× Sequencing Buffer", "5×", "0.75×", 1.5),
                MixComponent("BigDye Terminator v3.1 Mix", "2.5×", "0.25×", 1.0),
                MixComponent("Sequencing Primer", "3.2 µM", "0.32 µM", 1.0),
            ],
        ),
    }
