from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTableWidget, QTableWidgetItem, QDialogButtonBox, QGroupBox, QFormLayout
)
from PyQt5.QtCore import Qt
from models.harness_calculations import HarnessCalculator
from ui.wire_dialog import WirePropertiesDialog
from database import DatabaseManager

class BundleCalculationDialog(QDialog):
    """Detailed calculation breakdown and override dialog for a single harness bundle."""
    
    def __init__(self, bundle_data: dict, project_model, undo_stack=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Bundle Diameter Calculation - {bundle_data.get('bundle_id')}")
        self.resize(700, 520)
        
        self.bundle_data = bundle_data
        self.project_model = project_model
        self.undo_stack = undo_stack
        self.parent_window = parent
        
        self._init_ui()
        self._refresh_calculations()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Summary Info Group
        info_group = QGroupBox("Diameter Summary")
        info_layout = QFormLayout(info_group)

        self.method_label = QLabel()
        info_layout.addRow("Calculation Method:", self.method_label)

        self.calc_val_label = QLabel()
        info_layout.addRow("Bundle Diameter:", self.calc_val_label)

        # Manual Override Input
        override_val = self.bundle_data.get("override_diameter_mm")
        self.override_input = QLineEdit(str(override_val) if override_val is not None else "")
        self.override_input.setPlaceholderText("Leave blank for calculated diameter")
        info_layout.addRow("Overridden Diameter (mm):", self.override_input)

        self.status_label = QLabel()
        info_layout.addRow("Status / Warnings:", self.status_label)

        layout.addWidget(info_group)

        # Contained Wires Table (Double-click to open WirePropertiesDialog)
        wires_group = QGroupBox("Contained Wires & Cables (Double-click any wire to edit properties & OD)")
        wires_layout = QVBoxLayout(wires_group)

        self.wire_table = QTableWidget()
        self.wire_table.setColumnCount(4)
        self.wire_table.setHorizontalHeaderLabels(["Wire ID", "Signal Name", "Gauge (mm²)", "Outer Diameter (mm)"])
        self.wire_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only table, edited via dialog
        self.wire_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        self._populate_wire_table()
        self.wire_table.itemDoubleClicked.connect(self._on_wire_double_clicked)

        wires_layout.addWidget(self.wire_table)
        layout.addWidget(wires_group)

        # Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.save_data)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def save_data(self):
        text = self.override_input.text().strip()
        if not text:
            self.bundle_data.pop("override_diameter_mm", None)
        else:
            try:
                self.bundle_data["override_diameter_mm"] = float(text)
            except ValueError:
                pass
                
        # Ensure project state is saved on exit
        if self.project_model and hasattr(self.project_model, "data"):
            DatabaseManager.save_project(self.project_model.data)
            
        self.accept()
    def _populate_wire_table(self):
        wires = HarnessCalculator.get_wires_in_bundle(self.bundle_data, self.project_model.data)
        
        self.wire_table.setRowCount(len(wires))
        for row, w in enumerate(wires):
            id_item = QTableWidgetItem(w.get("wire_id", ""))
            sig_item = QTableWidgetItem(w.get("signal_name", ""))
            gauge_item = QTableWidgetItem(str(w.get("gauge", "")))
            od_item = QTableWidgetItem(str(w.get("outer_diameter_mm", "")))
            
            # Store wire reference on the ID item for easy lookup
            id_item.setData(Qt.UserRole, w)

            self.wire_table.setItem(row, 0, id_item)
            self.wire_table.setItem(row, 1, sig_item)
            self.wire_table.setItem(row, 2, gauge_item)
            self.wire_table.setItem(row, 3, od_item)

    def _refresh_calculations(self):
        """Recalculates bundle diameter and updates summary labels."""
        wires = HarnessCalculator.get_wires_in_bundle(self.bundle_data, self.project_model.data)
        calc_od, method_str, status_msg = HarnessCalculator.calculate_bundle_diameter(self.bundle_data, wires)

        self.method_label.setText(method_str)
        self.calc_val_label.setText(f"{calc_od:.2f} mm" if calc_od else "Not calculated")
        self.status_label.setText(status_msg)

    def _on_wire_double_clicked(self, item):
        """Opens the standard WirePropertiesDialog and explicitly syncs updates back to the project model."""
        row = item.row()
        id_item = self.wire_table.item(row, 0)
        if not id_item:
            return
            
        wire_ref = id_item.data(Qt.UserRole)
        if not wire_ref:
            return

        # Open the standard WirePropertiesDialog
        dialog = WirePropertiesDialog(wire_ref, self.project_model,self.undo_stack,self.parent_window.main_window.wires_tab.refresh_wires, self)
        if dialog.exec_() == QDialog.Accepted:
            # Explicitly retrieve updated wire data from dialog and sync to master project model
            updated_wire = getattr(dialog, "wire_data", None)
            if updated_wire and self.project_model and hasattr(self.project_model, "data"):
                wire_id = updated_wire.get("wire_id")
                wires = self.project_model.data.setdefault("wires", [])
                
                # Find and replace in the master project wires list
                for i, w in enumerate(wires):
                    if w.get("wire_id") == wire_id:
                        wires[i] = updated_wire
                        break

            # Refresh table view and recalculate bundle diameter
            self._populate_wire_table()
            self._refresh_calculations()
            
            # Persist changes to database / project file
            if self.project_model and hasattr(self.project_model, "data"):
                DatabaseManager.save_project(self.project_model.data)