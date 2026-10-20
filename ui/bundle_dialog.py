from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTableWidget, QTableWidgetItem, QDialogButtonBox, QComboBox, QGroupBox, QFormLayout
)
from PyQt5.QtCore import Qt

class BundlePropertiesDialog(QDialog):
    """Properties editor dialog for configuring bundle lengths, shielding, and protective coverings."""
    
    def __init__(self, bundle_data: dict, parent=None):
        super().__init__(parent)
        print("props")
        self.setWindowTitle(f"Bundle Properties - {bundle_data.get('bundle_id')}")
        self.resize(500, 400)
        
        self.bundle_data = bundle_data
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Form layout for basic attributes
        form_layout = QFormLayout()
        
        self.id_input = QLineEdit(self.bundle_data.get("bundle_id", ""))
        self.id_input.setReadOnly(True)
        form_layout.addRow("Bundle ID:", self.id_input)

        self.length_input = QLineEdit(str(self.bundle_data.get("length_mm", 0.0)))
        form_layout.addRow("Length Override (mm):", self.length_input)

        layout.addLayout(form_layout)

        # Protective Coverings Group (Corrugated tubing, braided sleeving, tape)[cite: 1]
        covering_group = QGroupBox("Outer Protective Coverings")
        cov_layout = QVBoxLayout(covering_group)

        self.covering_table = QTableWidget()
        self.covering_table.setColumnCount(4)
        self.covering_table.setHorizontalHeaderLabels(["Type", "Part Number", "Start Offset (mm)", "End Offset (mm)"])
        
        coverings = self.bundle_data.get("coverings", [])
        self.covering_table.setRowCount(len(coverings))
        
        for row, cov in enumerate(coverings):
            self.covering_table.setItem(row, 0, QTableWidgetItem(cov.get("covering_type", "CORRUGATED_TUBING")))
            self.covering_table.setItem(row, 1, QTableWidgetItem(cov.get("covering_part_number", "")))
            self.covering_table.setItem(row, 2, QTableWidgetItem(str(cov.get("start_offset_mm", 0))))
            self.covering_table.setItem(row, 3, QTableWidgetItem(str(cov.get("end_offset_mm", 0))))

        cov_layout.addWidget(self.covering_table)
        layout.addWidget(covering_group)

        # Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.save_data)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_data(self):
        """Saves modifications back into the bundle dictionary structure."""
        try:
            self.bundle_data["length_mm"] = float(self.length_input.text())
            print("lenght updated")
        except ValueError:
            print("conv failed")
            self.bundle_data["length_mm"] = 0.0

        updated_coverings = []
        for row in range(self.covering_table.rowCount()):
            cov_type_item = self.covering_table.item(row, 0)
            part_item = self.covering_table.item(row, 1)
            start_item = self.covering_table.item(row, 2)
            end_item = self.covering_table.item(row, 3)

            if part_item and part_item.text().strip():
                updated_coverings.append({
                    "covering_type": cov_type_item.text() if cov_type_item else "CORRUGATED_TUBING",
                    "covering_part_number": part_item.text().strip(),
                    "start_offset_mm": float(start_item.text()) if start_item and start_item.text().isdigit() else 0.0,
                    "end_offset_mm": float(end_item.text()) if end_item and end_item.text().isdigit() else 0.0
                })

        self.bundle_data["coverings"] = updated_coverings
        self.accept()