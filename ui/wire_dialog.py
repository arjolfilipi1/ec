from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QLabel, QGroupBox, QHBoxLayout, QComboBox, QPushButton, QInputDialog
)
from PyQt5.QtCore import Qt
from database import DatabaseManager

class WirePropertiesDialog(QDialog):
    """Properties editor dialog with support for dual-color (Base / Stripe) wire designations."""
    
    def __init__(self, wire_data: dict, project_model=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Wire Properties - {wire_data.get('wire_id', 'Wire')}")
        self.resize(480, 460)
        
        self.wire_data = wire_data
        self.project_model = project_model
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Wire ID & Signal
        self.id_input = QLineEdit(self.wire_data.get("wire_id", ""))
        form_layout.addRow("Wire ID:", self.id_input)

        self.signal_input = QLineEdit(self.wire_data.get("signal_name", ""))
        form_layout.addRow("Signal Name:", self.signal_input)

        # --- Color Selection (Base & Stripe) ---
        color_group = QGroupBox("Wire Insulation Colors")
        color_form = QFormLayout(color_group)

        # Base Color ComboBox
        base_layout = QHBoxLayout()
        self.base_color_combo = QComboBox()
        self.add_color_btn = QPushButton("Add Color...")
        self.add_color_btn.clicked.connect(self._prompt_add_color)
        base_layout.addWidget(self.base_color_combo)
        base_layout.addWidget(self.add_color_btn)
        color_form.addRow("Base Color:", base_layout)

        # Stripe / Secondary Color ComboBox (Optional)
        self.stripe_color_combo = QComboBox()
        color_form.addRow("Stripe Color:", self.stripe_color_combo)

        layout.addWidget(color_group)
        self._populate_colors()

        # Gauge & Extra Length
        self.gauge_input = QLineEdit(str(self.wire_data.get("gauge", "0.5")))
        form_layout.addRow("Cross-Section (mm²):", self.gauge_input)

        self.extra_len_input = QLineEdit(str(self.wire_data.get("extra_length_mm", 0.0)))
        form_layout.addRow("Extra Length Allowance (mm):", self.extra_len_input)

        layout.addLayout(form_layout)
        # ... [endpoints configuration code remains the same] ...

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.save_data)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_colors(self):
        """Populates base and stripe color combo boxes from the database."""
        self.base_color_combo.clear()
        self.stripe_color_combo.clear()
        
        # Add 'None' option for stripe
        self.stripe_color_combo.addItem("-- None (Single Color) --", "")

        colors = DatabaseManager.get_colors()
        
        current_base = self.wire_data.get("color", "BK").upper()
        current_stripe = self.wire_data.get("stripe_color", "").upper()
        
        base_idx = 0
        stripe_idx = 0

        for idx, col in enumerate(colors):
            display_text = f"{col['name']} ({col['code']})"
            self.base_color_combo.addItem(display_text, col['code'])
            self.stripe_color_combo.addItem(display_text, col['code'])
            
            if col['code'] == current_base:
                base_idx = idx
            if col['code'] == current_stripe:
                stripe_idx = idx + 1 # Offset by 1 because of '-- None --'

        self.base_color_combo.setCurrentIndex(base_idx)
        self.stripe_color_combo.setCurrentIndex(stripe_idx)

    def _prompt_add_color(self):
        code, ok1 = QInputDialog.getText(self, "New Color Code", "Enter short code (e.g., OG for Orange):")
        if not ok1 or not code.strip():
            return
        name, ok2 = QInputDialog.getText(self, "Color Name", "Enter descriptive name (e.g., Orange):")
        if not ok2 or not name.strip():
            return

        DatabaseManager.add_color(code.strip(), name.strip(), "#D35400")
        self._populate_colors()

    def save_data(self):
        """Saves base color, stripe color, and attributes back to wire data."""
        self.wire_data["wire_id"] = self.id_input.text().strip()
        self.wire_data["signal_name"] = self.signal_input.text().strip()
        self.wire_data["color"] = self.base_color_combo.currentData()
        self.wire_data["stripe_color"] = self.stripe_color_combo.currentData() # E.g. "BK" or ""
        
        try:
            self.wire_data["gauge"] = float(self.gauge_input.text())
        except ValueError:
            self.wire_data["gauge"] = 0.5

        try:
            self.wire_data["extra_length_mm"] = float(self.extra_len_input.text())
        except ValueError:
            self.wire_data["extra_length_mm"] = 0.0

        self.accept()