"""Main application window for platekit."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from i18n import language, set_language, tr
from plate_core.editing import (
    EditHistory,
    build_demo_plate,
    copy_wells,
    fill_serial_standards,
    parse_assay_lines,
    parse_sample_lines,
    paste_wells,
    smart_fill,
)
from plate_core.export import (
    export_bench_sheet_html,
    export_excel_workbook,
    render_bench_sheet_html,
)
from plate_core.instruments import (
    export_abi_sequencer_str,
    export_abi_sequencer_tsv,
    export_biorad_cfx_csv,
    export_biorad_cfx_str,
    export_quantstudio_csv,
    export_quantstudio_str,
    export_rotorgene_csv,
    export_rotorgene_str,
    import_instrument_layout_file,
)
from plate_core.models import PLATE_FORMATS, Plate, Well
from plate_core.normalization import apply_concentrations_to_plate, import_concentrations_file
from plate_core.sessions import (
    AppConfig,
    PlateProject,
    load_config,
    load_project,
    save_config,
    save_project,
)
from ui.inspector_panel import InspectorPanel
from ui.mix_panel import MixPanel
from ui.norm_panel import NormPanel
from ui.pipetting_dialog import PipettingDialog
from ui.plate_widget import PlateWidget
from ui.theme import app_qss


class MainWindow(QMainWindow):
    """Primary desktop window of platekit."""

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or load_config()
        set_language(self.config.language)

        self.project = PlateProject(plate=build_demo_plate())
        self.current_path: Path | None = None
        self.history = EditHistory()
        self._copied_wells: list[tuple[int, int, Well]] = []
        self._updating_ui = False

        self.resize(1240, 780)
        self._build_ui()
        self._build_menus_and_toolbar()
        self.apply_theme(self.config.theme == "dark")
        self.retranslate_ui()
        self._sync_all_views()

    @property
    def plate(self) -> Plate:
        return self.project.plate

    # --- UI construction ---

    def _build_ui(self) -> None:
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        # Tab 1: Plate Designer
        self.designer_tab = QSplitter(Qt.Orientation.Horizontal)
        self.plate_widget = PlateWidget(self.project.plate, self)
        self.plate_widget.set_color_mode(self.config.color_mode)
        self.plate_widget.selection_changed.connect(self._on_selection_changed)
        self.plate_widget.delete_requested.connect(self.clear_selected_wells)
        self.plate_widget.copy_requested.connect(self.copy_selected_wells)
        self.plate_widget.paste_requested.connect(self.paste_copied_wells)

        self.inspector = InspectorPanel(self)
        self.inspector.meta_changed.connect(self._on_meta_changed)
        self.inspector.apply_well_requested.connect(self._on_apply_well_props)
        self.inspector.clear_selected_requested.connect(self.clear_selected_wells)
        self.inspector.smart_fill_requested.connect(self._on_smart_fill)
        self.inspector.serial_std_requested.connect(self._on_serial_standards)

        self.designer_tab.addWidget(self.plate_widget)
        self.designer_tab.addWidget(self.inspector)
        self.designer_tab.setStretchFactor(0, 3)
        self.designer_tab.setStretchFactor(1, 1)
        self.designer_tab.setSizes([860, 380])
        self.tabs.addTab(self.designer_tab, "")

        # Tab 2: Master Mix Calculator
        self.mix_panel = MixPanel(self.project.plate, self.project.recipe, self)
        self.mix_panel.recipe_changed.connect(self._on_recipe_or_norm_changed)
        self.tabs.addTab(self.mix_panel, "")

        # Tab 3: DNA Normalization
        self.norm_panel = NormPanel(self.project.plate, self.project.norm_config, self)
        self.norm_panel.concentrations_updated.connect(self._sync_all_views)
        self.norm_panel.config_changed.connect(self._on_recipe_or_norm_changed)
        self.tabs.addTab(self.norm_panel, "")

        # Tab 4: Instrument & Bench Sheet Preview
        self.preview_tab = QWidget()
        prev_layout = QVBoxLayout(self.preview_tab)
        prev_bar = QHBoxLayout()
        self.preview_mode_combo = QComboBox()
        self.preview_mode_combo.addItem("Printable Bench Sheet (HTML)", "bench_html")
        self.preview_mode_combo.addItem("Bio-Rad CFX Plate Setup (CSV)", "cfx")
        self.preview_mode_combo.addItem("ABI QuantStudio / StepOne (CSV)", "quantstudio")
        self.preview_mode_combo.addItem("Qiagen Rotor-Gene Q (CSV)", "rotorgene")
        self.preview_mode_combo.addItem("ABI 3130/3500 Sequencer (TSV)", "abi_seq")
        self.preview_mode_combo.currentIndexChanged.connect(self._refresh_preview_tab)

        self.btn_save_preview = QPushButton()
        self.btn_save_preview.setObjectName("primaryBtn")
        self.btn_save_preview.clicked.connect(self._on_save_active_preview)

        self.btn_export_xlsx_tab = QPushButton()
        self.btn_export_xlsx_tab.clicked.connect(self.export_xlsx_dialog)

        prev_bar.addWidget(self.preview_mode_combo)
        prev_bar.addWidget(self.btn_save_preview)
        prev_bar.addWidget(self.btn_export_xlsx_tab)
        prev_bar.addStretch(1)
        prev_layout.addLayout(prev_bar)

        self.preview_browser = QTextBrowser()
        self.preview_browser.setOpenExternalLinks(False)
        prev_layout.addWidget(self.preview_browser, stretch=1)
        self.tabs.addTab(self.preview_tab, "")

        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _build_menus_and_toolbar(self) -> None:
        mb = self.menuBar()

        # File menu
        self.menu_file = mb.addMenu("")
        self.act_new = QAction(self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.triggered.connect(self.new_plate)

        self.act_open = QAction(self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self.open_project_dialog)

        self.act_save = QAction(self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self.save_project_dialog)

        self.act_save_as = QAction(self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(lambda: self.save_project_dialog(force_dialog=True))

        self.menu_import = self.menu_file.addMenu("")
        self.act_import_samples = QAction(self)
        self.act_import_samples.triggered.connect(self.import_sample_concentrations_dialog)
        self.act_import_inst = QAction(self)
        self.act_import_inst.triggered.connect(self.import_instrument_dialog)
        self.menu_import.addAction(self.act_import_samples)
        self.menu_import.addAction(self.act_import_inst)

        self.menu_export = self.menu_file.addMenu("")
        self.act_exp_xlsx = QAction(self)
        self.act_exp_xlsx.triggered.connect(self.export_xlsx_dialog)
        self.act_exp_bench = QAction(self)
        self.act_exp_bench.triggered.connect(self.export_bench_html_dialog)
        self.act_exp_cfx = QAction(self)
        self.act_exp_cfx.triggered.connect(self.export_cfx_dialog)
        self.act_exp_qs = QAction(self)
        self.act_exp_qs.triggered.connect(self.export_quantstudio_dialog)
        self.act_exp_rg = QAction(self)
        self.act_exp_rg.triggered.connect(self.export_rotorgene_dialog)
        self.act_exp_abi = QAction(self)
        self.act_exp_abi.triggered.connect(self.export_abi_seq_dialog)

        self.menu_export.addAction(self.act_exp_xlsx)
        self.menu_export.addAction(self.act_exp_bench)
        self.menu_export.addSeparator()
        self.menu_export.addAction(self.act_exp_cfx)
        self.menu_export.addAction(self.act_exp_qs)
        self.menu_export.addAction(self.act_exp_rg)
        self.menu_export.addAction(self.act_exp_abi)

        self.act_exit = QAction(self)
        self.act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_exit.triggered.connect(self.close)

        self.menu_file.addAction(self.act_new)
        self.menu_file.addAction(self.act_open)
        self.menu_file.addAction(self.act_save)
        self.menu_file.addAction(self.act_save_as)
        self.menu_file.addSeparator()
        self.menu_file.addMenu(self.menu_import)
        self.menu_file.addMenu(self.menu_export)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_exit)

        # Edit menu
        self.menu_edit = mb.addMenu("")
        self.act_undo = QAction(self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.triggered.connect(self.undo_edit)

        self.act_redo = QAction(self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.triggered.connect(self.redo_edit)

        self.act_copy = QAction(self)
        self.act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.act_copy.triggered.connect(self.copy_selected_wells)

        self.act_paste = QAction(self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.act_paste.triggered.connect(self.paste_copied_wells)

        self.act_clear_sel = QAction(self)
        self.act_clear_sel.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self.act_clear_sel.triggered.connect(self.clear_selected_wells)

        self.act_clear_all = QAction(self)
        self.act_clear_all.triggered.connect(self.clear_all_wells)

        self.act_select_all = QAction(self)
        self.act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.act_select_all.triggered.connect(self.plate_widget.select_all)

        self.menu_edit.addAction(self.act_undo)
        self.menu_edit.addAction(self.act_redo)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.act_copy)
        self.menu_edit.addAction(self.act_paste)
        self.menu_edit.addAction(self.act_clear_sel)
        self.menu_edit.addAction(self.act_clear_all)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.act_select_all)

        # View menu
        self.menu_view = mb.addMenu("")
        self.act_dark_theme = QAction(self)
        self.act_dark_theme.setCheckable(True)
        self.act_dark_theme.setChecked(self.config.theme == "dark")
        self.act_dark_theme.toggled.connect(self.apply_theme)

        self.act_lang_ru = QAction(self)
        self.act_lang_ru.setCheckable(True)
        self.act_lang_ru.triggered.connect(lambda: self.switch_language("ru"))

        self.act_lang_en = QAction(self)
        self.act_lang_en.setCheckable(True)
        self.act_lang_en.triggered.connect(lambda: self.switch_language("en"))

        self.menu_view.addAction(self.act_dark_theme)
        self.menu_view.addSeparator()
        self.menu_view.addAction(self.act_lang_ru)
        self.menu_view.addAction(self.act_lang_en)

        # Tools menu
        self.menu_tools = mb.addMenu("")
        self.act_pipetting = QAction(self)
        self.act_pipetting.triggered.connect(self.open_pipetting_assistant)
        self.act_load_demo = QAction(self)
        self.act_load_demo.triggered.connect(self.load_demo_plate)
        self.menu_tools.addAction(self.act_pipetting)
        self.menu_tools.addAction(self.act_load_demo)

        # Help menu
        self.menu_help = mb.addMenu("")
        self.act_about = QAction(self)
        self.act_about.triggered.connect(self.show_about_dialog)
        self.menu_help.addAction(self.act_about)

        # Toolbar
        tb = QToolBar("MainToolbar", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction(self.act_new)
        tb.addAction(self.act_open)
        tb.addAction(self.act_save)
        tb.addSeparator()
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addAction(self.act_clear_sel)
        tb.addSeparator()

        self.lbl_tb_format = QLabel()
        tb.addWidget(self.lbl_tb_format)
        self.format_combo = QComboBox()
        for fid, fmt in PLATE_FORMATS.items():
            self.format_combo.addItem(fmt.title, fid)
        self.format_combo.currentIndexChanged.connect(self._on_format_combo_changed)
        tb.addWidget(self.format_combo)

        tb.addSeparator()
        self.lbl_tb_color = QLabel()
        tb.addWidget(self.lbl_tb_color)
        self.color_combo = QComboBox()
        self.color_combo.addItem("Assay", "assay")
        self.color_combo.addItem("Role", "role")
        self.color_combo.currentIndexChanged.connect(self._on_color_combo_changed)
        tb.addWidget(self.color_combo)

        tb.addSeparator()
        self.lbl_tb_lang = QLabel()
        tb.addWidget(self.lbl_tb_lang)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("RU", "ru")
        self.lang_combo.addItem("EN", "en")
        self.lang_combo.currentIndexChanged.connect(self._on_lang_combo_changed)
        tb.addWidget(self.lang_combo)

        tb.addSeparator()
        tb.addAction(self.act_pipetting)
        tb.addAction(self.act_exp_xlsx)
        tb.addAction(self.act_exp_bench)

    # --- Theme & Localization ---

    def apply_theme(self, dark: bool) -> None:
        t_name = "dark" if dark else "light"
        self.config.theme = t_name
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(app_qss(dark))
        self.plate_widget.set_theme(t_name)
        self.norm_panel.set_theme(t_name)
        self._refresh_preview_tab()
        save_config(self.config)

    def switch_language(self, lang: str) -> None:
        set_language(lang)
        self.config.language = language()
        save_config(self.config)
        self.retranslate_ui()
        self._sync_all_views()

    def _on_lang_combo_changed(self, idx: int) -> None:
        if self._updating_ui or idx < 0:
            return
        code = str(self.lang_combo.itemData(idx))
        if code != language():
            self.switch_language(code)

    def retranslate_ui(self) -> None:
        self._updating_ui = True
        self.setWindowTitle(f"platekit — {self.plate.name}")
        self.act_lang_ru.setChecked(language() == "ru")
        self.act_lang_en.setChecked(language() == "en")
        l_idx = self.lang_combo.findData(language())
        if l_idx >= 0:
            self.lang_combo.setCurrentIndex(l_idx)

        self.menu_file.setTitle(tr("menu.file"))
        self.act_new.setText(tr("tb.new"))
        self.act_open.setText(tr("tb.open"))
        self.act_save.setText(tr("tb.save"))
        self.act_save_as.setText(tr("menu.file.save_as"))
        self.menu_import.setTitle(tr("menu.file.import"))
        self.act_import_samples.setText(tr("menu.file.import_samples"))
        self.act_import_inst.setText(tr("menu.file.import_instrument"))
        self.menu_export.setTitle(tr("menu.file.export"))
        self.act_exp_xlsx.setText(tr("tb.export_xlsx"))
        self.act_exp_bench.setText(tr("tb.export_bench"))
        self.act_exp_cfx.setText(tr("menu.file.export_cfx"))
        self.act_exp_qs.setText(tr("menu.file.export_quantstudio"))
        self.act_exp_rg.setText(tr("menu.file.export_rotorgene"))
        self.act_exp_abi.setText(tr("menu.file.export_abi_seq"))
        self.act_exit.setText(tr("menu.file.exit"))

        self.menu_edit.setTitle(tr("menu.edit"))
        self.act_undo.setText(tr("tb.undo"))
        self.act_redo.setText(tr("tb.redo"))
        self.act_copy.setText(tr("menu.edit.copy"))
        self.act_paste.setText(tr("menu.edit.paste"))
        self.act_clear_sel.setText(tr("tb.clear"))
        self.act_clear_all.setText(tr("menu.edit.clear_all"))
        self.act_select_all.setText(tr("menu.edit.select_all"))

        self.menu_view.setTitle(tr("menu.view"))
        self.act_dark_theme.setText(tr("menu.view.dark_theme"))
        self.act_lang_ru.setText(tr("menu.view.lang_ru"))
        self.act_lang_en.setText(tr("menu.view.lang_en"))

        self.menu_tools.setTitle(tr("menu.tools"))
        self.act_pipetting.setText(tr("tb.pipetting"))
        self.act_load_demo.setText(tr("menu.tools.load_demo"))

        self.menu_help.setTitle(tr("menu.help"))
        self.act_about.setText(tr("menu.help.about"))

        self.lbl_tb_format.setText(" " + tr("tb.format") + " ")
        self.lbl_tb_color.setText(" " + tr("tb.color_mode") + " ")
        self.lbl_tb_lang.setText(" " + tr("tb.lang") + " ")
        self.color_combo.setItemText(0, tr("tb.color.assay"))
        self.color_combo.setItemText(1, tr("tb.color.role"))

        self.preview_mode_combo.setItemText(0, tr("preview.bench_html"))
        self.preview_mode_combo.setItemText(1, tr("preview.cfx"))
        self.preview_mode_combo.setItemText(2, tr("preview.quantstudio"))
        self.preview_mode_combo.setItemText(3, tr("preview.rotorgene"))
        self.preview_mode_combo.setItemText(4, tr("preview.abi_seq"))

        self.tabs.setTabText(0, tr("tab.plate"))
        self.tabs.setTabText(1, tr("tab.mix"))
        self.tabs.setTabText(2, tr("tab.norm"))
        self.tabs.setTabText(3, tr("tab.export"))

        self.btn_save_preview.setText(tr("tb.save"))
        self.btn_export_xlsx_tab.setText(tr("tb.export_xlsx"))

        self.inspector.retranslate_ui(len(self.plate_widget.selected_coords))
        self.mix_panel.retranslate_ui()
        self.norm_panel.retranslate_ui()
        self._updating_ui = False

    # --- State synchronization ---

    def _record_undo(self, desc: str = "edit") -> None:
        self.history.push(self.history.capture(self.plate, desc))

    def _sync_all_views(self) -> None:
        self._updating_ui = True
        self.setWindowTitle(f"platekit — {self.plate.name}")
        f_idx = self.format_combo.findData(self.plate.format_id)
        if f_idx >= 0:
            self.format_combo.setCurrentIndex(f_idx)

        self.inspector.plate_name_edit.setText(self.plate.name)
        self.inspector.operator_edit.setText(self.plate.operator)

        self.plate_widget.update()
        self._on_selection_changed()
        self.mix_panel.set_plate(self.plate)
        self.norm_panel.set_plate(self.plate)
        self._refresh_preview_tab()
        self._update_status_bar()
        self.act_undo.setEnabled(self.history.can_undo)
        self.act_redo.setEnabled(self.history.can_redo)
        self._updating_ui = False

    def _update_status_bar(self) -> None:
        occ = len(self.plate.occupied_wells())
        self.statusBar().showMessage(
            tr(
                "status.ready",
                fmt=self.plate.format.title,
                occupied=occ,
                total=self.plate.total_wells,
            )
        )

    def _on_selection_changed(self) -> None:
        coords = self.plate_widget.ordered_selection()
        wells = [
            self.plate.get_well(r, c)
            for r, c in coords
            if 0 <= r < self.plate.rows and 0 <= c < self.plate.cols
        ]
        self.inspector.sync_from_selection(wells)

    def _on_meta_changed(self, name: str, operator: str) -> None:
        self.plate.name = name
        self.plate.operator = operator
        self.setWindowTitle(f"platekit — {self.plate.name}")
        self._refresh_preview_tab()

    def _on_format_combo_changed(self, idx: int) -> None:
        if self._updating_ui or idx < 0:
            return
        new_fmt = str(self.format_combo.itemData(idx))
        if new_fmt != self.plate.format_id:
            self._record_undo("resize_format")
            self.plate.resize_format(new_fmt)
            self.plate_widget.set_plate(self.plate)
            self._sync_all_views()

    def _on_color_combo_changed(self, idx: int) -> None:
        if idx < 0:
            return
        mode = str(self.color_combo.itemData(idx))
        self.config.color_mode = mode
        self.plate_widget.set_color_mode(mode)
        save_config(self.config)

    def _on_recipe_or_norm_changed(self) -> None:
        self._refresh_preview_tab()

    def _on_tab_changed(self, _idx: int) -> None:
        self._refresh_preview_tab()

    # --- Plate editing actions ---

    def _on_apply_well_props(self, props: dict) -> None:
        coords = self.plate_widget.ordered_selection()
        if not coords:
            return
        self._record_undo("apply_well_props")
        for r, c in coords:
            self.plate.set_well(
                r,
                c,
                sample=props["sample"],
                concentration=props["concentration"],
                clear_concentration=props["clear_concentration"],
                assay=props["assay"],
                role=props["role"],
                replicate_group=props["replicate_group"],
                std_quantity=props["std_quantity"],
                note=props["note"],
            )
        self._sync_all_views()

    def _on_smart_fill(self, params: dict) -> None:
        samples = parse_sample_lines(params["samples_text"])
        assays = parse_assay_lines(params["assays_text"])
        if not samples and not params["include_ntc"] and not params["include_pos"]:
            return
        self._record_undo("smart_fill")
        start_coord = (0, 0)
        if params.get("start_selected") and self.plate_widget.selected_coords:
            start_coord = min(self.plate_widget.selected_coords)
        elif not params.get("start_selected"):
            self.plate.clear_all()

        placed = smart_fill(
            self.plate,
            samples=samples,
            assays=assays,
            replicates=params["replicates"],
            direction=params["direction"],
            include_ntc=params["include_ntc"],
            include_pos=params["include_pos"],
            start_coord=start_coord,
        )
        self._sync_all_views()
        self.statusBar().showMessage(tr("status.smart_filled", n=placed), 5000)

    def _on_serial_standards(self, params: dict) -> None:
        self._record_undo("serial_standards")
        start_coord = (
            min(self.plate_widget.selected_coords)
            if self.plate_widget.selected_coords
            else (0, 0)
        )
        placed = fill_serial_standards(
            self.plate,
            assay=params["assay"],
            start_quantity=params["start_quantity"],
            dilution_factor=params["dilution_factor"],
            steps=params["steps"],
            replicates=params["replicates"],
            direction=params["direction"],
            start_coord=start_coord,
        )
        self._sync_all_views()
        self.statusBar().showMessage(tr("status.smart_filled", n=placed), 5000)

    def clear_selected_wells(self) -> None:
        coords = self.plate_widget.ordered_selection()
        if not coords:
            return
        self._record_undo("clear_selected")
        for r, c in coords:
            self.plate.get_well(r, c).clear()
        self._sync_all_views()

    def clear_all_wells(self) -> None:
        self._record_undo("clear_all")
        self.plate.clear_all()
        self._sync_all_views()

    def copy_selected_wells(self) -> None:
        self._copied_wells = copy_wells(self.plate, self.plate_widget.selected_coords)

    def paste_copied_wells(self) -> None:
        if not self._copied_wells or not self.plate_widget.selected_coords:
            return
        anchor = min(self.plate_widget.selected_coords)
        self._record_undo("paste_wells")
        paste_wells(self.plate, self._copied_wells, anchor)
        self._sync_all_views()

    def undo_edit(self) -> None:
        if self.history.undo(self.plate):
            self.plate_widget.set_plate(self.plate)
            self._sync_all_views()

    def redo_edit(self) -> None:
        if self.history.redo(self.plate):
            self.plate_widget.set_plate(self.plate)
            self._sync_all_views()

    # --- File / Project / Export operations ---

    def new_plate(self) -> None:
        self._record_undo("new_plate")
        self.project.plate = Plate(format_id=self.plate.format_id)
        self.current_path = None
        self.plate_widget.set_plate(self.project.plate)
        self._sync_all_views()

    def load_demo_plate(self) -> None:
        self._record_undo("load_demo")
        self.project.plate = build_demo_plate()
        self.plate_widget.set_plate(self.project.plate)
        self._sync_all_views()

    def open_path(self, path: str | Path) -> bool:
        try:
            proj = load_project(path)
            self.project = proj
            self.current_path = Path(path)
            self.history = EditHistory()
            self.plate_widget.set_plate(self.project.plate)
            self.mix_panel.set_recipe(self.project.recipe)
            self.norm_panel.set_config(self.project.norm_config)
            self.config.add_recent(path)
            save_config(self.config)
            self._sync_all_views()
            self.statusBar().showMessage(tr("status.loaded", path=str(path)), 5000)
            return True
        except Exception as exc:
            QMessageBox.critical(self, tr("err.title"), tr("err.open_failed", err=str(exc)))
            return False

    def open_project_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("menu.file.open"),
            "",
            "platekit Project (*.platekit.json *.json);;All Files (*)",
        )
        if path:
            self.open_path(path)

    def save_project_dialog(self, force_dialog: bool = False) -> bool:
        target = self.current_path
        if target is None or force_dialog:
            default_name = f"{self.plate.name}.platekit.json"
            path_str, _ = QFileDialog.getSaveFileName(
                self,
                tr("menu.file.save_as"),
                default_name,
                "platekit Project (*.platekit.json);;JSON (*.json)",
            )
            if not path_str:
                return False
            target = Path(path_str)

        try:
            save_project(self.project, target)
            self.current_path = target
            self.config.add_recent(target)
            save_config(self.config)
            self.statusBar().showMessage(tr("status.saved", path=str(target)), 5000)
            return True
        except Exception as exc:
            QMessageBox.critical(self, tr("err.title"), tr("err.save_failed", err=str(exc)))
            return False

    def import_sample_concentrations_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("menu.file.import_samples"),
            "",
            "CSV / TSV (*.csv *.tsv *.txt);;All Files (*)",
        )
        if not path:
            return
        concs = import_concentrations_file(path)
        if concs:
            self._record_undo("import_concentrations")
            apply_concentrations_to_plate(self.plate, concs)
            self._sync_all_views()

    def import_instrument_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("menu.file.import_instrument"),
            "",
            "Instrument CSV/TSV (*.csv *.tsv *.txt);;All Files (*)",
        )
        if not path:
            return
        self._record_undo("import_instrument")
        import_instrument_layout_file(self.plate, path)
        self._sync_all_views()

    def export_xlsx_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("menu.file.export_xlsx"),
            f"{self.plate.name}.xlsx",
            "Excel Workbook (*.xlsx)",
        )
        if path:
            export_excel_workbook(
                self.plate, self.project.recipe, self.project.norm_config, path
            )
            self.statusBar().showMessage(tr("status.exported", path=path), 5000)

    def export_bench_html_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("menu.file.export_bench_html"),
            f"{self.plate.name}_bench_sheet.html",
            "HTML Document (*.html)",
        )
        if path:
            export_bench_sheet_html(
                self.plate, self.project.recipe, self.project.norm_config, path
            )
            self.statusBar().showMessage(tr("status.exported", path=path), 5000)

    def export_cfx_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("menu.file.export_cfx"),
            f"{self.plate.name}_biorad_cfx.csv",
            "CSV (*.csv)",
        )
        if path:
            export_biorad_cfx_csv(self.plate, path)
            self.statusBar().showMessage(tr("status.exported", path=path), 5000)

    def export_quantstudio_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("menu.file.export_quantstudio"),
            f"{self.plate.name}_quantstudio.csv",
            "CSV (*.csv)",
        )
        if path:
            export_quantstudio_csv(self.plate, path)
            self.statusBar().showMessage(tr("status.exported", path=path), 5000)

    def export_rotorgene_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("menu.file.export_rotorgene"),
            f"{self.plate.name}_rotorgene.csv",
            "CSV (*.csv)",
        )
        if path:
            export_rotorgene_csv(self.plate, path)
            self.statusBar().showMessage(tr("status.exported", path=path), 5000)

    def export_abi_seq_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("menu.file.export_abi_seq"),
            f"{self.plate.name}_abi3500.tsv",
            "TSV (*.tsv *.txt)",
        )
        if path:
            export_abi_sequencer_tsv(self.plate, path)
            self.statusBar().showMessage(tr("status.exported", path=path), 5000)

    def _refresh_preview_tab(self) -> None:
        mode = str(self.preview_mode_combo.currentData() or "bench_html")
        if mode == "bench_html":
            html_doc = render_bench_sheet_html(
                self.plate,
                self.project.recipe,
                self.project.norm_config,
                dark=(self.config.theme == "dark"),
            )
            self.preview_browser.setHtml(html_doc)
        elif mode == "cfx":
            self.preview_browser.setPlainText(export_biorad_cfx_str(self.plate))
        elif mode == "quantstudio":
            self.preview_browser.setPlainText(export_quantstudio_str(self.plate))
        elif mode == "rotorgene":
            self.preview_browser.setPlainText(export_rotorgene_str(self.plate))
        elif mode == "abi_seq":
            self.preview_browser.setPlainText(export_abi_sequencer_str(self.plate))

    def _on_save_active_preview(self) -> None:
        mode = str(self.preview_mode_combo.currentData() or "bench_html")
        if mode == "bench_html":
            self.export_bench_html_dialog()
        elif mode == "cfx":
            self.export_cfx_dialog()
        elif mode == "quantstudio":
            self.export_quantstudio_dialog()
        elif mode == "rotorgene":
            self.export_rotorgene_dialog()
        elif mode == "abi_seq":
            self.export_abi_seq_dialog()

    def open_pipetting_assistant(self) -> None:
        dlg = PipettingDialog(
            plate=self.plate,
            recipe=self.project.recipe,
            norm_config=self.project.norm_config,
            theme_name=self.config.theme,
            parent=self,
        )
        dlg.exec()

    def show_about_dialog(self) -> None:
        QMessageBox.about(self, tr("dlg.about.title"), tr("dlg.about.body"))


def run(initial_path: str | Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("platekit")
    win = MainWindow()
    if initial_path:
        win.open_path(initial_path)
    win.show()
    return app.exec()
