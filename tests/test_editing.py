"""Unit tests for plate_core.editing (Smart Fill, serial standards, copy/paste, Undo/Redo)."""

from __future__ import annotations

from plate_core.editing import (
    EditHistory,
    build_demo_plate,
    copy_wells,
    fill_serial_standards,
    parse_assay_lines,
    parse_sample_lines,
    paste_wells,
    smart_fill,
)
from plate_core.models import Plate


def test_parse_sample_and_assay_lines():
    text = (
        "Sample;Concentration\n"
        "S01; 42.5\n"
        "S02\t19,8\n"
        "S03\n"
    )
    samples = parse_sample_lines(text)
    assert samples == [("S01", 42.5), ("S02", 19.8), ("S03", None)]

    assays = parse_assay_lines("ACTB; GAPDH\nBRCA1\nACTB")
    assert assays == ["ACTB", "GAPDH", "BRCA1"]


def test_smart_fill_replicates_and_controls():
    plate = Plate(format_id="96")
    samples = [("S1", 30.0), ("S2", 40.0)]
    assays = ["TargetA", "TargetB"]

    # 2 assays * (2 samples * 2 reps + 2 pos + 2 ntc) = 2 * 8 = 16 wells
    placed = smart_fill(
        plate,
        samples=samples,
        assays=assays,
        replicates=2,
        direction="row",
        include_pos=True,
        include_ntc=True,
    )
    assert placed == 16
    assert plate.counts_by_assay() == {"TargetA": 8, "TargetB": 8}
    assert plate.by_coord("A1").sample == "S1"
    assert plate.by_coord("A2").sample == "S1"
    assert plate.by_coord("A5").role == "pos"
    assert plate.by_coord("A7").role == "ntc"


def test_serial_standards():
    plate = Plate(format_id="96")
    placed = fill_serial_standards(
        plate,
        assay="ACTB",
        start_quantity=10000.0,
        dilution_factor=10.0,
        steps=4,
        replicates=2,
    )
    assert placed == 8
    assert plate.by_coord("A1").role == "std"
    assert plate.by_coord("A1").std_quantity == 10000.0
    assert plate.by_coord("A3").std_quantity == 1000.0
    assert plate.by_coord("A7").std_quantity == 10.0


def test_copy_paste_and_undo_redo():
    plate = Plate(format_id="96")
    history = EditHistory()

    history.push(history.capture(plate, "initial"))
    plate.set_well(0, 0, sample="Orig1", assay="A1")
    plate.set_well(0, 1, sample="Orig2", assay="A1")

    copied = copy_wells(plate, [(0, 0), (0, 1)])
    history.push(history.capture(plate, "before_paste"))
    pasted = paste_wells(plate, copied, anchor=(2, 0))
    assert pasted == 2
    assert plate.get_well(2, 0).sample == "Orig1"
    assert plate.get_well(2, 1).sample == "Orig2"

    assert history.undo(plate)
    assert not plate.get_well(2, 0).is_occupied
    assert history.redo(plate)
    assert plate.get_well(2, 0).sample == "Orig1"


def test_build_demo_plate():
    demo = build_demo_plate()
    assert len(demo.occupied_wells()) == 48
    assert set(demo.assays()) == {"ACTB_ref", "BRCA1_ex11"}
