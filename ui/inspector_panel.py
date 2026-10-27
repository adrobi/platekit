"""Side panel for editing selected wells, plate metadata, Smart Fill and Serial Standards."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from plate_core.models import WELL_ROLES, Well


class SerialStandardsDialog(QDialog):
    """Dialog to configure serial standard dilutions (STD)."""

    def __init__(self, default_assay: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("serial.title"))
        layout = QFormLayout(self)

        self.assay_edit = QLineEdit(default_assay)
        self.start_qty_spin = QDoubleSpinBox()
        self.start_qty_spin.setRange(1.0, 1e12)
        self.start_qty_spin.setDecimals(1)
        self.start_qty_spin.setValue(100000.0)

        self.factor_spin = QDoubleSpinBox()
        self.factor_spin.setRange(1.5, 1000.0)
        self.factor_spin.setDecimals(1)
        self.factor_spin.setValue(10.0)

        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(2, 12)
        self.steps_spin.setValue(5)

        self.reps_spin = QSpinBox()
        self.reps_spin.setRange(1, 6)
        self.reps_spin.setValue(2)

        layout.addRow(tr("insp.assay_name"), self.assay_edit)
        layout.addRow(tr("serial.start_qty"), self.start_qty_spin)
        layout.addRow(tr("serial.factor"), self.factor_spin)
        layout.addRow(tr("serial.steps"), self.steps_spin)
        layout.addRow(tr("smart.replicates"), self.reps_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class InspectorPanel(QScrollArea):
    """Inspector for plate metadata, selected well properties and Smart Fill."""

    meta_changed = Signal(str, str)  # plate_name, operator
    apply_well_requested = Signal(dict)
    clear_selected_requested = Signal()
    smart_fill_requested = Signal(dict)
    serial_std_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumWidth(340)

        container = QWidget()
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(8)

        # 1. Plate metadata group
        self.meta_group = QGroupBox()
        meta_form = QFormLayout(self.meta_group)
        self.plate_name_edit = QLineEdit("Plate_01")
        self.operator_edit = QLineEdit()
        self.plate_name_edit.editingFinished.connect(self._emit_meta)
        self.operator_edit.editingFinished.connect(self._emit_meta)
        self.lbl_plate_name = QLabel()
        self.lbl_operator = QLabel()
        meta_form.addRow(self.lbl_plate_name, self.plate_name_edit)
        meta_form.addRow(self.lbl_operator, self.operator_edit)
        self.main_layout.addWidget(self.meta_group)

        # 2. Selected wells editor group
        self.sel_group = QGroupBox()
        sel_form = QFormLayout(self.sel_group)
        self.sample_edit = QLineEdit()
        self.conc_edit = QLineEdit()
        self.conc_edit.setPlaceholderText("e.g. 42.5")
        self.assay_edit = QLineEdit()
        self.role_combo = QComboBox()
        for r in WELL_ROLES:
            self.role_combo.addItem(r.upper(), r)
        self.rep_edit = QLineEdit()
        self.std_edit = QLineEdit()
        self.note_edit = QLineEdit()

        self.lbl_sample = QLabel()
        self.lbl_conc = QLabel()
        self.lbl_assay = QLabel()
        self.lbl_role = QLabel()
        self.lbl_rep = QLabel()
        self.lbl_std = QLabel()
        self.lbl_note = QLabel()

        sel_form.addRow(self.lbl_sample, self.sample_edit)
        sel_form.addRow(self.lbl_conc, self.conc_edit)
        sel_form.addRow(self.lbl_assay, self.assay_edit)
        sel_form.addRow(self.lbl_role, self.role_combo)
        sel_form.addRow(self.lbl_rep, self.rep_edit)
        sel_form.addRow(self.lbl_std, self.std_edit)
        sel_form.addRow(self.lbl_note, self.note_edit)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton()
        self.apply_btn.setObjectName("primaryBtn")
        self.apply_btn.clicked.connect(self._on_apply_well)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self.clear_selected_requested.emit)
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.clear_btn)
        sel_form.addRow(btn_row)
        self.main_layout.addWidget(self.sel_group)

        # 3. Smart Fill group
        self.smart_group = QGroupBox()
        smart_layout = QVBoxLayout(self.smart_group)

        self.lbl_smart_samples = QLabel()
        self.smart_samples_edit = QPlainTextEdit()
        self.smart_samples_edit.setMaximumHeight(95)
        self.paste_samples_btn = QPushButton()
        self.paste_samples_btn.clicked.connect(self._on_paste_clipboard_samples)

        self.lbl_smart_assays = QLabel()
        self.smart_assays_edit = QPlainTextEdit()
        self.smart_assays_edit.setMaximumHeight(65)

        smart_form = QFormLayout()
        self.lbl_replicates = QLabel()
        self.reps_spin = QSpinBox()
        self.reps_spin.setRange(1, 12)
        self.reps_spin.setValue(2)

        self.lbl_direction = QLabel()
        self.dir_combo = QComboBox()
        self.dir_combo.addItem("Row", "row")
        self.dir_combo.addItem("Col", "col")

        smart_form.addRow(self.lbl_replicates, self.reps_spin)
        smart_form.addRow(self.lbl_direction, self.dir_combo)

        self.chk_ntc = QCheckBox()
        self.chk_ntc.setChecked(True)
        self.chk_pos = QCheckBox()
        self.chk_pos.setChecked(False)
        self.chk_start_sel = QCheckBox()
        self.chk_start_sel.setChecked(False)

        self.fill_btn = QPushButton()
        self.fill_btn.setObjectName("primaryBtn")
        self.fill_btn.clicked.connect(self._on_smart_fill)

        self.serial_btn = QPushButton()
        self.serial_btn.clicked.connect(self._on_serial_dialog)

        smart_layout.addWidget(self.lbl_smart_samples)
        smart_layout.addWidget(self.smart_samples_edit)
        smart_layout.addWidget(self.paste_samples_btn)
        smart_layout.addWidget(self.lbl_smart_assays)
        smart_layout.addWidget(self.smart_assays_edit)
        smart_layout.addLayout(smart_form)
        smart_layout.addWidget(self.chk_ntc)
        smart_layout.addWidget(self.chk_pos)
        smart_layout.addWidget(self.chk_start_sel)
        smart_layout.addWidget(self.fill_btn)
        smart_layout.addWidget(self.serial_btn)

        self.main_layout.addWidget(self.smart_group)
        self.main_layout.addStretch(1)
        self.setWidget(container)
        self.retranslate_ui()

    def retranslate_ui(self, selected_count: int = 1) -> None:
        self.meta_group.setTitle(tr("insp.plate_title"))
        self.lbl_plate_name.setText(tr("insp.plate_name"))
        self.lbl_operator.setText(tr("insp.operator"))

        self.sel_group.setTitle(tr("insp.selection_title", n=selected_count))
        self.lbl_sample.setText(tr("insp.sample_name"))
        self.lbl_conc.setText(tr("insp.sample_conc"))
        self.lbl_assay.setText(tr("insp.assay_name"))
        self.lbl_role.setText(tr("insp.well_role"))
        self.lbl_rep.setText(tr("insp.rep_group"))
        self.lbl_std.setText(tr("insp.std_conc"))
        self.lbl_note.setText(tr("insp.note"))

        for idx, r in enumerate(WELL_ROLES):
            self.role_combo.setItemText(idx, tr(f"role.{r}"))

        self.apply_btn.setText(tr("insp.apply_selected"))
        self.clear_btn.setText(tr("insp.clear_selected"))

        self.smart_group.setTitle(tr("smart.title"))
        self.lbl_smart_samples.setText(tr("smart.samples_label"))
        self.smart_samples_edit.setPlaceholderText(tr("smart.samples_placeholder"))
        self.paste_samples_btn.setText(tr("smart.paste_clipboard"))
        self.lbl_smart_assays.setText(tr("smart.assays_label"))
        self.smart_assays_edit.setPlaceholderText(tr("smart.assays_placeholder"))
        self.lbl_replicates.setText(tr("smart.replicates"))
        self.lbl_direction.setText(tr("smart.direction"))
        self.dir_combo.setItemText(0, tr("smart.dir.row"))
        self.dir_combo.setItemText(1, tr("smart.dir.col"))
        self.chk_ntc.setText(tr("smart.include_ntc"))
        self.chk_pos.setText(tr("smart.include_pos"))
        self.chk_start_sel.setText(tr("smart.start_selected"))
        self.fill_btn.setText(tr("smart.fill_btn"))
        self.serial_btn.setText(tr("smart.serial_btn"))

    def sync_from_selection(self, wells: list[Well]) -> None:
        self.sel_group.setTitle(tr("insp.selection_title", n=len(wells)))
        if not wells:
            return
        w0 = wells[0]
        self.sample_edit.setText(w0.sample)
        self.conc_edit.setText(f"{w0.concentration:g}" if w0.concentration is not None else "")
        self.assay_edit.setText(w0.assay)
        role_idx = self.role_combo.findData(w0.role)
        if role_idx >= 0:
            self.role_combo.setCurrentIndex(role_idx)
        self.rep_edit.setText(w0.replicate_group)
        self.std_edit.setText(f"{w0.std_quantity:g}" if w0.std_quantity is not None else "")
        self.note_edit.setText(w0.note)

    def _emit_meta(self) -> None:
        self.meta_changed.emit(
            self.plate_name_edit.text().strip() or "Plate_01",
            self.operator_edit.text().strip(),
        )

    def _on_apply_well(self) -> None:
        conc_txt = self.conc_edit.text().strip().replace(",", ".")
        conc_val: float | None = None
        if conc_txt:
            try:
                conc_val = float(conc_txt)
            except ValueError:
                conc_val = None

        std_txt = self.std_edit.text().strip().replace(",", ".")
        std_val: float | None = None
        if std_txt:
            try:
                std_val = float(std_txt)
            except ValueError:
                std_val = None

        role = str(self.role_combo.currentData() or "unknown")
        sample = self.sample_edit.text().strip()
        assay = self.assay_edit.text().strip()
        if (sample or assay) and role == "empty":
            role = "unknown"

        self.apply_well_requested.emit(
            {
                "sample": sample,
                "concentration": conc_val,
                "clear_concentration": (conc_val is None),
                "assay": assay,
                "role": role,
                "replicate_group": self.rep_edit.text().strip(),
                "std_quantity": std_val,
                "note": self.note_edit.text().strip(),
            }
        )

    def _on_paste_clipboard_samples(self) -> None:
        cb = QApplication.clipboard()
        if cb and cb.text().strip():
            self.smart_samples_edit.setPlainText(cb.text().strip())

    def _on_smart_fill(self) -> None:
        self.smart_fill_requested.emit(
            {
                "samples_text": self.smart_samples_edit.toPlainText(),
                "assays_text": self.smart_assays_edit.toPlainText(),
                "replicates": self.reps_spin.value(),
                "direction": str(self.dir_combo.currentData() or "row"),
                "include_ntc": self.chk_ntc.isChecked(),
                "include_pos": self.chk_pos.isChecked(),
                "start_selected": self.chk_start_sel.isChecked(),
            }
        )

    def _on_serial_dialog(self) -> None:
        dlg = SerialStandardsDialog(default_assay=self.assay_edit.text().strip(), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.serial_std_requested.emit(
                {
                    "assay": dlg.assay_edit.text().strip(),
                    "start_quantity": dlg.start_qty_spin.value(),
                    "dilution_factor": dlg.factor_spin.value(),
                    "steps": dlg.steps_spin.value(),
                    "replicates": dlg.reps_spin.value(),
                    "direction": str(self.dir_combo.currentData() or "row"),
                }
            )
