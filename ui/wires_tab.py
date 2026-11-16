from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QHeaderView, QCheckBox
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, pyqtSignal
from database import DatabaseManager

class WiresTabWidget(QWidget):
    """Sidebar tab displaying all project wires. Pure UI: emits signals for edits and highlights."""
    
    wireEditRequested = pyqtSignal(dict)          # Emits wire_data dict on double-click
    wireHighlightToggled = pyqtSignal(str, bool)  # Emits (wire_id, is_highlighted)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wires_by_id = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Select", "Wire ID", "From", "To", "Wire Part #"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self._on_wire_double_clicked)

        layout.addWidget(self.table)

    def load_project(self, project_model):
        """Populates the wire table from the given project model."""
        wires = project_model.data.get("wires", []) if project_model and hasattr(project_model, "data") else []
        self._wires_by_id = {w.get("wire_id"): w for w in wires if w.get("wire_id")}

        # Build color lookup once per refresh instead of querying DB per row
        color_map = self._build_color_map()

        self.table.setRowCount(len(wires))
        for row, w in enumerate(wires):
            wire_id = w.get("wire_id", "")

            # 1. Highlight Checkbox Column
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)

            checkbox = QCheckBox()
            checkbox.setChecked(bool(w.get("is_highlighted", False)))
            checkbox.stateChanged.connect(
                lambda state, w_id=wire_id: self.wireHighlightToggled.emit(w_id, state == Qt.Checked)
            )
            checkbox_layout.addWidget(checkbox)
            self.table.setCellWidget(row, 0, checkbox_widget)

            # 2. Wire ID Column
            id_item = QTableWidgetItem(wire_id)
            id_item.setData(Qt.UserRole, wire_id)
            self.table.setItem(row, 1, id_item)

            # 3. From & 4. To Endpoints Columns
            endpoints = w.get("endpoints", [])
            self.table.setItem(row, 2, QTableWidgetItem(self._format_endpoint(endpoints, 0)))
            self.table.setItem(row, 3, QTableWidgetItem(self._format_endpoint(endpoints, 1)))

            # 5. Wire Part Number Column (Colored to match insulation)
            wire_pn = w.get("wire_part_number", "")
            color_code = w.get("color", "BK")
            pn_item = QTableWidgetItem(wire_pn or color_code)

            hex_color = color_map.get(color_code.upper(), "#7F7F7F")
            qcolor = QColor(hex_color)
            pn_item.setBackground(qcolor)

            luminance = (0.299 * qcolor.red() + 0.587 * qcolor.green() + 0.114 * qcolor.blue()) / 255
            pn_item.setForeground(QColor(Qt.white if luminance < 0.5 else Qt.black))

            self.table.setItem(row, 4, pn_item)

    def _format_endpoint(self, endpoints: list, index: int) -> str:
        if len(endpoints) <= index:
            return "Unassigned"
        ep = endpoints[index]
        node_id = ep.get("node_id", "")
        pin = ep.get("cavity_id") or ep.get("pin", "")
        return f"{node_id} (Pin: {pin})" if pin else node_id

    def _build_color_map(self) -> dict:
        fallback = {
            "BK": "#1a1a1a", "BN": "#8B4513", "RD": "#CC0000", "OR": "#FF8C00",
            "YE": "#D4AC0D", "GN": "#008000", "BU": "#0000CC", "VT": "#800080",
            "GY": "#7F7F7F", "WH": "#E5E5E5", "PK": "#FF69B4",
        }
        try:
            for col in DatabaseManager.get_colors():
                code = str(col.get("code", "")).upper()
                hex_val = col.get("hex") or col.get("hex_value")
                if code and hex_val:
                    fallback[code] = hex_val
        except Exception:
            pass
        return fallback

    def _on_wire_double_clicked(self, item):
        id_item = self.table.item(item.row(), 1)
        if not id_item:
            return
        wire_id = id_item.data(Qt.UserRole)
        wire_ref = self._wires_by_id.get(wire_id)
        if wire_ref:
            self.wireEditRequested.emit(wire_ref)