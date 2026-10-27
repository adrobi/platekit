"""Unit tests for plate_core.sessions and CLI headless mode."""

from __future__ import annotations

from plate_cli import main as cli_main
from plate_core.editing import build_demo_plate
from plate_core.sessions import (
    AppConfig,
    PlateProject,
    load_config,
    load_project,
    save_config,
    save_project,
)


def test_project_save_and_load(tmp_path):
    proj = PlateProject(plate=build_demo_plate())
    proj.recipe.overfill_value = 15.0
    proj.norm_config.target_mass_ng = 30.0

    pfile = tmp_path / "demo.platekit.json"
    save_project(proj, pfile)
    assert pfile.exists()

    loaded = load_project(pfile)
    assert loaded.plate.name == proj.plate.name
    assert len(loaded.plate.occupied_wells()) == len(proj.plate.occupied_wells())
    assert loaded.recipe.overfill_value == 15.0
    assert loaded.norm_config.target_mass_ng == 30.0


def test_app_config_persistence(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg = AppConfig(language="en", theme="light", color_mode="role")
    cfg.add_recent(tmp_path / "a.platekit.json")
    save_config(cfg, cfg_path)

    loaded = load_config(cfg_path)
    assert loaded.language == "en"
    assert loaded.theme == "light"
    assert loaded.color_mode == "role"
    assert len(loaded.recent_files) == 1


def test_cli_export_workflow(tmp_path):
    proj_path = tmp_path / "cli.platekit.json"
    xlsx_path = tmp_path / "cli.xlsx"
    bench_path = tmp_path / "cli.html"
    cfx_path = tmp_path / "cfx.csv"

    rc = cli_main(
        [
            "--demo",
            "--save-project",
            str(proj_path),
            "--export-xlsx",
            str(xlsx_path),
            "--export-bench",
            str(bench_path),
            "--export-cfx",
            str(cfx_path),
        ]
    )
    assert rc == 0
    assert proj_path.exists()
    assert xlsx_path.exists()
    assert bench_path.exists()
    assert cfx_path.exists()
