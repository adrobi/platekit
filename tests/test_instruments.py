"""Unit tests for plate_core.instruments (CFX, QuantStudio, Rotor-Gene, ABI 3500)."""

from __future__ import annotations

from plate_core.editing import build_demo_plate
from plate_core.instruments import (
    export_abi_sequencer_str,
    export_biorad_cfx_str,
    export_quantstudio_str,
    export_rotorgene_str,
    import_instrument_layout_text,
)
from plate_core.models import Plate


def test_export_and_reimport_biorad_cfx():
    demo = build_demo_plate()
    csv_text = export_biorad_cfx_str(demo)
    assert "Well,Fluor,Target,Content,Sample" in csv_text
    assert "A01,SYBR,ACTB_ref,Unkn,Sample_01" in csv_text

    reimported = Plate(format_id="96")
    count = import_instrument_layout_text(reimported, csv_text)
    assert count == len(demo.occupied_wells())
    assert reimported.by_coord("A1").sample == "Sample_01"
    assert reimported.by_coord("A1").assay == "ACTB_ref"


def test_export_and_reimport_quantstudio():
    demo = build_demo_plate()
    qs_text = export_quantstudio_str(demo)
    assert "[Sample Setup]" in qs_text
    assert "Sample_01,ACTB_ref,UNKNOWN" in qs_text

    reimported = Plate(format_id="96")
    count = import_instrument_layout_text(reimported, qs_text)
    assert count == len(demo.occupied_wells())
    assert reimported.by_coord("A1").sample == "Sample_01"


def test_export_rotorgene_and_abi_sequencer():
    demo = build_demo_plate()
    rg_text = export_rotorgene_str(demo)
    assert "Position,Coordinate,Type,Name,Target,Given Conc" in rg_text

    abi_text = export_abi_sequencer_str(demo)
    assert "[Data]" in abi_text
    assert "A01_Sample_01_ACTB_ref.ab1" in abi_text
