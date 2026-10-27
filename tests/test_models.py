"""Unit tests for plate_core.models."""

from __future__ import annotations

import pytest

from plate_core.models import (
    PLATE_FORMATS,
    Plate,
    Well,
    format_coord,
    parse_coord,
    parse_row_label,
    row_label,
)


def test_row_label_roundtrip():
    for r in range(24):
        lbl = row_label(r)
        assert parse_row_label(lbl) == r


def test_format_and_parse_coord():
    assert format_coord(0, 0) == "A1"
    assert format_coord(0, 0, zero_pad=True) == "A01"
    assert format_coord(7, 11, zero_pad=True) == "H12"
    assert parse_coord("A1") == (0, 0)
    assert parse_coord("A01") == (0, 0)
    assert parse_coord("h12") == (7, 11)
    # Numeric rotor position
    assert parse_coord("1", cols=12) == (0, 0)
    assert parse_coord("13", cols=12) == (1, 0)


def test_plate_formats_and_resize():
    p = Plate(name="Test", format_id="96")
    assert p.rows == 8
    assert p.cols == 12
    assert p.total_wells == 96

    p.set_well(0, 0, sample="S1", concentration=25.0, assay="ACTB")
    p.set_well(7, 11, sample="S2", assay="GAPDH")
    assert len(p.occupied_wells()) == 2
    assert p.assays() == ["ACTB", "GAPDH"]
    assert p.counts_by_assay() == {"ACTB": 1, "GAPDH": 1}

    # Resize to 8-strip (8x1): (0,0) survives, (7,11) is out of bounds
    p.resize_format("strip8")
    assert p.total_wells == 8
    assert len(p.occupied_wells()) == 1
    assert p.get_well(0, 0).sample == "S1"


def test_plate_serialization_roundtrip():
    p = Plate(name="Roundtrip", format_id="384", operator="Alice")
    p.set_well(15, 23, sample="Ctrl", role="pos", assay="TargetX", note="corner")
    data = p.to_dict()
    restored = Plate.from_dict(data)
    assert restored.name == "Roundtrip"
    assert restored.format_id == "384"
    assert restored.operator == "Alice"
    w = restored.get_well(15, 23)
    assert w.sample == "Ctrl"
    assert w.role == "pos"
    assert w.assay == "TargetX"
    assert w.note == "corner"


def test_well_clear_and_clone():
    w = Well(row=1, col=2, sample="DNA1", concentration=50.0, assay="A1")
    assert w.is_occupied
    cloned = w.clone()
    w.clear()
    assert not w.is_occupied
    assert w.role == "empty"
    assert cloned.is_occupied
    assert cloned.sample == "DNA1"


def test_invalid_plate_format_raises():
    with pytest.raises(ValueError):
        Plate(format_id="invalid_fmt")
    assert set(PLATE_FORMATS) >= {"96", "384", "strip8", "strip12", "rotor36", "rotor72", "rotor100"}
