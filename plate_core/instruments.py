"""Export and import plate layouts for real qPCR cyclers and Sanger sequencers."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from plate_core.models import Plate, parse_coord

CFX_ROLE_TO_CONTENT = {
    "unknown": "Unkn",
    "ntc": "NTC",
    "pos": "Pos Ctrl",
    "std": "Std",
    "ipc": "IPC",
    "empty": "",
}

CFX_CONTENT_TO_ROLE = {
    "unkn": "unknown",
    "unknown": "unknown",
    "ntc": "ntc",
    "pos ctrl": "pos",
    "pos": "pos",
    "std": "std",
    "standard": "std",
    "ipc": "ipc",
}

QS_ROLE_TO_TASK = {
    "unknown": "UNKNOWN",
    "ntc": "NTC",
    "pos": "POSITIVE_CONTROL",
    "std": "STANDARD",
    "ipc": "IPC",
    "empty": "",
}

QS_TASK_TO_ROLE = {
    "unknown": "unknown",
    "ntc": "ntc",
    "positive_control": "pos",
    "pos": "pos",
    "standard": "std",
    "std": "std",
    "ipc": "ipc",
}


def export_biorad_cfx_str(plate: Plate, default_fluor: str = "SYBR") -> str:
    """Serialize plate to Bio-Rad CFX Maestro Plate Setup CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "Well",
            "Fluor",
            "Target",
            "Content",
            "Sample",
            "Biological Set Name",
            "Starting Quantity",
        ]
    )
    for w in plate.iter_wells(direction="row"):
        if not w.is_occupied:
            continue
        sq = f"{w.std_quantity:g}" if w.std_quantity is not None else ""
        writer.writerow(
            [
                w.coord_padded,
                default_fluor,
                w.assay,
                CFX_ROLE_TO_CONTENT.get(w.role, "Unkn"),
                w.sample,
                w.replicate_group,
                sq,
            ]
        )
    return buf.getvalue()


def export_biorad_cfx_csv(plate: Plate, path: str | Path, default_fluor: str = "SYBR") -> None:
    Path(path).write_text(export_biorad_cfx_str(plate, default_fluor=default_fluor), encoding="utf-8")


def export_quantstudio_str(
    plate: Plate,
    reporter: str = "SYBR",
    quencher: str = "None",
) -> str:
    """Serialize plate to Applied Biosystems QuantStudio / StepOne Sample Setup CSV."""
    buf = io.StringIO()
    buf.write(f"* Block Type = {plate.format.title}\n")
    buf.write(f"* Experiment Name = {plate.name}\n")
    buf.write("[Sample Setup]\n")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "Well",
            "Well Position",
            "Sample Name",
            "Target Name",
            "Task",
            "Reporter",
            "Quencher",
            "Quantity",
        ]
    )
    for idx, w in enumerate(plate.iter_wells(direction="row"), start=1):
        if not w.is_occupied:
            continue
        qty = f"{w.std_quantity:g}" if w.std_quantity is not None else ""
        writer.writerow(
            [
                idx,
                w.coord,
                w.sample,
                w.assay,
                QS_ROLE_TO_TASK.get(w.role, "UNKNOWN"),
                reporter,
                quencher,
                qty,
            ]
        )
    return buf.getvalue()


def export_quantstudio_csv(
    plate: Plate,
    path: str | Path,
    reporter: str = "SYBR",
    quencher: str = "None",
) -> None:
    Path(path).write_text(
        export_quantstudio_str(plate, reporter=reporter, quencher=quencher),
        encoding="utf-8",
    )


