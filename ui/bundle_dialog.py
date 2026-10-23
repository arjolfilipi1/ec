from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTableWidget, QTableWidgetItem, QDialogButtonBox, QGroupBox, QFormLayout, QPushButton, QComboBox,QInputDialog
)
from PyQt5.QtCore import Qt
from database import DatabaseManager

class BundlePropertiesDialog(QDialog):
    """Properties and covering manager dialog for harness bundles."""
    
    def __init__(self, bundle_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Bundle Properties - {bundle_data.get('bundle_id', 'Bundle')}")
        self.resize(520, 420)
        
        self.bundle_data = bundle_data
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.id_input = QLineEdit(self.bundle_data.get("bundle_id", ""))
        self.id_input.setReadOnly(True)
        form_layout.addRow("Bundle ID:", self.id_input)

        self.len_input = QLineEdit(str(self.bundle_data.get("length_mm", 0.0)))
        form_layout.addRow("Calculated Length (mm):", self.len_input)

        layout.addLayout(form_layout)

        # Coverings Assignment Group
        cov_group = QGroupBox("Applied Protective Coverings (Sleeving / Tubing)")
        cov_layout = QVBoxLayout(cov_group)

        self.cov_table = QTableWidget()
        self.cov_table.setColumnCount(3)
        self.cov_table.setHorizontalHeaderLabels(["Part Number", "Description", "Coverage Span"])
        
        self._populate_covering_table()
        cov_layout.addWidget(self.cov_table)

        btn_row = QHBoxLayout()
        self.add_cov_btn = QPushButton("Add Covering...")
        self.add_cov_btn.clicked.connect(self._add_covering_row)
        btn_row.addWidget(self.add_cov_btn)

        self.del_cov_btn = QPushButton("Remove Selected")
        self.del_cov_btn.clicked.connect(self._del_covering_row)
        btn_row.addWidget(self.del_cov_btn)

        cov_layout.addLayout(btn_row)
        layout.addWidget(cov_group)

        # Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.save_data)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_covering_table(self):
        coverings = self.bundle_data.get("coverings", [])
        master_coverings = {c['part_number']: c for c in DatabaseManager.get_coverings()}
        
        self.cov_table.setRowCount(len(coverings))
        for row, cov in enumerate(coverings):
            p_num = cov.get("part_number", "")
            master_info = master_coverings.get(p_num, {})
            desc = master_info.get("description", "Custom Covering")
            
            self.cov_table.setItem(row, 0, QTableWidgetItem(p_num))
            self.cov_table.setItem(row, 1, QTableWidgetItem(desc))
            self.cov_table.setItem(row, 2, QTableWidgetItem(f"{int(cov.get('start_ratio', 0.0)*100)}% - {int(cov.get('end_ratio', 1.0)*100)}%"))

    def _add_covering_row(self):
        master_coverings = DatabaseManager.get_coverings()
        if not master_coverings:
            return
            
        part_nums = [c['part_number'] for c in master_coverings]
        part_num, ok = QInputDialog.getItem(self, "Select Covering", "Master Part Number:", part_nums, 0, False)
        
        if ok and part_num:
            row = self.cov_table.rowCount()
            self.cov_table.insertRow(row)
            self.cov_table.setItem(row, 0, QTableWidgetItem(part_num))
            self.cov_table.setItem(row, 1, QTableWidgetItem("Sleeving / Tubing"))
            self.cov_table.setItem(row, 2, QTableWidgetItem("0% - 100%"))

    def _del_covering_row(self):
        selected_rows = set(item.row() for item in self.cov_table.selectedItems())
        for row in sorted(selected_rows, reverse=True):
            self.cov_table.removeRow(row)

    def save_data(self):
        try:
            self.bundle_data["length_mm"] = float(self.len_input.text())
        except ValueError:
            pass

        updated_coverings = []
        for row in range(self.cov_table.rowCount()):
            p_item = self.cov_table.item(row, 0)
            if p_item and p_item.text().strip():
                updated_coverings.append({
                    "part_number": p_item.text().strip(),
                    "start_ratio": 0.0,
                    "end_ratio": 1.0
                })
        
        self.bundle_data["coverings"] = updated_coverings
        self.accept()