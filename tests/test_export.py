"""Unit tests for plate_core.export (Excel .xlsx and printable HTML Bench Sheet)."""

from __future__ import annotations

import openpyxl

from plate_core.editing import build_demo_plate
from plate_core.export import export_bench_sheet_html, export_excel_workbook
from plate_core.normalization import NormalizationConfig
from plate_core.presets import builtin_recipes


def test_export_excel_workbook(tmp_path):
    plate = build_demo_plate()
    recipe = builtin_recipes()["pcr_standard"]
    norm_cfg = NormalizationConfig()

    xlsx_path = tmp_path / "out.xlsx"
    export_excel_workbook(plate, recipe, norm_cfg, xlsx_path)
    assert xlsx_path.exists()

    wb = openpyxl.load_workbook(xlsx_path)
    assertwb_sheets = set(wb.sheetnames)
    assert {"Plate Map", "Master Mix", "DNA Normalization", "Well List"} <= assertwb_sheets
    ws_map = wb["Plate Map"]
    assert "Sample_01" in str(ws_map["B5"].value)


def test_export_bench_sheet_html(tmp_path):
    plate = build_demo_plate()
    recipe = builtin_recipes()["pcr_standard"]
    norm_cfg = NormalizationConfig()

    html_path = tmp_path / "bench.html"
    export_bench_sheet_html(plate, recipe, norm_cfg, html_path)
    text = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "ACTB_ref" in text
    assert "BRCA1_ex11" in text
    assert "Sample_01" in text
