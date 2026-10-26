from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QLabel, QGroupBox, QHBoxLayout, QComboBox, QPushButton
)
from PyQt5.QtCore import Qt
from database import DatabaseManager

class AddWireDialog(QDialog):
    """Unified single window dialog for adding a new wire with master library auto-fill and dynamic pin population."""
    
    def __init__(self, project_model=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Wire")
        self.resize(500, 580)
        
        self.project_model = project_model
        self.wire_data = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 1. Identification Group
        id_group = QGroupBox("Wire Identification")
        id_form = QFormLayout(id_group)
        
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("e.g., W101")
        id_form.addRow("Wire ID:", self.id_input)

        self.signal_input = QLineEdit()
        self.signal_input.setPlaceholderText("e.g., GND_MAIN")
        id_form.addRow("Signal Name:", self.signal_input)
        
        layout.addWidget(id_group)

        # 2. Specifications & Master Library Group
        spec_group = QGroupBox("Technical Specifications & Colors")
        spec_form = QFormLayout(spec_group)

        self.master_wire_combo = QComboBox()
        self._populate_master_wires()
        self.master_wire_combo.currentIndexChanged.connect(self._on_master_wire_changed)
        spec_form.addRow("Master Spec:", self.master_wire_combo)

        self.gauge_input = QLineEdit("0.5")
        spec_form.addRow("Cross-Section (mm²):", self.gauge_input)

        self.od_input = QLineEdit("1.6")
        spec_form.addRow("Outer Diameter (mm):", self.od_input)

        self.base_color_combo = QComboBox()
        self.stripe_color_combo = QComboBox()
        spec_form.addRow("Base Color:", self.base_color_combo)
        spec_form.addRow("Stripe Color:", self.stripe_color_combo)
        self._populate_colors()

        self.ext_len_input = QLineEdit("0.0")
        spec_form.addRow("Extra Length Allowance (mm):", self.ext_len_input)

        layout.addWidget(spec_group)

        # 3. Endpoints & Dynamic Pin Population Group
        endpoint_group = QGroupBox("Endpoints & Pin Designations")
        endpoint_form = QFormLayout(endpoint_group)

        # Start Node & Pin ComboBox (Editable for custom pins)
        start_layout = QHBoxLayout()
        self.start_combo = QComboBox()
        self.start_pin_combo = QComboBox()
        self.start_pin_combo.setEditable(True)
        self.start_pin_combo.setPlaceholderText("Pin")
        self.start_pin_combo.setMaximumWidth(100)
        start_layout.addWidget(self.start_combo, stretch=3)
        start_layout.addWidget(QLabel("Pin:"))
        start_layout.addWidget(self.start_pin_combo, stretch=1)

        # End Node & Pin ComboBox (Editable for custom pins)
        end_layout = QHBoxLayout()
        self.end_combo = QComboBox()
        self.end_pin_combo = QComboBox()
        self.end_pin_combo.setEditable(True)
        self.end_pin_combo.setPlaceholderText("Pin")
        self.end_pin_combo.setMaximumWidth(100)
        end_layout.addWidget(self.end_combo, stretch=3)
        end_layout.addWidget(QLabel("Pin:"))
        end_layout.addWidget(self.end_pin_combo, stretch=1)

        self._populate_endpoints()

        # Connect change signals to dynamically populate pins
        self.start_combo.currentIndexChanged.connect(self._on_start_node_changed)
        self.end_combo.currentIndexChanged.connect(self._on_end_node_changed)

        endpoint_form.addRow("Start Node:", start_layout)
        endpoint_form.addRow("End Node:", end_layout)

        layout.addWidget(endpoint_group)

        # Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_master_wires(self):
        self.master_wire_combo.clear()
        self.master_wire_combo.addItem("-- Custom Spec --", None)
        
        master_wires = DatabaseManager.get_master_wires()
        for mw in master_wires:
            display = f"{mw['part_number']} ({mw['gauge_mm2']} mm², OD: {mw['outer_diameter_mm']}mm)"
            self.master_wire_combo.addItem(display, mw)

    def _populate_colors(self):
        self.base_color_combo.clear()
        self.stripe_color_combo.clear()
        self.stripe_color_combo.addItem("-- None (Single Color) --", "")

        colors = DatabaseManager.get_colors()
        for col in colors:
            display_text = f"{col['name']} ({col['code']})"
            self.base_color_combo.addItem(display_text, col['code'])
            self.stripe_color_combo.addItem(display_text, col['code'])

    def _populate_endpoints(self):
        self.start_combo.clear()
        self.end_combo.clear()
        
        if not self.project_model or not self.project_model.data:
            self.start_combo.addItem("-- No Nodes --", "")
            self.end_combo.addItem("-- No Nodes --", "")
            return

        nodes = self.project_model.data.get("nodes", [])
        for node in nodes:
            node_id = node.get("node_id", "")
            comp_pn = node.get("component_part_number", "Unassigned")
            display = f"{node_id}"
            self.start_combo.addItem(display, node_id)
            self.end_combo.addItem(display, node_id)

        # Trigger initial pin population
        self._on_start_node_changed()
        self._on_end_node_changed()

    def _on_start_node_changed(self):
        node_id = self.start_combo.currentData()
        self.start_pin_combo.clear()
        pins = self._get_pins_for_node(node_id)
        for p in pins:
            self.start_pin_combo.addItem(str(p))

    def _on_end_node_changed(self):
        node_id = self.end_combo.currentData()
        self.end_pin_combo.clear()
        pins = self._get_pins_for_node(node_id)
        for p in pins:
            self.end_pin_combo.addItem(str(p))

    def _get_pins_for_node(self, node_id) -> list:
        """Robustly extracts cavity/pin identifiers across different dictionary key formats."""
        if not self.project_model or not self.project_model.data:
            return []
            
        nodes = self.project_model.data.get("nodes", [])
        for n in nodes:
            if n.get("node_id") == node_id:
                cavities = n.get("cavities", n.get("pins", []))
                extracted = []
                for c in cavities:
                    if isinstance(c, dict):
                        # Check all common naming conventions for cavity/pin keys
                        val = (
                            c.get("cavity_id") or 
                            c.get("cavity") or 
                            c.get("pin") or 
                            c.get("id") or 
                            c.get("name")
                        )
                    else:
                        val = c
                        
                    if val is not None:
                        extracted.append(str(val))
                        
                if extracted:
                    return extracted
                    
                # Default fallback range if no explicit cavities are defined on the node
                return [str(i) for i in range(1, 9)]
                
        return [str(i) for i in range(1, 9)]


    def _on_master_wire_changed(self, index):
        mw = self.master_wire_combo.currentData()
        if mw:
            self.gauge_input.setText(str(mw.get("gauge_mm2", 0.5)))
            self.od_input.setText(str(mw.get("outer_diameter_mm", 1.6)))

    
    def validate_and_accept(self):
        wire_id = self.id_input.text().strip()
        if not wire_id:
            return
            
        try:
            gauge = float(self.gauge_input.text())
        except ValueError:
            gauge = 0.5

        try:
            od = float(self.od_input.text())
        except ValueError:
            od = 1.6

        try:
            extra_len = float(self.ext_len_input.text())
        except ValueError:
            extra_len = 0.0

        base_code = self.base_color_combo.currentData() or "BK"
        stripe_code = self.stripe_color_combo.currentData() or ""

        # Collect endpoints using the correct "cavity_id" key
        endpoints = []
        start_node = self.start_combo.currentData()
        start_pin = self.start_pin_combo.currentText().strip()
        if start_node:
            endpoints.append({"node_id": start_node, "cavity_id": start_pin})

        end_node = self.end_combo.currentData()
        end_pin = self.end_pin_combo.currentText().strip()
        if end_node:
            endpoints.append({"node_id": end_node, "cavity_id": end_pin})

        self.wire_data = {
            "wire_id": wire_id,
            "signal_name": self.signal_input.text().strip(),
            "gauge": gauge,
            "outer_diameter_mm": od,
            "color": base_code,
            "stripe_color": stripe_code,
            "wire_part_number": f"WIRE-{gauge}-{base_code}",
            "extra_length_mm": extra_len,
            "endpoints": endpoints
        }
        self.accept()
class WirePropertiesDialog(QDialog):
    """Dialog for editing an existing wire's properties."""
    
    def __init__(self, wire_data: dict, project_model=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Wire Properties - {wire_data.get('wire_id', 'Wire')}")
        self.resize(450, 400)
        
        self.wire_data = wire_data
        self.project_model = project_model
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.id_input = QLineEdit(self.wire_data.get("wire_id", ""))
        form_layout.addRow("Wire ID:", self.id_input)

        self.signal_input = QLineEdit(self.wire_data.get("signal_name", ""))
        form_layout.addRow("Signal Name:", self.signal_input)

        # Gauge & Outer Diameter
        self.gauge_input = QLineEdit(str(self.wire_data.get("gauge", 0.5)))
        form_layout.addRow("Cross-Section (mm²):", self.gauge_input)

        self.od_input = QLineEdit(str(self.wire_data.get("outer_diameter_mm", 1.6)))
        form_layout.addRow("Outer Diameter (mm):", self.od_input)  # <--- Added OD field

        # Color Combos
        self.base_color_combo = QComboBox()
        self.stripe_color_combo = QComboBox()
        self.stripe_color_combo.addItem("-- None --", "")
        
        colors = DatabaseManager.get_colors()
        for col in colors:
            display = f"{col['name']} ({col['code']})"
            self.base_color_combo.addItem(display, col['code'])
            self.stripe_color_combo.addItem(display, col['code'])

        # Set current colors
        curr_color = self.wire_data.get("color", "BK")
        curr_stripe = self.wire_data.get("stripe_color", "")
        
        for i in range(self.base_color_combo.count()):
            if self.base_color_combo.itemData(i) == curr_color:
                self.base_color_combo.setCurrentIndex(i)
                break
                
        for i in range(self.stripe_color_combo.count()):
            if self.stripe_color_combo.itemData(i) == curr_stripe:
                self.stripe_color_combo.setCurrentIndex(i)
                break

        form_layout.addRow("Base Color:", self.base_color_combo)
        form_layout.addRow("Stripe Color:", self.stripe_color_combo)

        # Extra Length
        self.ext_len_input = QLineEdit(str(self.wire_data.get("extra_length_mm", 0.0)))
        form_layout.addRow("Extra Length (mm):", self.ext_len_input)

        layout.addLayout(form_layout)

        # Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.save_data)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_data(self):
        self.wire_data["wire_id"] = self.id_input.text().strip()
        self.wire_data["signal_name"] = self.signal_input.text().strip()
        self.wire_data["color"] = self.base_color_combo.currentData() or "BK"
        self.wire_data["stripe_color"] = self.stripe_color_combo.currentData() or ""
        
        try:
            self.wire_data["gauge"] = float(self.gauge_input.text())
        except ValueError:
            pass

        try:
            self.wire_data["outer_diameter_mm"] = float(self.od_input.text())
        except ValueError:
            pass

        try:
            self.wire_data["extra_length_mm"] = float(self.ext_len_input.text())
        except ValueError:
            pass
            
        self.accept()