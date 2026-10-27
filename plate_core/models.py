"""Core data structures for PCR & sequencing plates, wells, samples and assays."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterator

WELL_ROLES = ("unknown", "ntc", "pos", "std", "ipc", "empty")

ASSAY_PALETTE = (
    "#3B82F6",  # Blue
    "#10B981",  # Emerald
    "#F59E0B",  # Amber
    "#8B5CF6",  # Violet
    "#EC4899",  # Pink
    "#06B6D4",  # Cyan
    "#EF4444",  # Red
    "#84CC16",  # Lime
    "#F97316",  # Orange
    "#6366F1",  # Indigo
    "#14B8A6",  # Teal
    "#D946EF",  # Fuchsia
)

ROLE_COLORS = {
    "unknown": "#3B82F6",
    "ntc": "#EF4444",
    "pos": "#10B981",
    "std": "#F59E0B",
    "ipc": "#8B5CF6",
    "empty": "#6B7280",
}


@dataclass(frozen=True)
class PlateFormat:
    format_id: str
    title: str
    rows: int
    cols: int
    is_rotor: bool = False

    @property
    def total_wells(self) -> int:
        return self.rows * self.cols


PLATE_FORMATS: dict[str, PlateFormat] = {
    "96": PlateFormat("96", "96-well (8×12)", 8, 12),
    "384": PlateFormat("384", "384-well (16×24)", 16, 24),
    "strip8": PlateFormat("strip8", "8-strip (8×1)", 8, 1),
    "strip12": PlateFormat("strip12", "12-strip (1×12)", 1, 12),
    "rotor36": PlateFormat("rotor36", "Rotor-36 (6×6)", 6, 6, is_rotor=True),
    "rotor72": PlateFormat("rotor72", "Rotor-72 (6×12)", 6, 12, is_rotor=True),
    "rotor100": PlateFormat("rotor100", "Rotor-100 (10×10)", 10, 10, is_rotor=True),
}


def row_label(row: int) -> str:
    """Convert 0-based row index to alphabetic label (0 -> 'A', 15 -> 'P')."""
    if row < 0:
        raise ValueError(f"Row index must be non-negative, got {row}")
    if row < 26:
        return chr(ord("A") + row)
    return chr(ord("A") + (row // 26) - 1) + chr(ord("A") + (row % 26))


def parse_row_label(label: str) -> int:
    """Convert alphabetic row label ('A'..'Z') to 0-based row index."""
    clean = label.strip().upper()
    if not clean or not clean.isalpha():
        raise ValueError(f"Invalid row label: {label!r}")
    idx = 0
    for ch in clean:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def format_coord(row: int, col: int, zero_pad: bool = False) -> str:
    """Format 0-based (row, col) as 'A1' or 'A01'."""
    r = row_label(row)
    return f"{r}{col + 1:02d}" if zero_pad else f"{r}{col + 1}"


_COORD_RE = re.compile(r"^([A-Za-z]+)\s*0*([1-9]\d*)$")


def parse_coord(coord: str, cols: int = 12) -> tuple[int, int]:
    """Parse well coordinate ('A1', 'A01', 'H12') or 1-based rotor number ('1'..'100')."""
    s = coord.strip()
    m = _COORD_RE.match(s)
    if m:
        row = parse_row_label(m.group(1))
        col = int(m.group(2)) - 1
        return row, col
    if s.isdigit():
        num = int(s) - 1
        if num < 0:
            raise ValueError(f"Invalid numeric well position: {coord!r}")
        return num // cols, num % cols
    raise ValueError(f"Unrecognized well coordinate: {coord!r}")


@dataclass
class Well:
    row: int
    col: int
    sample: str = ""
    concentration: float | None = None
    assay: str = ""
    role: str = "empty"
    replicate_group: str = ""
    std_quantity: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.role not in WELL_ROLES:
            self.role = "unknown"
        if (self.sample or self.assay) and self.role == "empty":
            self.role = "unknown"

    @property
    def coord(self) -> str:
        return format_coord(self.row, self.col, zero_pad=False)

    @property
    def coord_padded(self) -> str:
        return format_coord(self.row, self.col, zero_pad=True)

    def rotor_position(self, cols: int) -> int:
        return self.row * cols + self.col + 1

    @property
    def is_occupied(self) -> bool:
        return self.role != "empty" or bool(self.sample.strip()) or bool(self.assay.strip())

    def clear(self) -> None:
        self.sample = ""
        self.concentration = None
        self.assay = ""
        self.role = "empty"
        self.replicate_group = ""
        self.std_quantity = None
        self.note = ""

    def clone(self) -> Well:
        return Well(
            row=self.row,
            col=self.col,
            sample=self.sample,
            concentration=self.concentration,
            assay=self.assay,
            role=self.role,
            replicate_group=self.replicate_group,
            std_quantity=self.std_quantity,
            note=self.note,
        )

    def to_dict(self) -> dict:
        return {
            "row": self.row,
            "col": self.col,
            "coord": self.coord,
            "sample": self.sample,
            "concentration": self.concentration,
            "assay": self.assay,
            "role": self.role,
            "replicate_group": self.replicate_group,
            "std_quantity": self.std_quantity,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Well:
        return cls(
            row=int(data["row"]),
            col=int(data["col"]),
            sample=str(data.get("sample", "")),
            concentration=(
                float(data["concentration"])
                if data.get("concentration") is not None
                else None
            ),
            assay=str(data.get("assay", "")),
            role=str(data.get("role", "empty")),
            replicate_group=str(data.get("replicate_group", "")),
            std_quantity=(
                float(data["std_quantity"])
                if data.get("std_quantity") is not None
                else None
            ),
            note=str(data.get("note", "")),
        )


@dataclass
class Plate:
    name: str = "Plate_01"
    format_id: str = "96"
    operator: str = ""
    wells: dict[tuple[int, int], Well] = field(default_factory=dict)
    assay_colors: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.format_id not in PLATE_FORMATS:
            raise ValueError(f"Unsupported plate format: {self.format_id!r}")
        self._init_grid()

    def _init_grid(self) -> None:
        fmt = self.format
        for r in range(fmt.rows):
            for c in range(fmt.cols):
                if (r, c) not in self.wells:
                    self.wells[(r, c)] = Well(row=r, col=c)

    @property
    def format(self) -> PlateFormat:
        return PLATE_FORMATS[self.format_id]

    @property
    def rows(self) -> int:
        return self.format.rows

    @property
    def cols(self) -> int:
        return self.format.cols

    @property
    def total_wells(self) -> int:
        return self.format.total_wells

    def get_well(self, row: int, col: int) -> Well:
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise IndexError(f"Well ({row}, {col}) out of bounds for {self.format_id}")
        return self.wells[(row, col)]

    def by_coord(self, coord: str) -> Well:
        row, col = parse_coord(coord, cols=self.cols)
        return self.get_well(row, col)

    def set_well(
        self,
        row: int,
        col: int,
        *,
        sample: str | None = None,
        concentration: float | None = None,
        clear_concentration: bool = False,
        assay: str | None = None,
        role: str | None = None,
        replicate_group: str | None = None,
        std_quantity: float | None = None,
        note: str | None = None,
    ) -> Well:
        w = self.get_well(row, col)
        if sample is not None:
            w.sample = sample.strip()
        if clear_concentration:
            w.concentration = None
        elif concentration is not None:
            w.concentration = concentration
        if assay is not None:
            w.assay = assay.strip()
            if w.assay:
                self.ensure_assay_color(w.assay)
        if role is not None:
            w.role = role if role in WELL_ROLES else "unknown"
        elif (w.sample or w.assay) and w.role == "empty":
            w.role = "unknown"
        if replicate_group is not None:
            w.replicate_group = replicate_group.strip()
        if std_quantity is not None:
            w.std_quantity = std_quantity
        if note is not None:
            w.note = note.strip()
        if not w.sample and not w.assay and w.role == "empty":
            w.clear()
        return w

    def ensure_assay_color(self, assay: str) -> str:
        clean = assay.strip()
        if not clean:
            return "#6B7280"
        if clean not in self.assay_colors:
            idx = len(self.assay_colors) % len(ASSAY_PALETTE)
            self.assay_colors[clean] = ASSAY_PALETTE[idx]
        return self.assay_colors[clean]

    def iter_coords(self, direction: str = "row") -> Iterator[tuple[int, int]]:
        if direction == "col":
            for c in range(self.cols):
                for r in range(self.rows):
                    yield r, c
        else:
            for r in range(self.rows):
                for c in range(self.cols):
                    yield r, c

    def iter_wells(self, direction: str = "row") -> Iterator[Well]:
        for r, c in self.iter_coords(direction=direction):
            yield self.wells[(r, c)]

    def occupied_wells(self, direction: str = "row") -> list[Well]:
        return [w for w in self.iter_wells(direction=direction) if w.is_occupied]

    def assays(self) -> list[str]:
        seen: list[str] = []
        for w in self.iter_wells(direction="row"):
            if w.assay and w.assay not in seen:
                seen.append(w.assay)
                self.ensure_assay_color(w.assay)
        return seen

    def samples(self) -> list[tuple[str, float | None]]:
        """Return unique non-empty samples in plate order with their stock concentration."""
        seen: dict[str, float | None] = {}
        for w in self.iter_wells(direction="row"):
            if w.sample:
                if w.sample not in seen or (seen[w.sample] is None and w.concentration is not None):
                    seen[w.sample] = w.concentration
        return list(seen.items())

    def counts_by_assay(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for w in self.occupied_wells():
            key = w.assay or "(Unassigned)"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def counts_by_role(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for w in self.iter_wells():
            counts[w.role] = counts.get(w.role, 0) + 1
        return counts

    def resize_format(self, new_format_id: str) -> None:
        if new_format_id not in PLATE_FORMATS:
            raise ValueError(f"Unsupported plate format: {new_format_id!r}")
        self.format_id = new_format_id
        fmt = self.format
        preserved: dict[tuple[int, int], Well] = {}
        for (r, c), w in self.wells.items():
            if r < fmt.rows and c < fmt.cols:
                preserved[(r, c)] = w
        self.wells = preserved
        self._init_grid()

    def clear_all(self) -> None:
        for w in self.wells.values():
            w.clear()

    def clone(self) -> Plate:
        p = Plate(
            name=self.name,
            format_id=self.format_id,
            operator=self.operator,
            assay_colors=dict(self.assay_colors),
        )
        for pos, w in self.wells.items():
            p.wells[pos] = w.clone()
        return p

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "format_id": self.format_id,
            "operator": self.operator,
            "assay_colors": dict(self.assay_colors),
            "wells": [w.to_dict() for w in self.occupied_wells(direction="row")],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Plate:
        fmt_id = str(data.get("format_id", "96"))
        plate = cls(
            name=str(data.get("name", "Plate_01")),
            format_id=fmt_id if fmt_id in PLATE_FORMATS else "96",
            operator=str(data.get("operator", "")),
            assay_colors=dict(data.get("assay_colors", {})),
        )
        for w_data in data.get("wells", []):
            w = Well.from_dict(w_data)
            if 0 <= w.row < plate.rows and 0 <= w.col < plate.cols:
                plate.wells[(w.row, w.col)] = w
                if w.assay:
                    plate.ensure_assay_color(w.assay)
        return plate
