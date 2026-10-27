"""Interactive 96/384/strip/rotor plate canvas widget."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from plate_core.models import ROLE_COLORS, Plate, Well, row_label
from ui.theme import theme


class PlateWidget(QWidget):
    """Custom painted interactive plate layout widget."""

    selection_changed = Signal()
    well_double_clicked = Signal(int, int)
    delete_requested = Signal()
    copy_requested = Signal()
    paste_requested = Signal()

    HEADER_W = 34
    HEADER_H = 28
    LEGEND_H = 32
    PADDING = 10

    def __init__(self, plate: Plate | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plate: Plate = plate or Plate()
        self.theme_name: str = "dark"
        self.color_mode: str = "assay"  # "assay" | "role"
        self.selected_coords: set[tuple[int, int]] = {(0, 0)}
        self.highlighted_coords: set[tuple[int, int]] = set()
        self._drag_start: tuple[int, int] | None = None
        self._drag_additive: bool = False

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(540, 360)

    def set_plate(self, plate: Plate) -> None:
        self.plate = plate
        valid = {
            (r, c)
            for (r, c) in self.selected_coords
            if 0 <= r < plate.rows and 0 <= c < plate.cols
        }
        self.selected_coords = valid or {(0, 0)}
        self.update()
        self.selection_changed.emit()

    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.update()

    def set_color_mode(self, mode: str) -> None:
        self.color_mode = mode if mode in ("assay", "role") else "assay"
        self.update()

    def set_highlighted_coords(self, coords: set[tuple[int, int]]) -> None:
        self.highlighted_coords = set(coords)
        self.update()

    def select_all(self) -> None:
        self.selected_coords = set(self.plate.iter_coords())
        self.update()
        self.selection_changed.emit()

    def ordered_selection(self) -> list[tuple[int, int]]:
        return sorted(self.selected_coords)

    # --- Geometry helpers ---

    def _grid_rect(self) -> QRectF:
        w = max(100, self.width() - 2 * self.PADDING - self.HEADER_W)
        h = max(80, self.height() - 2 * self.PADDING - self.HEADER_H - self.LEGEND_H)
        return QRectF(self.PADDING + self.HEADER_W, self.PADDING + self.HEADER_H, w, h)

    def _cell_size(self) -> tuple[float, float]:
        gr = self._grid_rect()
        cw = gr.width() / max(1, self.plate.cols)
        ch = gr.height() / max(1, self.plate.rows)
        return cw, ch

    def _well_rect(self, row: int, col: int) -> QRectF:
        gr = self._grid_rect()
        cw, ch = self._cell_size()
        return QRectF(
            gr.left() + col * cw + 2.0,
            gr.top() + row * ch + 2.0,
            max(4.0, cw - 4.0),
            max(4.0, ch - 4.0),
        )

    def _hit_test(self, pos: QPointF) -> tuple[str, int, int]:
        """Return ('well', r, c), ('row', r, -1), ('col', -1, c), ('corner', -1, -1) or ('none', -1, -1)."""
        gr = self._grid_rect()
        cw, ch = self._cell_size()
        x, y = pos.x(), pos.y()

        in_left_hdr = self.PADDING <= x < gr.left()
        in_top_hdr = self.PADDING <= y < gr.top()
        in_grid_x = gr.left() <= x <= gr.right()
        in_grid_y = gr.top() <= y <= gr.bottom()

        if in_left_hdr and in_top_hdr:
            return ("corner", -1, -1)
        if in_top_hdr and in_grid_x:
            c = min(self.plate.cols - 1, max(0, int((x - gr.left()) / cw)))
            return ("col", -1, c)
        if in_left_hdr and in_grid_y:
            r = min(self.plate.rows - 1, max(0, int((y - gr.top()) / ch)))
            return ("row", r, -1)
        if in_grid_x and in_grid_y:
            c = min(self.plate.cols - 1, max(0, int((x - gr.left()) / cw)))
            r = min(self.plate.rows - 1, max(0, int((y - gr.top()) / ch)))
            return ("well", r, c)
        return ("none", -1, -1)

    # --- Painting ---

    def _well_base_color(self, w: Well) -> QColor:
        pal = theme(self.theme_name)
        if not w.is_occupied:
            return QColor(pal["well_empty"])
        if self.color_mode == "role":
            return QColor(ROLE_COLORS.get(w.role, "#3B82F6"))
        if w.assay:
            return QColor(self.plate.ensure_assay_color(w.assay))
        return QColor(ROLE_COLORS.get(w.role, "#6B7280"))

    def paintEvent(self, _event) -> None:
        pal = theme(self.theme_name)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background
        painter.fillRect(self.rect(), QColor(pal["bg"]))

        gr = self._grid_rect()
        cw, ch = self._cell_size()

        # Corner button
        corner_rect = QRectF(self.PADDING, self.PADDING, self.HEADER_W - 2, self.HEADER_H - 2)
        painter.setPen(QPen(QColor(pal["grid"]), 1))
        painter.setBrush(QColor(pal["header_bg"]))
        painter.drawRoundedRect(corner_rect, 4, 4)

        hdr_font = QFont(self.font())
        hdr_font.setBold(True)
        hdr_font.setPointSize(max(7, min(10, int(min(cw, ch) * 0.25))))
        painter.setFont(hdr_font)
        painter.setPen(QColor(pal["dim"]))
        painter.drawText(corner_rect, Qt.AlignmentFlag.AlignCenter, "All")

        # Column headers
        for c in range(self.plate.cols):
            crect = QRectF(gr.left() + c * cw + 1, self.PADDING, cw - 2, self.HEADER_H - 2)
            painter.setPen(QPen(QColor(pal["grid"]), 1))
            painter.setBrush(QColor(pal["header_bg"]))
            painter.drawRoundedRect(crect, 4, 4)
            painter.setPen(QColor(pal["text"]))
            painter.drawText(crect, Qt.AlignmentFlag.AlignCenter, str(c + 1))

        # Row headers
        for r in range(self.plate.rows):
            rrect = QRectF(self.PADDING, gr.top() + r * ch + 1, self.HEADER_W - 2, ch - 2)
            painter.setPen(QPen(QColor(pal["grid"]), 1))
            painter.setBrush(QColor(pal["header_bg"]))
            painter.drawRoundedRect(rrect, 4, 4)
            painter.setPen(QColor(pal["text"]))
            painter.drawText(rrect, Qt.AlignmentFlag.AlignCenter, row_label(r))

        # Wells
        is_dense = self.plate.rows >= 16 or self.plate.cols >= 24
        for r in range(self.plate.rows):
            for c in range(self.plate.cols):
                w = self.plate.get_well(r, c)
                wrect = self._well_rect(r, c)
                base_col = self._well_base_color(w)

                # Fill
                if w.is_occupied:
                    fill_col = QColor(base_col)
                    fill_col.setAlpha(65 if self.theme_name == "dark" else 48)
                else:
                    fill_col = QColor(pal["well_empty"])

                painter.setBrush(fill_col)

                # Border (highlighted / selected / normal)
                if (r, c) in self.highlighted_coords:
                    pen = QPen(QColor(pal["pipet_active"]), 3.0)
                elif (r, c) in self.selected_coords:
                    pen = QPen(QColor(pal["selection"]), 2.2)
                elif w.is_occupied:
                    pen = QPen(base_col, 1.5)
                else:
                    pen = QPen(QColor(pal["well_border"]), 1.0)

                painter.setPen(pen)
                radius = 4.0 if is_dense else 6.0
                painter.drawRoundedRect(wrect, radius, radius)

                if not w.is_occupied:
                    if not is_dense:
                        coord_font = QFont(self.font())
                        coord_font.setPointSize(7)
                        painter.setFont(coord_font)
                        painter.setPen(QColor(pal["dim"]))
                        painter.drawText(
                            wrect.adjusted(4, 2, -2, -2),
                            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                            w.coord,
                        )
                    continue

                # Left color stripe inside occupied well
                stripe_rect = QRectF(wrect.left() + 1, wrect.top() + 2, 4.0, wrect.height() - 4)
                painter.fillRect(stripe_rect, base_col)

                if is_dense:
                    # Compact label for 384-well plates
                    tiny_font = QFont(self.font())
                    tiny_font.setPointSize(6)
                    tiny_font.setBold(True)
                    painter.setFont(tiny_font)
                    painter.setPen(QColor(pal["text"]))
                    short_txt = (w.sample or w.role.upper())[:4]
                    painter.drawText(wrect.adjusted(5, 0, -1, 0), Qt.AlignmentFlag.AlignCenter, short_txt)
                    continue

                # Role badge in top-right if control/std
                if w.role != "unknown":
                    badge_font = QFont(self.font())
                    badge_font.setPointSize(6)
                    badge_font.setBold(True)
                    painter.setFont(badge_font)
                    role_col = QColor(ROLE_COLORS.get(w.role, "#6B7280"))
                    painter.setPen(role_col)
                    painter.drawText(
                        wrect.adjusted(6, 2, -4, -2),
                        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                        w.role.upper(),
                    )

                # Sample name
                s_font = QFont(self.font())
                s_font.setPointSize(8 if cw >= 58 else 7)
                s_font.setBold(True)
                painter.setFont(s_font)
                painter.setPen(QColor(pal["text"]))
                sample_label = w.sample or w.role.upper()
                metrics = painter.fontMetrics()
                elided_sample = metrics.elidedText(
                    sample_label, Qt.TextElideMode.ElideRight, int(wrect.width() - 10)
                )
                painter.drawText(
                    wrect.adjusted(7, int(ch * 0.22), -3, -2),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    elided_sample,
                )

                # Assay & concentration subtitle
                sub_font = QFont(self.font())
                sub_font.setPointSize(7 if cw >= 58 else 6)
                painter.setFont(sub_font)
                painter.setPen(QColor(pal["dim"]))
                sub_parts: list[str] = []
                if w.assay:
                    sub_parts.append(w.assay)
                if w.concentration is not None:
                    sub_parts.append(f"{w.concentration:g}ng")
                elif w.std_quantity is not None:
                    sub_parts.append(f"{w.std_quantity:g}")
                sub_str = " · ".join(sub_parts)
                if sub_str:
                    elided_sub = painter.fontMetrics().elidedText(
                        sub_str, Qt.TextElideMode.ElideRight, int(wrect.width() - 10)
                    )
                    painter.drawText(
                        wrect.adjusted(7, int(ch * 0.56), -3, -2),
                        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                        elided_sub,
                    )

        # Legend bar at bottom
        self._draw_legend(painter, pal)

    def _draw_legend(self, painter: QPainter, pal: dict) -> None:
        y = self.height() - self.LEGEND_H + 6
        x = float(self.PADDING + self.HEADER_W)
        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)

        items: list[tuple[str, str]] = []
        if self.color_mode == "assay":
            for assay in self.plate.assays():
                items.append((assay, self.plate.ensure_assay_color(assay)))
            for r_key in ("ntc", "pos", "std"):
                items.append((r_key.upper(), ROLE_COLORS[r_key]))
        else:
            for r_key in ("unknown", "ntc", "pos", "std", "ipc"):
                items.append((r_key.upper(), ROLE_COLORS[r_key]))

        for label, hex_col in items:
            if x > self.width() - 90:
                break
            swatch = QRectF(x, y + 2, 12, 12)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(hex_col))
            painter.drawRoundedRect(swatch, 3, 3)
            painter.setPen(QColor(pal["text"]))
            text_w = painter.fontMetrics().horizontalAdvance(label) + 18
            painter.drawText(QRectF(x + 16, y, text_w, 16), Qt.AlignmentFlag.AlignVCenter, label)
            x += text_w + 14

    # --- Mouse & Keyboard interaction ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        kind, r, c = self._hit_test(event.position())
        mods = event.modifiers()
        additive = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))

        if kind == "corner":
            self.select_all()
            return
        if kind == "col":
            col_wells = {(row, c) for row in range(self.plate.rows)}
            self.selected_coords = (self.selected_coords | col_wells) if additive else col_wells
            self.update()
            self.selection_changed.emit()
            return
        if kind == "row":
            row_wells = {(r, col) for col in range(self.plate.cols)}
            self.selected_coords = (self.selected_coords | row_wells) if additive else row_wells
            self.update()
            self.selection_changed.emit()
            return
        if kind == "well":
            self._drag_start = (r, c)
            self._drag_additive = additive
            if mods & Qt.KeyboardModifier.ControlModifier:
                if (r, c) in self.selected_coords and len(self.selected_coords) > 1:
                    self.selected_coords.remove((r, c))
                else:
                    self.selected_coords.add((r, c))
            else:
                self.selected_coords = {(r, c)}
            self.update()
            self.selection_changed.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        kind, r, c = self._hit_test(event.position())
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_start is not None and kind == "well":
            r0, c0 = self._drag_start
            r_min, r_max = min(r0, r), max(r0, r)
            c_min, c_max = min(c0, c), max(c0, c)
            rect_coords = {
                (rr, cc)
                for rr in range(r_min, r_max + 1)
                for cc in range(c_min, c_max + 1)
            }
            if self._drag_additive:
                self.selected_coords |= rect_coords
            else:
                self.selected_coords = rect_coords
            self.update()
            self.selection_changed.emit()
            return

        # Hover tooltip
        if kind == "well":
            w = self.plate.get_well(r, c)
            if w.is_occupied:
                tip_lines = [f"<b>Well {w.coord}</b> ({w.role.upper()})"]
                if w.sample:
                    tip_lines.append(f"Sample: <b>{w.sample}</b>")
                if w.concentration is not None:
                    tip_lines.append(f"DNA Conc: {w.concentration:g} ng/µL")
                if w.assay:
                    tip_lines.append(f"Assay: <b>{w.assay}</b>")
                if w.replicate_group:
                    tip_lines.append(f"Replicate group: {w.replicate_group}")
                if w.std_quantity is not None:
                    tip_lines.append(f"Standard quantity: {w.std_quantity:g}")
                if w.note:
                    tip_lines.append(f"Note: {w.note}")
                QToolTip.showText(event.globalPosition().toPoint(), "<br>".join(tip_lines), self)
            else:
                QToolTip.hideText()
        else:
            QToolTip.hideText()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        self._drag_start = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        kind, r, c = self._hit_test(event.position())
        if kind == "well":
            self.well_double_clicked.emit(r, c)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit()
            return
        if mods & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_A:
                self.select_all()
                return
            if key == Qt.Key.Key_C:
                self.copy_requested.emit()
                return
            if key == Qt.Key.Key_V:
                self.paste_requested.emit()
                return
        super().keyPressEvent(event)
