"""Master Mix Calculator tab with editable protocol presets and live per-assay breakdowns."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from plate_core.mastermix import OVERFILL_MODES, MixComponent, MixRecipe, calculate_plate_mixes
from plate_core.models import Plate
from plate_core.presets import builtin_recipes


class MixPanel(QWidget):
    """Interactive Master Mix editor and per-assay calculator."""

    recipe_changed = Signal()

    def __init__(
        self,
        plate: Plate,
        recipe: MixRecipe | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.plate = plate
        self.presets = builtin_recipes()
        self.recipe: MixRecipe = recipe or self.presets["pcr_standard"].clone()
        self._updating = False

        root_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        # Left pane: Recipe configuration & component editor
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.settings_group = QGroupBox()
        form = QFormLayout(self.settings_group)

        self.lbl_preset = QLabel()
        self.preset_combo = QComboBox()
        for pid, r in self.presets.items():
            self.preset_combo.addItem(r.name, pid)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)

        self.lbl_rxn_vol = QLabel()
        self.rxn_vol_spin = QDoubleSpinBox()
        self.rxn_vol_spin.setRange(1.0, 200.0)
        self.rxn_vol_spin.setDecimals(2)
        self.rxn_vol_spin.setSingleStep(1.0)
        self.rxn_vol_spin.valueChanged.connect(self._on_params_edited)

        self.lbl_tmpl_vol = QLabel()
        self.tmpl_vol_spin = QDoubleSpinBox()
        self.tmpl_vol_spin.setRange(0.0, 100.0)
        self.tmpl_vol_spin.setDecimals(2)
        self.tmpl_vol_spin.setSingleStep(0.5)
        self.tmpl_vol_spin.valueChanged.connect(self._on_params_edited)

        self.lbl_overfill_mode = QLabel()
        self.overfill_combo = QComboBox()
        for m in OVERFILL_MODES:
            self.overfill_combo.addItem(m, m)
        self.overfill_combo.currentIndexChanged.connect(self._on_params_edited)

        self.lbl_overfill_val = QLabel()
        self.overfill_val_spin = QDoubleSpinBox()
        self.overfill_val_spin.setRange(0.0, 100.0)
        self.overfill_val_spin.setDecimals(1)
        self.overfill_val_spin.setSingleStep(1.0)
        self.overfill_val_spin.valueChanged.connect(self._on_params_edited)

        form.addRow(self.lbl_preset, self.preset_combo)
        form.addRow(self.lbl_rxn_vol, self.rxn_vol_spin)
        form.addRow(self.lbl_tmpl_vol, self.tmpl_vol_spin)
        form.addRow(self.lbl_overfill_mode, self.overfill_combo)
        form.addRow(self.lbl_overfill_val, self.overfill_val_spin)
        left_layout.addWidget(self.settings_group)

        self.comp_group = QGroupBox()
        comp_layout = QVBoxLayout(self.comp_group)
        self.comp_table = QTableWidget(0, 4)
        self.comp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col_i in (1, 2, 3):
            self.comp_table.horizontalHeader().setSectionResizeMode(
                col_i, QHeaderView.ResizeMode.ResizeToContents
            )
        self.comp_table.itemChanged.connect(self._on_table_edited)
        comp_layout.addWidget(self.comp_table)

        btn_row = QHBoxLayout()
        self.add_comp_btn = QPushButton()
        self.add_comp_btn.clicked.connect(self._on_add_component)
        self.rem_comp_btn = QPushButton()
        self.rem_comp_btn.clicked.connect(self._on_remove_component)
        btn_row.addWidget(self.add_comp_btn)
        btn_row.addWidget(self.rem_comp_btn)
        comp_layout.addLayout(btn_row)

        self.warn_label = QLabel()
        self.warn_label.setStyleSheet("color: #ef4444; font-weight: bold;")
        self.warn_label.setWordWrap(True)
        comp_layout.addWidget(self.warn_label)

        left_layout.addWidget(self.comp_group)
        splitter.addWidget(left_widget)

        # Right pane: Calculated per-assay Master Mix cards
        self.results_group = QGroupBox()
        res_outer = QVBoxLayout(self.results_group)
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_scroll.setWidget(self.results_container)
        res_outer.addWidget(self.results_scroll)
        splitter.addWidget(self.results_group)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([460, 740])

        self.retranslate_ui()
        self.set_recipe(self.recipe)

    def retranslate_ui(self) -> None:
        self.settings_group.setTitle(tr("tab.mix"))
        self.lbl_preset.setText(tr("mix.preset"))
        self.lbl_rxn_vol.setText(tr("mix.rxn_vol"))
        self.lbl_tmpl_vol.setText(tr("mix.template_vol"))
        self.lbl_overfill_mode.setText(tr("mix.overfill_mode"))
        for idx, m in enumerate(OVERFILL_MODES):
            self.overfill_combo.setItemText(idx, tr(f"mix.overfill.{m}"))
        self.lbl_overfill_val.setText(tr("mix.overfill_val"))

        self.comp_group.setTitle(tr("mix.recipe_title"))
        self.comp_table.setHorizontalHeaderLabels(
            [
                tr("mix.col.component"),
                tr("mix.col.stock"),
                tr("mix.col.final"),
                tr("mix.col.vol_1x"),
            ]
        )
        self.add_comp_btn.setText(tr("mix.add_comp"))
        self.rem_comp_btn.setText(tr("mix.remove_comp"))
        self.results_group.setTitle(tr("mix.results_title"))
        self.refresh_calculations()

    def set_plate(self, plate: Plate) -> None:
        self.plate = plate
        self.refresh_calculations()

    def set_recipe(self, recipe: MixRecipe) -> None:
        self._updating = True
        self.recipe = recipe
        self.rxn_vol_spin.setValue(recipe.reaction_volume_ul)
        self.tmpl_vol_spin.setValue(recipe.template_volume_ul)
        m_idx = self.overfill_combo.findData(recipe.overfill_mode)
        if m_idx >= 0:
            self.overfill_combo.setCurrentIndex(m_idx)
        self.overfill_val_spin.setValue(recipe.overfill_value)

        self.comp_table.setRowCount(len(recipe.components))
        for r_idx, comp in enumerate(recipe.components):
            self.comp_table.setItem(r_idx, 0, QTableWidgetItem(comp.name))
            self.comp_table.setItem(r_idx, 1, QTableWidgetItem(comp.stock_conc))
            self.comp_table.setItem(r_idx, 2, QTableWidgetItem(comp.final_conc))
            self.comp_table.setItem(r_idx, 3, QTableWidgetItem(f"{comp.vol_per_rxn_ul:g}"))
        self._updating = False
        self.refresh_calculations()

    def _on_preset_selected(self, idx: int) -> None:
        if self._updating or idx < 0:
            return
        pid = str(self.preset_combo.itemData(idx))
        if pid in self.presets:
            self.set_recipe(self.presets[pid].clone())
            self.recipe_changed.emit()

    def _on_params_edited(self) -> None:
        if self._updating:
            return
        self.recipe.reaction_volume_ul = self.rxn_vol_spin.value()
        self.recipe.template_volume_ul = self.tmpl_vol_spin.value()
        self.recipe.overfill_mode = str(self.overfill_combo.currentData() or "percent")
        self.recipe.overfill_value = self.overfill_val_spin.value()
        self.refresh_calculations()
        self.recipe_changed.emit()

    def _on_table_edited(self, _item: QTableWidgetItem) -> None:
        if self._updating:
            return
        comps: list[MixComponent] = []
        for r in range(self.comp_table.rowCount()):
            name = (self.comp_table.item(r, 0).text() if self.comp_table.item(r, 0) else "").strip()
            stock = (self.comp_table.item(r, 1).text() if self.comp_table.item(r, 1) else "").strip()
            final = (self.comp_table.item(r, 2).text() if self.comp_table.item(r, 2) else "").strip()
            vol_txt = (
                self.comp_table.item(r, 3).text() if self.comp_table.item(r, 3) else "0"
            ).strip().replace(",", ".")
            try:
                vol = max(0.0, float(vol_txt))
            except ValueError:
                vol = 0.0
            comps.append(MixComponent(name or "Component", stock, final, vol))
        self.recipe.components = comps
        self.refresh_calculations()
        self.recipe_changed.emit()

    def _on_add_component(self) -> None:
        self.recipe.components.append(MixComponent("New Reagent", "10×", "1×", 1.0))
        self.set_recipe(self.recipe)
        self.recipe_changed.emit()

    def _on_remove_component(self) -> None:
        row = self.comp_table.currentRow()
        if 0 <= row < len(self.recipe.components):
            self.recipe.components.pop(row)
            self.set_recipe(self.recipe)
            self.recipe_changed.emit()

    def refresh_calculations(self) -> None:
        if self.recipe.exceeds_reaction_volume:
            self.warn_label.setText(
                tr(
                    "mix.warn_exceeds",
                    used=self.recipe.used_volume_ul,
                    total=self.recipe.reaction_volume_ul,
                )
            )
            self.warn_label.setVisible(True)
        else:
            self.warn_label.setVisible(False)

        # Clear existing cards
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        calcs = calculate_plate_mixes(
            self.plate,
            self.recipe,
            water_label=tr("mix.water_auto"),
        )
        if not calcs:
            empty_lbl = QLabel(tr("mix.no_assays"))
            empty_lbl.setWordWrap(True)
            self.results_layout.addWidget(empty_lbl)
            self.results_layout.addStretch(1)
            return

        for calc in calcs:
            card = QGroupBox(f"{calc.assay} ({calc.well_count})")
            vlay = QVBoxLayout(card)
            summary_lbl = QLabel(
                tr(
                    "mix.summary_header",
                    assay=calc.assay,
                    wells=calc.well_count,
                    eff=calc.effective_rxns,
                    total=calc.total_mix_volume_ul,
                    disp=calc.dispense_per_well_ul,
                    tmpl=calc.template_volume_ul,
                )
            )
            summary_lbl.setWordWrap(True)
            vlay.addWidget(summary_lbl)
            tbl = QTableWidget(len(calc.lines), 5)
            tbl.setHorizontalHeaderLabels(
                [
                    tr("mix.col.component"),
                    tr("mix.col.stock"),
                    tr("mix.col.final"),
                    tr("mix.col.vol_1x"),
                    tr("mix.col.vol_total"),
                ]
            )
            tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for col_i in (1, 2, 3, 4):
                tbl.horizontalHeader().setSectionResizeMode(
                    col_i, QHeaderView.ResizeMode.ResizeToContents
                )
            tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tbl.setMinimumHeight(min(220, 42 + 28 * len(calc.lines)))

            for r_i, ln in enumerate(calc.lines):
                c_item = QTableWidgetItem(ln.component)
                c_item.setFlags(c_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                c_item.setCheckState(Qt.CheckState.Unchecked)
                tbl.setItem(r_i, 0, c_item)
                tbl.setItem(r_i, 1, QTableWidgetItem(ln.stock_conc))
                tbl.setItem(r_i, 2, QTableWidgetItem(ln.final_conc))
                tbl.setItem(r_i, 3, QTableWidgetItem(f"{ln.vol_1x_ul:.2f}"))
                tot_item = QTableWidgetItem(f"{ln.vol_total_ul:.2f}")
                tot_Font = tot_item.font()
                tot_Font.setBold(True)
                tot_item.setFont(tot_Font)
                tbl.setItem(r_i, 4, tot_item)

            vlay.addWidget(tbl)
            self.results_layout.addWidget(card)

        self.results_layout.addStretch(1)
