from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTableWidget, QTableWidgetItem, QDialogButtonBox, QGroupBox, QFormLayout, QPushButton, QCheckBox
)
from PyQt5.QtCore import Qt

class ConnectorPropertiesDialog(QDialog):
    """Properties and cavity manager dialog with explicit is_junction support."""
    
    def __init__(self, node_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Node Properties - {node_data.get('ref_designator', 'Node')}")
        self.resize(520, 460)
        
        self.node_data = node_data
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.id_input = QLineEdit(self.node_data.get("node_id", ""))
        self.id_input.setReadOnly(True)
        form_layout.addRow("Node ID:", self.id_input)

        self.ref_input = QLineEdit(self.node_data.get("ref_designator", ""))
        form_layout.addRow("Reference Designator:", self.ref_input)

        self.part_input = QLineEdit(self.node_data.get("part_number", ""))
        form_layout.addRow("Part Number:", self.part_input)

        # Explicit Is Junction Checkbox
        self.junction_checkbox = QCheckBox("Is Splice Junction")
        self.junction_checkbox.setChecked(self.node_data.get("is_junction", False))
        form_layout.addRow("Node Type:", self.junction_checkbox)

        layout.addLayout(form_layout)

        # Cavity & Pin Configuration Group (Hidden or adjusted if junction, but kept for flexibility)
        pin_group = QGroupBox("Connector Cavities & Pins")
        pin_layout = QVBoxLayout(pin_group)

        self.pin_table = QTableWidget()
        self.pin_table.setColumnCount(3)
        self.pin_table.setHorizontalHeaderLabels(["Cavity ID", "Pin Number", "Insertion Depth (mm)"])
        
        pins = self.node_data.get("pins", [])
        self.pin_table.setRowCount(len(pins))
        
        for row, pin in enumerate(pins):
            self.pin_table.setItem(row, 0, QTableWidgetItem(str(pin.get("cavity_id", ""))))
            self.pin_table.setItem(row, 1, QTableWidgetItem(str(pin.get("pin_number", ""))))
            self.pin_table.setItem(row, 2, QTableWidgetItem(str(pin.get("insertion_depth_mm", 0.0))))

        pin_layout.addWidget(self.pin_table)

        btn_row = QHBoxLayout()
        self.add_row_btn = QPushButton("Add Cavity/Pin")
        self.add_row_btn.clicked.connect(self._add_pin_row)
        btn_row.addWidget(self.add_row_btn)

        self.del_row_btn = QPushButton("Remove Selected Pin")
        self.del_row_btn.clicked.connect(self._del_pin_row)
        btn_row.addWidget(self.del_row_btn)

        pin_layout.addLayout(btn_row)
        layout.addWidget(pin_group)

        # Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.save_data)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_pin_row(self):
        row = self.pin_table.rowCount()
        self.pin_table.insertRow(row)
        self.pin_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.pin_table.setItem(row, 1, QTableWidgetItem(str(row + 1)))
        self.pin_table.setItem(row, 2, QTableWidgetItem("3.0"))

    def _del_pin_row(self):
        selected_rows = set(item.row() for item in self.pin_table.selectedItems())
        for row in sorted(selected_rows, reverse=True):
            self.pin_table.removeRow(row)

    def save_data(self):
        """Saves modifications including is_junction boolean state."""
        self.node_data["ref_designator"] = self.ref_input.text().strip()
        self.node_data["part_number"] = self.part_input.text().strip()
        self.node_data["is_junction"] = self.junction_checkbox.isChecked()

        updated_pins = []
        for row in range(self.pin_table.rowCount()):
            cav_item = self.pin_table.item(row, 0)
            pin_item = self.pin_table.item(row, 1)
            depth_item = self.pin_table.item(row, 2)

            if cav_item and cav_item.text().strip():
                try:
                    depth = float(depth_item.text()) if depth_item else 0.0
                except ValueError:
                    depth = 0.0

                updated_pins.append({
                    "cavity_id": cav_item.text().strip(),
                    "pin_number": pin_item.text().strip() if pin_item else cav_item.text().strip(),
                    "insertion_depth_mm": depth
                })

        self.node_data["pins"] = updated_pins
        self.accept()