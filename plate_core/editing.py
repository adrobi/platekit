"""Plate editing operations, Smart Fill layout generator, copy/paste and Undo/Redo."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from plate_core.models import Plate, Well


@dataclass
class PlateSnapshot:
    description: str
    format_id: str
    wells_state: dict[tuple[int, int], Well]
    assay_colors: dict[str, str]


class EditHistory:
    """Undo/Redo manager for Plate mutations."""

    def __init__(self, max_depth: int = 100) -> None:
        self.max_depth = max_depth
        self._undo_stack: list[PlateSnapshot] = []
        self._redo_stack: list[PlateSnapshot] = []

    def capture(self, plate: Plate, description: str = "edit") -> PlateSnapshot:
        return PlateSnapshot(
            description=description,
            format_id=plate.format_id,
            wells_state={pos: w.clone() for pos, w in plate.wells.items()},
            assay_colors=dict(plate.assay_colors),
        )

    def push(self, snapshot: PlateSnapshot) -> None:
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self.max_depth:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self, plate: Plate) -> bool:
        if not self._undo_stack:
            return False
        current = self.capture(plate, "redo_state")
        self._redo_stack.append(current)
        snap = self._undo_stack.pop()
        self._restore(plate, snap)
        return True

    def redo(self, plate: Plate) -> bool:
        if not self._redo_stack:
            return False
        current = self.capture(plate, "undo_state")
        self._undo_stack.append(current)
        snap = self._redo_stack.pop()
        self._restore(plate, snap)
        return True

    @staticmethod
    def _restore(plate: Plate, snap: PlateSnapshot) -> None:
        plate.format_id = snap.format_id
        plate.assay_colors = dict(snap.assay_colors)
        plate.wells = {pos: w.clone() for pos, w in snap.wells_state.items()}


_NUM_RE = re.compile(r"^[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?$")


def parse_sample_lines(text: str) -> list[tuple[str, float | None]]:
    """Parse sample lines like 'Sample_01; 42.5', 'Sample_02\t18,0', or 'Sample_03'."""
    results: list[tuple[str, float | None]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # Check common headers
        lower = line.lower()
        if lower.startswith(("sample", "образец", "name", "имя")) and any(
            sep in line for sep in (";", "\t", ",")
        ):
            parts_hdr = re.split(r"[;\t,]+", line)
            if len(parts_hdr) >= 2 and not _NUM_RE.match(parts_hdr[1].strip()):
                continue

        conc: float | None = None
        name = line
        for sep in ("\t", ";", ","):
            if sep in line:
                parts = [p.strip() for p in line.split(sep) if p.strip()]
                if len(parts) >= 2 and _NUM_RE.match(parts[1]):
                    name = parts[0]
                    conc = float(parts[1].replace(",", "."))
                    break
        results.append((name.strip(), conc))
    return results


def parse_assay_lines(text: str) -> list[str]:
    """Parse assay names (one per line or semicolon/comma separated)."""
    assays: list[str] = []
    for raw_line in text.splitlines():
        for chunk in raw_line.replace(";", "\n").splitlines():
            clean = chunk.strip()
            if clean and clean not in assays:
                assays.append(clean)
    return assays


def smart_fill(
    plate: Plate,
    samples: list[tuple[str, float | None]],
    assays: list[str],
    *,
    replicates: int = 1,
    direction: str = "row",
    include_ntc: bool = True,
    include_pos: bool = False,
    start_coord: tuple[int, int] = (0, 0),
    target_coords: list[tuple[int, int]] | None = None,
) -> int:
    """Populate plate with samples × assays × replicates + optional POS/NTC controls.

    Returns the number of wells populated.
    """
    replicates = max(1, int(replicates))
    assay_list = [a.strip() for a in assays if a.strip()] or [""]
    sample_list = [(s.strip(), c) for s, c in samples if s.strip()]

    # Build ordered coordinate list
    if target_coords:
        coords = list(target_coords)
    else:
        all_coords = list(plate.iter_coords(direction=direction))
        try:
            start_idx = all_coords.index(start_coord)
        except ValueError:
            start_idx = 0
        coords = all_coords[start_idx:]

    # Build queue of well descriptors
    queue: list[dict] = []
    for assay in assay_list:
        for sample_name, conc in sample_list:
            rep_grp = f"{sample_name}:{assay}" if assay else sample_name
            for _ in range(replicates):
                queue.append(
                    {
                        "sample": sample_name,
                        "concentration": conc,
                        "assay": assay,
                        "role": "unknown",
                        "replicate_group": rep_grp if replicates > 1 else "",
                    }
                )
        if include_pos:
            rep_grp = f"POS:{assay}" if assay else "POS"
            for _ in range(replicates):
                queue.append(
                    {
                        "sample": "POS",
                        "concentration": None,
                        "assay": assay,
                        "role": "pos",
                        "replicate_group": rep_grp if replicates > 1 else "",
                    }
                )
        if include_ntc:
            rep_grp = f"NTC:{assay}" if assay else "NTC"
            for _ in range(replicates):
                queue.append(
                    {
                        "sample": "NTC",
                        "concentration": None,
                        "assay": assay,
                        "role": "ntc",
                        "replicate_group": rep_grp if replicates > 1 else "",
                    }
                )

    placed = 0
    for (r, c), item in zip(coords, queue):
        plate.set_well(
            r,
            c,
            sample=item["sample"],
            concentration=item["concentration"],
            clear_concentration=(item["concentration"] is None),
            assay=item["assay"],
            role=item["role"],
            replicate_group=item["replicate_group"],
            std_quantity=None,
            note="",
        )
        placed += 1
    return placed


def fill_serial_standards(
    plate: Plate,
    *,
    assay: str,
    start_quantity: float = 1e6,
    dilution_factor: float = 10.0,
    steps: int = 5,
    replicates: int = 2,
    direction: str = "row",
    start_coord: tuple[int, int] = (0, 0),
) -> int:
    """Fill a calibration curve of STD wells with serial dilutions."""
    if dilution_factor <= 0:
        raise ValueError("Dilution factor must be positive")
    steps = max(1, int(steps))
    replicates = max(1, int(replicates))

    all_coords = list(plate.iter_coords(direction=direction))
    try:
        start_idx = all_coords.index(start_coord)
    except ValueError:
        start_idx = 0
    coords = all_coords[start_idx:]

    queue: list[tuple[str, float, str]] = []
    qty = float(start_quantity)
    for i in range(1, steps + 1):
        std_name = f"STD_{i}"
        rep_grp = f"{std_name}:{assay}" if assay else std_name
        for _ in range(replicates):
            queue.append((std_name, qty, rep_grp if replicates > 1 else ""))
        qty = qty / dilution_factor

    placed = 0
    for (r, c), (std_name, std_qty, rep_grp) in zip(coords, queue):
        plate.set_well(
            r,
            c,
            sample=std_name,
            clear_concentration=True,
            assay=assay,
            role="std",
            replicate_group=rep_grp,
            std_quantity=std_qty,
            note=f"{std_qty:g}",
        )
        placed += 1
    return placed


def copy_wells(plate: Plate, coords: Iterable[tuple[int, int]]) -> list[tuple[int, int, Well]]:
    """Copy selected wells as relative offsets (dr, dc, cloned_well) from top-left."""
    pts = sorted(set(coords))
    if not pts:
        return []
    r0 = min(r for r, _ in pts)
    c0 = min(c for _, c in pts)
    copied: list[tuple[int, int, Well]] = []
    for r, c in pts:
        w = plate.get_well(r, c).clone()
        copied.append((r - r0, c - c0, w))
    return copied


def paste_wells(
    plate: Plate,
    copied: list[tuple[int, int, Well]],
    anchor: tuple[int, int],
) -> int:
    """Paste previously copied wells at anchor=(row, col). Returns count pasted."""
    if not copied:
        return 0
    ar, ac = anchor
    count = 0
    for dr, dc, src in copied:
        nr, nc = ar + dr, ac + dc
        if 0 <= nr < plate.rows and 0 <= nc < plate.cols:
            dst = src.clone()
            dst.row = nr
            dst.col = nc
            plate.wells[(nr, nc)] = dst
            if dst.assay:
                plate.ensure_assay_color(dst.assay)
            count += 1
    return count


def build_demo_plate() -> Plate:
    """Create a realistic 96-well demo plate for testing and quick exploration."""
    plate = Plate(name="Demo_Genotyping_Plate", format_id="96", operator="Lab User")
    samples = [
        ("Sample_01", 28.5),
        ("Sample_02", 24.0),
        ("Sample_03", 145.0),  # High concentration -> triggers pre-dilution tip
        ("Sample_04", 31.2),
        ("Sample_05", 12.8),
        ("Sample_06", 3.2),    # Low concentration -> triggers dilute QC warning
        ("Sample_07", 55.0),
        ("Sample_08", 29.4),
    ]
    assays = ["ACTB_ref", "BRCA1_ex11"]
    smart_fill(
        plate,
        samples=samples,
        assays=assays,
        replicates=2,
        direction="row",
        include_pos=True,
        include_ntc=True,
        start_coord=(0, 0),
    )
    # Add a 4-point standard curve on row D (row=3, col=4)
    fill_serial_standards(
        plate,
        assay="ACTB_ref",
        start_quantity=1e5,
        dilution_factor=10.0,
        steps=4,
        replicates=2,
        direction="row",
        start_coord=(3, 4),
    )
    return plate
