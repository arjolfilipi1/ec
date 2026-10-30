from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QPushButton, QGroupBox, QFormLayout, QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt
from models.harness_model import HarnessProjectModel

class WireRoutingManagerDialog(QDialog):
    """Interactive manager for inspecting, recomputing, and editing wire routing paths."""
    
    def __init__(self, project_model: HarnessProjectModel, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Interactive Wire Routing & Pathfinding Manager")
        self.resize(700, 450)
        
        self.project_model = project_model
        self.current_wire = None
        self._init_ui()
        self._load_wires()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # Left panel: Wire List
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Project Wires:"))
        self.wire_list_widget = QListWidget()
        self.wire_list_widget.currentRowChanged.connect(self._on_wire_selected)
        left_layout.addWidget(self.wire_list_widget)
        main_layout.addLayout(left_layout, 1)
        
        # Right panel: Wire Routing Details
        right_layout = QVBoxLayout()
        
        details_group = QGroupBox("Wire Route & Endpoint Details")
        form_layout = QFormLayout(details_group)
        
        self.wire_id_lbl = QLabel("")
        form_layout.addRow("Wire ID:", self.wire_id_lbl)
        
        self.signal_input = QLineEdit()
        form_layout.addRow("Signal Name:", self.signal_input)
        
        self.endpoints_lbl = QLabel("")
        form_layout.addRow("Endpoints:", self.endpoints_lbl)
        
        self.path_text_edit = QTextEdit()
        self.path_text_edit.setPlaceholderText("Comma-separated bundle IDs representing routed path")
        form_layout.addRow("Routed Bundles:", self.path_text_edit)
        
        right_layout.addWidget(details_group)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.recompute_btn = QPushButton("Recompute Path (BFS)")
        self.recompute_btn.clicked.connect(self._recompute_path)
        btn_layout.addWidget(self.recompute_btn)
        
        self.save_btn = QPushButton("Apply Changes")
        self.save_btn.clicked.connect(self._save_current_wire)
        btn_layout.addWidget(self.save_btn)
        
        right_layout.addLayout(btn_layout)
        main_layout.addLayout(right_layout, 2)

    def _load_wires(self):
        self.wire_list_widget.clear()
        for wire in self.main_window.current_project.data.get("wires", []):
            w_id = wire.get("wire_id", "Unknown")
            sig = wire.get("signal_name", "")
            item_text = f"{w_id} ({sig})" if sig else w_id
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, wire)
            self.wire_list_widget.addItem(item)
            
        if self.wire_list_widget.count() > 0:
            self.wire_list_widget.setCurrentRow(0)

    def _on_wire_selected(self, row):
        if row < 0:
            return
        item = self.wire_list_widget.item(row)
        if item:
            wire = item.data(Qt.UserRole)
            self.current_wire = wire
            
            self.wire_id_lbl.setText(wire.get("wire_id", ""))
            self.signal_input.setText(wire.get("signal_name", ""))
            
            endpoints = wire.get("endpoints", [])
            ep_str = ", ".join([f"{ep.get('node_id')} (Cavity: {ep.get('cavity_id', ep.get('pin_id'))})" for ep in endpoints])
            self.endpoints_lbl.setText(ep_str if ep_str else "None")
            
            routed_bundles = wire.get("routed_bundle_ids", [])
            self.path_text_edit.setText(", ".join(routed_bundles))

    def _recompute_path(self):
        """Recomputes bundle path using BFS; falls back to generating a path if disconnected."""
        if not self.current_wire:
            return
            
        endpoints = self.current_wire.get("endpoints", [])
        if len(endpoints) < 2:
            QMessageBox.warning(self, "Pathfinding Warning", "Wire requires at least 2 endpoints to compute a path.")
            return
            
        start_node = endpoints[0].get("node_id")
        end_node = endpoints[1].get("node_id")
        
        # 1. Attempt standard BFS continuous path search
        path = self.main_window.current_project.find_bundle_path(start_node, end_node)
        
        if path:
            self.path_text_edit.setText(", ".join(path))
            self.current_wire["routed_bundle_ids"] = path
            QMessageBox.information(self, "Pathfinder Success", f"Successfully computed continuous path: {', '.join(path)}")
        else:
            # 2. Fallback: Find all bundles connected to start and end nodes to construct a path
            start_bundles = [b["bundle_id"] for b in self.main_window.current_project.data.get("bundles", []) 
                             if b.get("start_node_id") == start_node or b.get("end_node_id") == start_node]
            end_bundles = [b["bundle_id"] for b in self.main_window.current_project.data.get("bundles", []) 
                           if b.get("start_node_id") == end_node or b.get("end_node_id") == end_node]
            
            # Combine unique candidate bundles connecting start and end regions
            fallback_path = list(dict.fromkeys(start_bundles + end_bundles))
            
            if not fallback_path:
                # If no bundles touch either node, select all project bundles as default candidate path
                fallback_path = [b["bundle_id"] for b in self.main_window.current_project.data.get("bundles", [])]

            self.path_text_edit.setText(", ".join(fallback_path))
            self.current_wire["routed_bundle_ids"] = fallback_path
            
            # Show a soft warning message instead of a hard error
            QMessageBox.warning(
                self, 
                "Pathfinding Warning", 
                f"No fully continuous bundle path exists between '{start_node}' and '{end_node}'.\n\n"
                f"A candidate route ({', '.join(fallback_path)}) has been generated and assigned automatically."
            )

    def _save_current_wire(self):
        if not self.current_wire:
            return
            
        self.current_wire["signal_name"] = self.signal_input.text().strip()
        
        path_text = self.path_text_edit.toPlainText()
        bundles = [b.strip() for b in path_text.split(",") if b.strip()]
        self.current_wire["routed_bundle_ids"] = bundles
        
        self.accept()