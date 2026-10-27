"""Step-by-Step Interactive Bench Pipetting Assistant dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from plate_core.mastermix import MixRecipe
from plate_core.models import Plate, row_label
from plate_core.normalization import NormalizationConfig, calculate_single_sample
from ui.plate_widget import PlateWidget


class PipettingDialog(QDialog):
    """Interactive bench-side pipetting guide with keyboard navigation and plate highlighting."""

    def __init__(
        self,
        plate: Plate,
        recipe: MixRecipe,
        norm_config: NormalizationConfig,
        theme_name: str = "dark",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.plate = plate
        self.recipe = recipe
        self.norm_config = norm_config
        self.theme_name = theme_name

        self.setWindowTitle(tr("pipet.title"))
        self.resize(860, 620)

        layout = QVBoxLayout(self)

        # Top mode bar
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel(tr("pipet.mode")))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(tr("pipet.mode.well"), "well")
        self.mode_combo.addItem(tr("pipet.mode.col"), "col")
        self.mode_combo.addItem(tr("pipet.mode.row"), "row")
        self.mode_combo.currentIndexChanged.connect(self._rebuild_steps)
        top_bar.addWidget(self.mode_combo)
        top_bar.addStretch(1)

        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        top_bar.addWidget(self.progress_label)
        layout.addLayout(top_bar)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Large instruction banner
        self.well_banner = QLabel()
        self.well_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.well_banner.setStyleSheet(
            "font-size: 20px; font-weight: bold; padding: 10px; "
            "border: 2px solid #f59e0b; border-radius: 6px;"
        )
        self.well_banner.setWordWrap(True)
        layout.addWidget(self.well_banner)

        self.vol_banner = QLabel()
        self.vol_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vol_banner.setStyleSheet("font-size: 15px; padding: 6px;")
        self.vol_banner.setWordWrap(True)
        layout.addWidget(self.vol_banner)

        # Embedded plate preview
        self.plate_view = PlateWidget(self.plate, self)
        self.plate_view.set_theme(self.theme_name)
        self.plate_view.selected_coords.clear()
        layout.addWidget(self.plate_view, stretch=1)

        # Navigation buttons
        nav_row = QHBoxLayout()
        self.reset_btn = QPushButton(tr("pipet.reset"))
        self.reset_btn.clicked.connect(self.reset_steps)
        self.prev_btn = QPushButton(tr("pipet.prev"))
        self.prev_btn.clicked.connect(self.prev_step)
        self.next_btn = QPushButton(tr("pipet.next"))
        self.next_btn.setObjectName("primaryBtn")
        self.next_btn.clicked.connect(self.next_step)

        nav_row.addWidget(self.reset_btn)
        nav_row.addStretch(1)
        nav_row.addWidget(self.prev_btn)
        nav_row.addWidget(self.next_btn)
        layout.addLayout(nav_row)

        self.steps: list[list[tuple[int, int]]] = []
        self.current_idx: int = 0
        self._rebuild_steps()

    def _rebuild_steps(self) -> None:
        mode = str(self.mode_combo.currentData() or "well")
        self.steps = []
        if mode == "col":
            for c in range(self.plate.cols):
                col_coords = [
                    (r, c)
                    for r in range(self.plate.rows)
                    if self.plate.get_well(r, c).is_occupied
                ]
                if col_coords:
                    self.steps.append(col_coords)
        elif mode == "row":
            for r in range(self.plate.rows):
                row_coords = [
                    (r, c)
                    for c in range(self.plate.cols)
                    if self.plate.get_well(r, c).is_occupied
                ]
                if row_coords:
                    self.steps.append(row_coords)
        else:
            for w in self.plate.occupied_wells(direction="row"):
                self.steps.append([(w.row, w.col)])

        self.current_idx = 0
        self._update_display()

    def reset_steps(self) -> None:
        self.current_idx = 0
        self._update_display()

    def next_step(self) -> None:
        if self.current_idx < len(self.steps):
            self.current_idx += 1
            self._update_display()

    def prev_step(self) -> None:
        if self.current_idx > 0:
            self.current_idx -= 1
            self._update_display()

    def _update_display(self) -> None:
        total = len(self.steps)
        if total == 0:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)
            self.progress_label.setText(tr("pipet.progress", cur=0, total=0))
            self.well_banner.setText(tr("mix.no_assays"))
            self.vol_banner.setText("")
            self.plate_view.set_highlighted_coords(set())
            return

        if self.current_idx >= total:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(total)
            self.progress_label.setText(tr("pipet.progress", cur=total, total=total))
            self.well_banner.setText(tr("pipet.done"))
            self.vol_banner.setText("")
            self.plate_view.set_highlighted_coords(set())
            return

        coords = self.steps[self.current_idx]
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(self.current_idx + 1)
        self.progress_label.setText(tr("pipet.progress", cur=self.current_idx + 1, total=total))
        self.plate_view.set_highlighted_coords(set(coords))

        if len(coords) == 1:
            r, c = coords[0]
            w = self.plate.get_well(r, c)
            self.well_banner.setText(
                tr(
                    "pipet.well_info",
                    coord=w.coord,
                    sample=w.sample or "—",
                    assay=w.assay or "—",
                    role=w.role.upper(),
                )
            )
            dna_vol = self.recipe.template_volume_ul
            water_vol = 0.0
            if w.role == "ntc":
                dna_vol = 0.0
                water_vol = self.recipe.template_volume_ul
            elif w.concentration is not None and w.concentration > 0:
                nrow = calculate_single_sample(w.sample, [w.coord], w.concentration, self.norm_config)
                dna_vol = nrow.dna_volume_ul
                water_vol = nrow.diluent_volume_ul

            self.vol_banner.setText(
                tr(
                    "pipet.volumes_info",
                    mix=self.recipe.dispense_per_well_ul,
                    dna=dna_vol,
                    water=water_vol,
                )
            )
        else:
            # Column or Row strip summary
            first_r, first_c = coords[0]
            mode = str(self.mode_combo.currentData() or "col")
            if mode == "col":
                strip_title = tr("pipet.col_strip", col=first_c + 1, n=len(coords))
            else:
                strip_title = tr("pipet.row_strip", row=row_label(first_r), n=len(coords))
            samples_preview = ", ".join(
                self.plate.get_well(r, c).sample or self.plate.get_well(r, c).role.upper()
                for r, c in coords[:6]
            )
            if len(coords) > 6:
                samples_preview += "…"
            self.well_banner.setText(f"{strip_title}  |  {samples_preview}")
            self.vol_banner.setText(
                tr(
                    "pipet.volumes_info",
                    mix=self.recipe.dispense_per_well_ul,
                    dna=self.recipe.template_volume_ul,
                    water=0.0,
                )
            )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_Return):
            self.next_step()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_Backspace):
            self.prev_step()
            return
        super().keyPressEvent(event)
