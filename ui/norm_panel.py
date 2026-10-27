"""DNA Normalization tab (C1*V1 = C2*V2 and per-reaction DNA mass calculator)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from plate_core.models import Plate
from plate_core.normalization import (
    NORM_MODES,
    NormalizationConfig,
    apply_concentrations_to_plate,
    calculate_normalization,
    import_concentrations_file,
    parse_concentration_table,
)
from ui.theme import theme


class NormPanel(QWidget):
    """Interactive DNA normalization calculator and sample concentration table."""

    concentrations_updated = Signal()
    config_changed = Signal()

    def __init__(
        self,
        plate: Plate,
        config: NormalizationConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.plate = plate
        self.config = config or NormalizationConfig()
        self.theme_name = "dark"
        self._updating = False

        layout = QVBoxLayout(self)

        # Top controls
        self.ctrl_group = QGroupBox()
        top_hbox = QHBoxLayout(self.ctrl_group)

        form_left = QFormLayout()
        self.lbl_mode = QLabel()
        self.mode_combo = QComboBox()
        for m in NORM_MODES:
            self.mode_combo.addItem(m, m)
        self.mode_combo.currentIndexChanged.connect(self._on_params_changed)

        self.lbl_target_conc = QLabel()
        self.target_conc_spin = QDoubleSpinBox()
        self.target_conc_spin.setRange(0.1, 1000.0)
        self.target_conc_spin.setDecimals(1)
        self.target_conc_spin.setValue(self.config.target_conc_ng_ul)
        self.target_conc_spin.valueChanged.connect(self._on_params_changed)

        self.lbl_final_vol = QLabel()
        self.final_vol_spin = QDoubleSpinBox()
        self.final_vol_spin.setRange(2.0, 500.0)
        self.final_vol_spin.setDecimals(1)
        self.final_vol_spin.setValue(self.config.final_volume_ul)
        self.final_vol_spin.valueChanged.connect(self._on_params_changed)

        form_left.addRow(self.lbl_mode, self.mode_combo)
        form_left.addRow(self.lbl_target_conc, self.target_conc_spin)
        form_left.addRow(self.lbl_final_vol, self.final_vol_spin)
        top_hbox.addLayout(form_left)

        form_right = QFormLayout()
        self.lbl_target_mass = QLabel()
        self.target_mass_spin = QDoubleSpinBox()
        self.target_mass_spin.setRange(0.5, 1000.0)
        self.target_mass_spin.setDecimals(1)
        self.target_mass_spin.setValue(self.config.target_mass_ng)
        self.target_mass_spin.valueChanged.connect(self._on_params_changed)

        self.lbl_max_tmpl = QLabel()
        self.max_tmpl_spin = QDoubleSpinBox()
        self.max_tmpl_spin.setRange(0.5, 50.0)
        self.max_tmpl_spin.setDecimals(2)
        self.max_tmpl_spin.setValue(self.config.max_template_vol_ul)
        self.max_tmpl_spin.valueChanged.connect(self._on_params_changed)

        self.lbl_min_pipet = QLabel()
        self.min_pipet_spin = QDoubleSpinBox()
        self.min_pipet_spin.setRange(0.1, 5.0)
        self.min_pipet_spin.setDecimals(2)
        self.min_pipet_spin.setSingleStep(0.1)
        self.min_pipet_spin.setValue(self.config.min_pipet_vol_ul)
        self.min_pipet_spin.valueChanged.connect(self._on_params_changed)

        form_right.addRow(self.lbl_target_mass, self.target_mass_spin)
        form_right.addRow(self.lbl_max_tmpl, self.max_tmpl_spin)
        form_right.addRow(self.lbl_min_pipet, self.min_pipet_spin)
        top_hbox.addLayout(form_right)

        layout.addWidget(self.ctrl_group)

        # Action toolbar
        btn_row = QHBoxLayout()
        self.import_btn = QPushButton()
        self.import_btn.clicked.connect(self._on_import_csv)
        self.paste_btn = QPushButton()
        self.paste_btn.clicked.connect(self._on_paste_clipboard)
        self.sync_btn = QPushButton()
        self.sync_btn.clicked.connect(self.refresh_table)
        btn_row.addWidget(self.import_btn)
        btn_row.addWidget(self.paste_btn)
        btn_row.addWidget(self.sync_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Normalization table
        self.table = QTableWidget(0, 8)
        for col_i in range(6):
            self.table.horizontalHeader().setSectionResizeMode(
                col_i, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_stock_cell_edited)
        layout.addWidget(self.table)

        self.retranslate_ui()
        self.set_config(self.config)

    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.refresh_table()

    def set_plate(self, plate: Plate) -> None:
        self.plate = plate
        self.refresh_table()

    def set_config(self, config: NormalizationConfig) -> None:
        self._updating = True
        self.config = config
        idx = self.mode_combo.findData(config.mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.target_conc_spin.setValue(config.target_conc_ng_ul)
        self.final_vol_spin.setValue(config.final_volume_ul)
        self.target_mass_spin.setValue(config.target_mass_ng)
        self.max_tmpl_spin.setValue(config.max_template_vol_ul)
        self.min_pipet_spin.setValue(config.min_pipet_vol_ul)
        self._updating = False
        self._update_field_states()
        self.refresh_table()

    def retranslate_ui(self) -> None:
        self.ctrl_group.setTitle(tr("tab.norm"))
        self.lbl_mode.setText(tr("norm.mode"))
        for idx, m in enumerate(NORM_MODES):
            self.mode_combo.setItemText(idx, tr(f"norm.mode.{m}"))
        self.lbl_target_conc.setText(tr("norm.target_conc"))
        self.lbl_final_vol.setText(tr("norm.final_vol"))
        self.lbl_target_mass.setText(tr("norm.target_mass"))
        self.lbl_max_tmpl.setText(tr("norm.max_template"))
        self.lbl_min_pipet.setText(tr("norm.min_pipet"))

        self.import_btn.setText(tr("norm.import_csv"))
        self.paste_btn.setText(tr("norm.paste_btn"))
        self.sync_btn.setText(tr("norm.sync_from_plate"))

        self.table.setHorizontalHeaderLabels(
            [
                tr("norm.col.sample"),
                tr("norm.col.wells"),
                tr("norm.col.stock"),
                tr("norm.col.predilution"),
                tr("norm.col.dna_vol"),
                tr("norm.col.diluent_vol"),
                tr("norm.col.final_info"),
                tr("norm.col.status"),
            ]
        )
        self.refresh_table()

    def _update_field_states(self) -> None:
        is_dil = self.config.mode == "dilution_plate"
        self.target_conc_spin.setEnabled(is_dil)
        self.final_vol_spin.setEnabled(is_dil)
        self.target_mass_spin.setEnabled(not is_dil)
        self.max_tmpl_spin.setEnabled(not is_dil)

    def _on_params_changed(self) -> None:
        if self._updating:
            return
        self.config.mode = str(self.mode_combo.currentData() or "per_reaction")
        self.config.target_conc_ng_ul = self.target_conc_spin.value()
        self.config.final_volume_ul = self.final_vol_spin.value()
        self.config.target_mass_ng = self.target_mass_spin.value()
        self.config.max_template_vol_ul = self.max_tmpl_spin.value()
        self.config.min_pipet_vol_ul = self.min_pipet_spin.value()
        self._update_field_states()
        self.refresh_table()
        self.config_changed.emit()

    def refresh_table(self) -> None:
        self._updating = True
        pal = theme(self.theme_name)
        rows = calculate_normalization(self.plate, self.config)
        self.table.setRowCount(len(rows))

        for r_i, nrow in enumerate(rows):
            # Only column 2 (Stock concentration) is user-editable
            it_sample = QTableWidgetItem(nrow.sample)
            it_sample.setFlags(it_sample.flags() & ~Qt.ItemFlag.ItemIsEditable)

            it_wells = QTableWidgetItem(", ".join(nrow.wells))
            it_wells.setFlags(it_wells.flags() & ~Qt.ItemFlag.ItemIsEditable)

            stock_str = f"{nrow.stock_conc_ng_ul:g}" if nrow.stock_conc_ng_ul is not None else ""
            it_stock = QTableWidgetItem(stock_str)

            predil_str = f"1:{nrow.predilution_factor}" if nrow.predilution_factor > 1 else "—"
            it_predil = QTableWidgetItem(predil_str)
            it_predil.setFlags(it_predil.flags() & ~Qt.ItemFlag.ItemIsEditable)

            it_dna = QTableWidgetItem(f"{nrow.dna_volume_ul:.2f}")
            it_dna.setFlags(it_dna.flags() & ~Qt.ItemFlag.ItemIsEditable)
            f_bold = it_dna.font()
            f_bold.setBold(True)
            it_dna.setFont(f_bold)

            it_dil = QTableWidgetItem(f"{nrow.diluent_volume_ul:.2f}")
            it_dil.setFlags(it_dil.flags() & ~Qt.ItemFlag.ItemIsEditable)

            it_res = QTableWidgetItem(nrow.final_summary)
            it_res.setFlags(it_res.flags() & ~Qt.ItemFlag.ItemIsEditable)

            status_txt = tr(
                f"norm.qc.{nrow.qc_status}",
                factor=nrow.predilution_factor,
            )
            it_status = QTableWidgetItem(status_txt)
            it_status.setFlags(it_status.flags() & ~Qt.ItemFlag.ItemIsEditable)

            if nrow.qc_status == "ok":
                it_status.setBackground(QColor(pal["qc_ok"]))
            elif nrow.qc_status == "too_concentrated":
                it_status.setBackground(QColor(pal["qc_warn"]))
            elif nrow.qc_status == "too_dilute":
                it_status.setBackground(QColor(pal["qc_err"]))

            self.table.setItem(r_i, 0, it_sample)
            self.table.setItem(r_i, 1, it_wells)
            self.table.setItem(r_i, 2, it_stock)
            self.table.setItem(r_i, 3, it_predil)
            self.table.setItem(r_i, 4, it_dna)
            self.table.setItem(r_i, 5, it_dil)
            self.table.setItem(r_i, 6, it_res)
            self.table.setItem(r_i, 7, it_status)

        self._updating = False

    def _on_stock_cell_edited(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != 2:
            return
        row = item.row()
        sample_item = self.table.item(row, 0)
        if not sample_item:
            return
        sample_name = sample_item.text().strip()
        txt = item.text().strip().replace(",", ".")
        try:
            conc_val = float(txt) if txt else None
        except ValueError:
            conc_val = None

        for w in self.plate.iter_wells():
            if w.sample == sample_name:
                w.concentration = conc_val
        self.refresh_table()
        self.concentrations_updated.emit()

    def _on_import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("norm.import_csv"),
            "",
            "CSV / TSV (*.csv *.tsv *.txt);;All Files (*)",
        )
        if not path:
            return
        concs = import_concentrations_file(path)
        if concs:
            apply_concentrations_to_plate(self.plate, concs)
            self.refresh_table()
            self.concentrations_updated.emit()

    def _on_paste_clipboard(self) -> None:
        cb = QApplication.clipboard()
        if not cb or not cb.text().strip():
            return
        concs = parse_concentration_table(cb.text())
        if concs:
            apply_concentrations_to_plate(self.plate, concs)
            self.refresh_table()
            self.concentrations_updated.emit()
