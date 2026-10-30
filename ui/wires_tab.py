from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QRadioButton, QButtonGroup, QHBoxLayout, QHeaderView,QDialog,QCheckBox
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from ui.wire_dialog import WirePropertiesDialog
from database import DatabaseManager

class WiresTabWidget(QWidget):
    """Sidebar tab displaying a master list of all project wires with radio selection and endpoints."""
    
    def __init__(self, current_project,undo_stack=None, parent=None):
        super().__init__(parent)
        self.current_project = parent.current_project
        self.parent_window = parent
        self.undo_stack = undo_stack
        self._init_ui()
        self.refresh_wires()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Select", "Wire ID", "From", "To", "Wire Part #"])
        
        # Table styling & sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self._on_wire_double_clicked)

        layout.addWidget(self.table)
        


    def refresh_wires(self):
        """Populates the table with wires and applies color-matched styling to the part number cell."""
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        
        wires = []
        if self.parent_window.current_project and hasattr(self.parent_window.current_project, "data"):
            wires = self.parent_window.current_project.data.get("wires", [])

        self.table.setRowCount(len(wires))
        
        for row, w in enumerate(wires):
            wire_id = w.get("wire_id", "")
            
            # 1. Highlight Checkbox Column (Individual selection)
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox = QCheckBox()
            checkbox.setChecked(w.get("is_highlighted", False))
            checkbox.stateChanged.connect(lambda state, wire=w: self._on_highlight_changed(wire, state))
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, checkbox_widget)

            # 2. Wire ID Column
            id_item = QTableWidgetItem(wire_id)
            id_item.setData(Qt.UserRole, wire_id)
            self.table.setItem(row, 1, id_item)

            # 3. From & 4. To Endpoints Columns
            endpoints = w.get("endpoints", [])
            from_str = "Unassigned"
            to_str = "Unassigned"
            
            if len(endpoints) > 0:
                ep1 = endpoints[0]
                node_id = ep1.get("node_id", "")
                pin = ep1.get("cavity_id") or ep1.get("pin", "")
                from_str = f"{node_id} (Pin: {pin})" if pin else node_id
                
            if len(endpoints) > 1:
                ep2 = endpoints[1]
                node_id = ep2.get("node_id", "")
                pin = ep2.get("cavity_id") or ep2.get("pin", "")
                to_str = f"{node_id} (Pin: {pin})" if pin else node_id

            self.table.setItem(row, 2, QTableWidgetItem(from_str))
            self.table.setItem(row, 3, QTableWidgetItem(to_str))

            # 5. Wire Part Number Column (Colored to match wire insulation)
            wire_pn = w.get("wire_part_number", "")
            color_code = w.get("color", "BK")
            
            item = QTableWidgetItem(wire_pn or color_code)
            hex_color = self._get_hex_for_color_code(color_code)
            
            if hex_color:
                qcolor = QColor(hex_color)
                item.setBackground(qcolor)
                
                # Calculate relative luminance to determine text contrast (white vs black)
                luminance = (0.299 * qcolor.red() + 0.587 * qcolor.green() + 0.114 * qcolor.blue()) / 255
                if luminance < 0.5:
                    item.setForeground(QColor(Qt.white))
                else:
                    item.setForeground(QColor(Qt.black))
                    
            self.table.setItem(row, 4, item)
    def _on_highlight_changed(self, wire_dict, state):
        """Saves individual wire highlight state and triggers canvas repaint."""
        wire_dict["is_highlighted"] = bool(state == Qt.Checked)
        
        if self.parent_window.current_project and hasattr(self.parent_window.current_project, "data"):
            DatabaseManager.save_project(self.parent_window.current_project.data)
            
        # Trigger canvas refresh on parent window if available
        main_win = self.window()
        if  hasattr(main_win, "cad_canvas"):
            main_win.cad_canvas.re_load_topology()
    def _get_hex_for_color_code(self, code: str) -> str:
        """Resolves color code to hex, supporting database colors with fallback automotive standards."""
        try:
            colors = DatabaseManager.get_colors()
            for col in colors:
                if col.get("code") == code:
                    h = col.get("hex") or col.get("hex_value")
                    if h:
                        return h
        except Exception:
            pass
            
        # Standard automotive color code mappings
        mapping = {
            "BK": "#1a1a1a",  # Black
            "BN": "#8B4513",  # Brown
            "RD": "#CC0000",  # Red
            "OR": "#FF8C00",  # Orange
            "YE": "#D4AC0D",  # Yellow
            "GN": "#008000",  # Green
            "BU": "#0000CC",  # Blue
            "VT": "#800080",  # Violet
            "GY": "#7F7F7F",  # Grey
            "WH": "#E5E5E5",  # White
            "PK": "#FF69B4",  # Pink
        }
        return mapping.get(code.upper(), "#7F7F7F")

    def _on_wire_double_clicked(self, item):
        """Looks up the wire dynamically by ID and opens the properties dialog."""
        row = item.row()
        id_item = self.table.item(row, 1)
        if not id_item:
            return
            
        wire_id = id_item.data(Qt.UserRole)
        if not wire_id:
            return

        # Fetch fresh reference from project model
        wires = self.parent_window.current_project.data.get("wires", [])
        wire_ref = next((w for w in wires if w.get("wire_id") == wire_id), None)
        if not wire_ref:
            return

        dialog = WirePropertiesDialog(wire_ref, self.parent_window.current_project,self.undo_stack,self.parent_window.wires_tab.refresh_wires, self)
        if dialog.exec_() == QDialog.Accepted:
            self.refresh_wires()
            if self.parent_window.current_project and hasattr(self.parent_window.current_project, "data"):
                DatabaseManager.save_project(self.parent_window.current_project.data)