def export_rotorgene_str(plate: Plate) -> str:
    """Serialize plate/rotor to Qiagen Rotor-Gene Q CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["Position", "Coordinate", "Type", "Name", "Target", "Given Conc"])
    for w in plate.iter_wells(direction="row"):
        if not w.is_occupied:
            continue
        pos = w.rotor_position(plate.cols)
        rg_type = {
            "unknown": "Unknown",
            "ntc": "NTC",
            "pos": "Positive Control",
            "std": "Standard",
            "ipc": "IPC",
        }.get(w.role, "Unknown")
        conc = f"{w.std_quantity:g}" if w.std_quantity is not None else ""
        writer.writerow([pos, w.coord, rg_type, w.sample, w.assay, conc])
    return buf.getvalue()


def export_rotorgene_csv(plate: Plate, path: str | Path) -> None:
    Path(path).write_text(export_rotorgene_str(plate), encoding="utf-8")


def export_abi_sequencer_str(plate: Plate) -> str:
    """Serialize plate to ABI 3130/3500 Capillary Sequencer Sample Sheet TSV (ab1kit-compatible)."""
    buf = io.StringIO()
    buf.write("Container Name\tPlate ID\tDescription\tContainerType\tAppType\tOwner\n")
    buf.write(f"{plate.name}\t{plate.name}\tplatekit export\t{plate.format_id}-Well\tRegular\t{plate.operator or 'Lab'}\n")
    buf.write("[Data]\n")
    writer = csv.writer(buf, delimiter="\t", lineterminator="\n")
    writer.writerow(
        [
            "Well",
            "Sample_Name",
            "Primer_Assay",
            "Role",
            "File_Name_Preview",
        ]
    )
    for w in plate.iter_wells(direction="col"):
        if not w.is_occupied:
            continue
        safe_s = (w.sample or w.role).replace(" ", "_")
        safe_a = (w.assay or "seq").replace(" ", "_")
        preview = f"{w.coord_padded}_{safe_s}_{safe_a}.ab1"
        writer.writerow([w.coord_padded, w.sample or w.role.upper(), w.assay, w.role, preview])
    return buf.getvalue()


def export_abi_sequencer_tsv(plate: Plate, path: str | Path) -> None:
    Path(path).write_text(export_abi_sequencer_str(plate), encoding="utf-8")


def import_instrument_layout_text(plate: Plate, text: str) -> int:
    """Auto-detect and import Bio-Rad CFX, QuantStudio, Rotor-Gene or ABI Sequencer layout into plate."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("*")]
    # Skip metadata blocks like [Sample Setup] or [Data]
    header_idx = 0
    for idx, ln in enumerate(lines):
        low = ln.lower()
        if any(k in low for k in ("well", "position", "coordinate")) and ("," in ln or "\t" in ln):
            header_idx = idx
            break

    data_text = "\n".join(lines[header_idx:])
    delim = "\t" if "\t" in lines[header_idx] else ","
    reader = csv.DictReader(io.StringIO(data_text), delimiter=delim)

    imported = 0
    for row in reader:
        norm = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
        coord_str = (
            norm.get("well position")
            or norm.get("coordinate")
            or norm.get("well")
            or norm.get("position")
            or ""
        )
        if not coord_str:
            continue
        try:
            r, c = parse_coord(coord_str, cols=plate.cols)
        except ValueError:
            continue
        if not (0 <= r < plate.rows and 0 <= c < plate.cols):
            continue

        sample = norm.get("sample name") or norm.get("sample_name") or norm.get("sample") or norm.get("name") or ""
        assay = norm.get("target name") or norm.get("target") or norm.get("primer_assay") or ""
        raw_role = (norm.get("content") or norm.get("task") or norm.get("type") or norm.get("role") or "unknown").lower()
        role = (
            CFX_CONTENT_TO_ROLE.get(raw_role)
            or QS_TASK_TO_ROLE.get(raw_role)
            or ("pos" if "pos" in raw_role else "ntc" if "ntc" in raw_role else "std" if "st" in raw_role else "unknown")
        )
        rep_group = norm.get("biological set name") or ""
        qty_str = norm.get("starting quantity") or norm.get("quantity") or norm.get("given conc") or ""
        std_qty: float | None = None
        if qty_str:
            try:
                std_qty = float(qty_str.replace(",", "."))
            except ValueError:
                std_qty = None

        plate.set_well(
            r,
            c,
            sample=sample,
            assay=assay,
            role=role,
            replicate_group=rep_group,
            std_quantity=std_qty,
        )
        imported += 1
    return imported


def import_instrument_layout_file(plate: Plate, path: str | Path) -> int:
    text = Path(path).read_text(encoding="utf-8-sig")
    return import_instrument_layout_text(plate, text)
