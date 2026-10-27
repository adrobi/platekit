"""GUI smoke tests: run Qt offscreen, no display required."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def no_config_writes(monkeypatch):
    monkeypatch.setattr("ui.main_window.save_config", lambda *a, **k: None)


def test_entry_point_importable():
    from plate_cli import main
    from ui.main_window import MainWindow, run

    assert callable(main)
    assert callable(run)
    assert MainWindow is not None


def test_main_window_renders_and_switches_tabs(qapp):
    from plate_core.sessions import AppConfig
    from ui.main_window import MainWindow

    win = MainWindow(AppConfig(language="ru", theme="dark"))
    win.show()
    assert len(win.plate.occupied_wells()) == 48

    # Switch across all tabs and ensure offscreen rendering works
    for tab_idx in range(win.tabs.count()):
        win.tabs.setCurrentIndex(tab_idx)
        assert not win.grab().isNull()

    # Switch language and theme
    win.switch_language("en")
    win.apply_theme(False)
    assert not win.grab().isNull()

    # Smart Fill via MainWindow handler
    win._on_smart_fill(
        {
            "samples_text": "S1; 35.0\nS2; 12.0",
            "assays_text": "Gene1",
            "replicates": 2,
            "direction": "row",
            "include_ntc": True,
            "include_pos": False,
            "start_selected": False,
        }
    )
    assert len(win.plate.occupied_wells()) == 6
    win.undo_edit()
    assert len(win.plate.occupied_wells()) == 48
    win.close()


def test_pipetting_dialog_stepping(qapp):
    from plate_core.editing import build_demo_plate
    from plate_core.normalization import NormalizationConfig
    from plate_core.presets import builtin_recipes
    from ui.pipetting_dialog import PipettingDialog

    plate = build_demo_plate()
    recipe = builtin_recipes()["pcr_standard"]
    dlg = PipettingDialog(plate, recipe, NormalizationConfig())
    dlg.show()
    assert len(dlg.steps) == 48
    dlg.next_step()
    assert dlg.current_idx == 1
    dlg.prev_step()
    assert dlg.current_idx == 0

    # Switch to column-wise multichannel mode
    dlg.mode_combo.setCurrentIndex(1)
    assert len(dlg.steps) == 12
    assert not dlg.grab().isNull()
    dlg.close()
