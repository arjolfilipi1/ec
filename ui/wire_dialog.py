from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QLabel
)
from PyQt5.QtCore import Qt

class WirePropertiesDialog(QDialog):
    """Properties editor dialog for configuring individual wire names, colors, gauges, and attributes."""
    
    def __init__(self, wire_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Wire Properties - {wire_data.get('wire_id', 'Wire')}")
        self.resize(420, 320)
        
        self.wire_data = wire_data
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Wire ID / Unique Identifier
        self.id_input = QLineEdit(self.wire_data.get("wire_id", ""))
        form_layout.addRow("Wire ID:", self.id_input)

        # Signal Name
        self.signal_input = QLineEdit(self.wire_data.get("signal_name", ""))
        form_layout.addRow("Signal Name:", self.signal_input)

        # Color Code
        self.color_input = QLineEdit(self.wire_data.get("color", "BK"))
        form_layout.addRow("Color Code (e.g., BK, RD):", self.color_input)

        # Gauge / Cross-Section
        self.gauge_input = QLineEdit(str(self.wire_data.get("gauge", "0.5")))
        form_layout.addRow("Cross-Section (mm²):", self.gauge_input)

        # Extra Length Allowance
        self.extra_len_input = QLineEdit(str(self.wire_data.get("extra_length_mm", 0.0)))
        form_layout.addRow("Extra Length Allowance (mm):", self.extra_len_input)

        # Endpoints Summary (Read-Only inspection)
        endpoints = self.wire_data.get("endpoints", [])
        ep_summary = ", ".join([f"{ep.get('node_id')}:{ep.get('pin_id') or ep.get('cavity_id', '')}" for ep in endpoints])
        self.endpoints_label = QLabel(ep_summary if ep_summary else "None")
        self.endpoints_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        form_layout.addRow("Endpoints:", self.endpoints_label)

        layout.addLayout(form_layout)

        # Dialog Action Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.save_data)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_data(self):
        """Saves modifications back into the wire dictionary structure."""
        self.wire_data["wire_id"] = self.id_input.text().strip()
        self.wire_data["signal_name"] = self.signal_input.text().strip()
        self.wire_data["color"] = self.color_input.text().strip().upper()
        
        try:
            self.wire_data["gauge"] = float(self.gauge_input.text())
        except ValueError:
            self.wire_data["gauge"] = 0.5

        try:
            self.wire_data["extra_length_mm"] = float(self.extra_len_input.text())
        except ValueError:
            self.wire_data["extra_length_mm"] = 0.0

        self.accept()