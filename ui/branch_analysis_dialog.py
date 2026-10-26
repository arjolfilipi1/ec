from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QLabel, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from database import DatabaseManager
from models.harness_calculations import HarnessCalculator
from ui.bundle_calculation_dialog import BundleCalculationDialog

class BranchAnalysisDialog(QDialog):
    """Engineering analysis window listing all branches, diameters, coverings, and fit status."""
    
    def __init__(self, project_model, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Branch & Covering Analysis (Edit Diameters)")
        self.resize(950, 520)
        
        self.project_model = project_model
        self._init_ui()
        self._load_branch_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header_label = QLabel("<b>Harness Branch & Diameter Review</b><br>Double-click any bundle row to inspect calculation methods or set manual overrides.")
        layout.addWidget(header_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Bundle ID", "Nodes", "Length (mm)", 
            "Bundle OD (mm)", "Overall OD (mm)", "Coverings", "Fit Status / Warnings"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Recalculate & Refresh")
        self.refresh_btn.clicked.connect(self._load_branch_data)
        btn_layout.addWidget(self.refresh_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_branch_data(self):
        self.table.setRowCount(0)
        if not self.project_model:
            return

        data = self.project_model.data
        bundles = data.get("bundles", [])
        master_coverings = {c['part_number']: c for c in DatabaseManager.get_coverings()}

        self.table.setRowCount(len(bundles))

        for row, bundle in enumerate(bundles):
            b_id = bundle.get("bundle_id", "")
            s_node = bundle.get("start_node_id", "")
            e_node = bundle.get("end_node_id", "")
            length = bundle.get("length_mm", 0.0)

            # Calculate Bundle OD using methods 1-4
            wires = HarnessCalculator.get_wires_in_bundle(bundle, data)
            bundle_od, method_str, status_msg = HarnessCalculator.calculate_bundle_diameter(bundle, wires)

            # Calculate Overall OD over coverings
            coverings = bundle.get("coverings", [])
            overall_od = HarnessCalculator.calculate_overall_diameter(bundle_od, coverings)

            # Evaluate Covering Fit
            fit_status = "PASS"
            is_warning = False
            current_inside_od = bundle_od
            
            cov_names = []
            for cov in coverings:
                p_num = cov.get("part_number", "")
                cov_names.append(p_num)
                master_info = master_coverings.get(p_num, {})
                # Merge master specs into evaluation copy
                eval_cov = {**master_info, **cov}
                
                status, warning_flag = HarnessCalculator.evaluate_covering_fit(current_inside_od, eval_cov)
                if warning_flag:
                    fit_status = status
                    is_warning = True
                
                # Update inside OD for next nested covering layer
                wall = eval_cov.get("wall_thickness_mm", 0.0)
                current_inside_od += (wall * 2.0)

            if not coverings:
                fit_status = "No Covering"

            # Populate Table Items
            self.table.setItem(row, 0, QTableWidgetItem(b_id))
            self.table.setItem(row, 1, QTableWidgetItem(f"{s_node} -> {e_node}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{length:.1f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{bundle_od:.2f}" if bundle_od else "Not calculated"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{overall_od:.2f}" if overall_od else "Not calculated"))
            self.table.setItem(row, 5, QTableWidgetItem(", ".join(cov_names) if cov_names else "None"))
            
            status_item = QTableWidgetItem(fit_status if not is_warning else f"⚠️ {fit_status}")
            if is_warning or "WARNING" in status_msg:
                status_item.setForeground(QColor(192, 57, 43))
            self.table.setItem(row, 6, status_item)

            # Store bundle reference on row for double-click editing
            self.table.item(row, 0).setData(Qt.UserRole, bundle)

    def _on_row_double_clicked(self, index):
        row = index.row()
        bundle = self.table.item(row, 0).data(Qt.UserRole)
        if bundle:
            undo_stack = getattr(self.parent(), "undo_stack", None)
            dialog = BundleCalculationDialog(bundle, self.project_model, undo_stack=undo_stack, parent=self)
            if dialog.exec_() == QDialog.Accepted:
                self._load_branch_data()