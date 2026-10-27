"""CLI and GUI entry point for platekit."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from plate_core.editing import build_demo_plate
from plate_core.export import export_bench_sheet_html, export_excel_workbook
from plate_core.instruments import (
    export_abi_sequencer_tsv,
    export_biorad_cfx_csv,
    export_quantstudio_csv,
    export_rotorgene_csv,
)
from plate_core.sessions import PlateProject, load_project, save_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="platekit",
        description="PCR & Sequencing Plate Planner, Master Mix & DNA Normalization Calculator",
    )
    parser.add_argument(
        "project",
        nargs="?",
        help="Optional path to a .platekit.json project file to open or process",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use the built-in 96-well demo plate for headless CLI export",
    )
    parser.add_argument(
        "--save-project",
        metavar="PATH",
        help="Save the loaded/demo project to a .platekit.json file",
    )
    parser.add_argument(
        "--export-xlsx",
        metavar="PATH",
        help="Export multi-sheet Excel workbook (.xlsx)",
    )
    parser.add_argument(
        "--export-bench",
        metavar="PATH",
        help="Export printable HTML Bench Sheet (.html)",
    )
    parser.add_argument(
        "--export-cfx",
        metavar="PATH",
        help="Export Bio-Rad CFX Maestro Plate Setup (.csv)",
    )
    parser.add_argument(
        "--export-quantstudio",
        metavar="PATH",
        help="Export ABI QuantStudio / StepOne Sample Setup (.csv)",
    )
    parser.add_argument(
        "--export-rotorgene",
        metavar="PATH",
        help="Export Qiagen Rotor-Gene Q layout (.csv)",
    )
    parser.add_argument(
        "--export-abi",
        metavar="PATH",
        help="Export ABI 3130/3500 Sequencer Sample Sheet (.tsv)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    has_cli_action = any(
        [
            args.save_project,
            args.export_xlsx,
            args.export_bench,
            args.export_cfx,
            args.export_quantstudio,
            args.export_rotorgene,
            args.export_abi,
        ]
    )

    if has_cli_action:
        if args.project:
            proj = load_project(args.project)
        elif args.demo:
            proj = PlateProject(plate=build_demo_plate())
        else:
            parser.error("Provide a project file or --demo when running CLI export flags.")
            return 2

        if args.save_project:
            save_project(proj, args.save_project)
        if args.export_xlsx:
            export_excel_workbook(proj.plate, proj.recipe, proj.norm_config, args.export_xlsx)
        if args.export_bench:
            export_bench_sheet_html(proj.plate, proj.recipe, proj.norm_config, args.export_bench)
        if args.export_cfx:
            export_biorad_cfx_csv(proj.plate, args.export_cfx)
        if args.export_quantstudio:
            export_quantstudio_csv(proj.plate, args.export_quantstudio)
        if args.export_rotorgene:
            export_rotorgene_csv(proj.plate, args.export_rotorgene)
        if args.export_abi:
            export_abi_sequencer_tsv(proj.plate, args.export_abi)
        return 0

    from ui.main_window import run

    return run(Path(args.project) if args.project else None)


if __name__ == "__main__":
    sys.exit(main())
