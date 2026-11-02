import copy,uuid
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QLabel, QGroupBox, QHBoxLayout, QComboBox, QPushButton, QUndoCommand
)
from PyQt5.QtCore import Qt
from database import DatabaseManager
from collections import deque

class AddWireDialog(QDialog):
    """Unified single window dialog for adding a new wire with master library auto-fill and dynamic pin population."""
    
    def __init__(self, project_model=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Wire")
        self.resize(500, 580)
        self.main_window = parent
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

        endpoints = []
        start_node = self.start_combo.currentData()
        start_pin = self.start_pin_combo.currentText().strip()
        if start_node:
            endpoints.append({"node_id": start_node, "cavity_id": start_pin})

        end_node = self.end_combo.currentData()
        end_pin = self.end_pin_combo.currentText().strip()
        if end_node:
            endpoints.append({"node_id": end_node, "cavity_id": end_pin})

        # --- FIX: Do not change project_model yet. Compute on a temp dummy dialog environment ---
        # Temporarily mock the network topology path calculation using a decoupled context
        original_data = self.project_model.data
        
        # Save structural changes to wire data dictionary instead of modifying project model
        self.wire_data.update({
            "wire_id": wire_id,
            "signal_name": self.signal_input.text().strip(),
            "gauge": gauge,
            "outer_diameter_mm": od,
            "color": base_code,
            "stripe_color": stripe_code,
            "wire_part_number": f"WIRE-{gauge}-{base_code}",
            "extra_length_mm": extra_len,
            "endpoints": endpoints,
            # Pass endpoints to controller so it knows who needs bridging inside the macro undo transaction
            "requires_bridge_nodes": [ep["node_id"] for ep in endpoints] 
        })

        self.accept()
    def _bridge_node_to_network(self, target_node_id: str):
        """Finds the nearest bundle segment, splits it if necessary, and creates a branch bundle to the target node."""
        if not self.project_model or not self.project_model.data:
            return
            
        data = self.project_model.data
        nodes = data.setdefault("nodes", [])
        bundles = data.setdefault("bundles", data.get("branches", []))
        wires = data.setdefault("wires", [])
        
        node_dict = {n.get("node_id"): n for n in nodes}
        target_node = node_dict.get(target_node_id)
        if not target_node or not bundles:
            return

        # Check if the node is already part of the bundle network graph
        connected_nodes = set()
        for b in bundles:
            connected_nodes.add(b.get("start_node_id") or b.get("node_a") or b.get("from_node"))
            connected_nodes.add(b.get("end_node_id") or b.get("node_b") or b.get("to_node"))
        
        # If already linked, no bridging needed
        if target_node_id in connected_nodes:
            return

        # --- FIX 2: Correct nested position dictionary read ---
        pos_2d = target_node.get("position_2d", {})
        nx, ny = pos_2d.get("x", 0.0), pos_2d.get("y", 0.0)

        best_bundle = None
        best_proj = None
        min_dist = float('inf')

        for b in bundles:
            u = b.get("start_node_id") or b.get("node_a") or b.get("from_node")
            v = b.get("end_node_id") or b.get("node_b") or b.get("to_node")
            u_n = node_dict.get(u)
            v_n = node_dict.get(v)
            if not u_n or not v_n:
                continue
                
            u_pos = u_n.get("position_2d", {})
            v_pos = v_n.get("position_2d", {})
            ux, uy = u_pos.get("x", 0.0), u_pos.get("y", 0.0)
            vx, vy = v_pos.get("x", 0.0), v_pos.get("y", 0.0)

            dx, dy = vx - ux, vy - uy
            length_sq = dx*dx + dy*dy
            if length_sq == 0:
                proj_x, proj_y = ux, uy
            else:
                t = max(0.0, min(1.0, ((nx - ux) * dx + (ny - uy) * dy) / length_sq))
                proj_x = ux + t * dx
                proj_y = uy + t * dy

            dist = ((nx - proj_x)**2 + (ny - proj_y)**2)**0.5
            if dist < min_dist:
                min_dist = dist
                best_bundle = b
                best_proj = (proj_x, proj_y, u, v)

        if not best_bundle or not best_proj:
            return

        proj_x, proj_y, u_id, v_id = best_proj
        b_id = best_bundle.get("bundle_id") or best_bundle.get("branch_id") or best_bundle.get("id")

        u_n = node_dict.get(u_id)
        v_n = node_dict.get(v_id)
        tolerance = 2.0 

        u_pos = u_n.get("position_2d", {})
        v_pos = v_n.get("position_2d", {})
        dist_u = ((proj_x - u_pos.get("x", 0))**2 + (proj_y - u_pos.get("y", 0))**2)**0.5
        dist_v = ((proj_x - v_pos.get("x", 0))**2 + (proj_y - v_pos.get("y", 0))**2)**0.5

        if dist_u < tolerance:
            junction_node_id = u_id
        elif dist_v < tolerance:
            junction_node_id = v_id
        else:
            junction_node_id = f"J_{uuid.uuid4().hex[:6]}"
            new_node = {
                "node_id": junction_node_id,
                "position_2d": {"x": proj_x, "y": proj_y},
                "formboard_position_2d": {"x": proj_x, "y": proj_y},
                "component_part_number": "Junction"
            }
            nodes.append(new_node)
            node_dict[junction_node_id] = new_node

            b1_id = f"B_{uuid.uuid4().hex[:6]}"
            b2_id = f"B_{uuid.uuid4().hex[:6]}"
            
            b1 = dict(best_bundle)
            b1["bundle_id"] = b1_id
            b1["start_node_id"] = u_id
            b1["end_node_id"] = junction_node_id
            for k in ["node_a", "node_b", "from_node", "to_node", "branch_id", "id"]:
                b1.pop(k, None)

            b2 = dict(best_bundle)
            b2["bundle_id"] = b2_id
            b2["start_node_id"] = junction_node_id
            b2["end_node_id"] = v_id
            for k in ["node_a", "node_b", "from_node", "to_node", "branch_id", "id"]:
                b2.pop(k, None)

            bundles.remove(best_bundle)
            bundles.extend([b1, b2])

            for w in wires:
                routed = w.get("routed_bundle_ids", [])
                if b_id in routed:
                    idx = routed.index(b_id)
                    routed[idx:idx+1] = [b1_id, b2_id]

        new_bundle_id = f"B_{uuid.uuid4().hex[:6]}"
        new_bundle = {
            "bundle_id": new_bundle_id,
            "start_node_id": junction_node_id,
            "end_node_id": target_node_id,
            "length_mm": round(min_dist, 1)
        }
        bundles.append(new_bundle)
    def _compute_route(self, endpoints: list) -> list:
        """Computes the route through bundles, automatically bridging unlinked nodes to the nearest bundle segment."""
        if len(endpoints) < 2 or not self.project_model or not self.project_model.data:
            return []
            
        start_node_id = endpoints[0].get("node_id")
        end_node_id = endpoints[1].get("node_id")
        
        if not start_node_id or not end_node_id or start_node_id == end_node_id:
            return []

        data = self.project_model.data
        nodes = {n.get("node_id"): n for n in data.get("nodes", [])}
        bundles = data.get("bundles", data.get("branches", []))
        
        if start_node_id not in nodes or end_node_id not in nodes:
            return []

        # 1. Build adjacency graph & bundle mapping
        graph = {}
        bundle_map = {} # bundle_id -> (u, v)
        for b in bundles:
            u = b.get("start_node_id") or b.get("node_a") or b.get("from_node")
            v = b.get("end_node_id") or b.get("node_b") or b.get("to_node")
            b_id = b.get("bundle_id") or b.get("branch_id") or b.get("id")
            if u and v and b_id:
                graph.setdefault(u, []).append((v, b_id))
                graph.setdefault(v, []).append((u, b_id))
                bundle_map[b_id] = (u, v)

        # 2. Helper to find the nearest bundle segment for an isolated node
        def get_nearest_bundle_id(node_id):
            node = nodes.get(node_id)
            if not node or not bundles:
                return None
            nx, ny = node.get("x", 0.0), node.get("y", 0.0)
            
            best_b_id = None
            min_dist = float('inf')
            
            for b in bundles:
                b_id = b.get("bundle_id") or b.get("branch_id") or b.get("id")
                u = b.get("start_node_id") or b.get("node_a") or b.get("from_node")
                v = b.get("end_node_id") or b.get("node_b") or b.get("to_node")
                u_node = nodes.get(u)
                v_node = nodes.get(v)
                if not u_node or not v_node:
                    continue
                ux, uy = u_node.get("x", 0.0), u_node.get("y", 0.0)
                vx, vy = v_node.get("x", 0.0), v_node.get("y", 0.0)
                
                # Point-to-line segment distance calculation
                dx, dy = vx - ux, vy - uy
                length_sq = dx*dx + dy*dy
                if length_sq == 0:
                    dist = ((nx - ux)**2 + (ny - uy)**2)**0.5
                else:
                    t = max(0.0, min(1.0, ((nx - ux) * dx + (ny - uy) * dy) / length_sq))
                    proj_x = ux + t * dx
                    proj_y = uy + t * dy
                    dist = ((nx - proj_x)**2 + (ny - proj_y)**2)**0.5
                
                if dist < min_dist:
                    min_dist = dist
                    best_b_id = b_id
            return best_b_id

        eff_start = start_node_id
        eff_end = end_node_id
        prefix = []
        suffix = []

        # If start node is not in the network graph, bridge to its nearest bundle
        if eff_start not in graph:
            nb_id = get_nearest_bundle_id(eff_start)
            if nb_id:
                prefix.append(nb_id)
                u, v = bundle_map[nb_id]
                u_node, v_node = nodes.get(u), nodes.get(v)
                s_node = nodes.get(eff_start)
                if u_node and v_node and s_node:
                    du = (s_node.get("x",0)-u_node.get("x",0))**2 + (s_node.get("y",0)-u_node.get("y",0))**2
                    dv = (s_node.get("x",0)-v_node.get("x",0))**2 + (s_node.get("y",0)-v_node.get("y",0))**2
                    eff_start = u if du <= dv else v
                else:
                    eff_start = u

        # If end node is not in the network graph, bridge to its nearest bundle
        if eff_end not in graph:
            nb_id = get_nearest_bundle_id(eff_end)
            if nb_id:
                suffix.insert(0, nb_id)
                u, v = bundle_map[nb_id]
                u_node, v_node = nodes.get(u), nodes.get(v)
                e_node = nodes.get(eff_end)
                if u_node and v_node and e_node:
                    du = (e_node.get("x",0)-u_node.get("x",0))**2 + (e_node.get("y",0)-e_node.get("y",0))**2
                    dv = (e_node.get("x",0)-v_node.get("x",0))**2 + (e_node.get("y",0)-v_node.get("y",0))**2
                    eff_end = u if du <= dv else v
                else:
                    eff_end = v

        # Standard BFS Pathfinding between effective nodes
        path = []
        if eff_start == eff_end:
            path = []
        elif eff_start in graph and eff_end in graph:
            queue = deque([[eff_start]])
            visited = {eff_start}
            parent_map = {}

            while queue:
                current = queue.popleft()
                curr = current[-1]

                if curr == eff_end:
                    node = eff_end
                    while node in parent_map:
                        prev, b_id = parent_map[node]
                        path.append(b_id)
                        node = prev
                    path.reverse()
                    break

                for neighbor, b_id in graph.get(curr, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        parent_map[neighbor] = (curr, b_id)
                        queue.append(current + [neighbor])

        # Combine prefix, core path, and suffix without duplicate bundle IDs
        full_route = []
        for b_id in prefix + path + suffix:
            if not full_route or full_route[-1] != b_id:
                full_route.append(b_id)
        return full_route

class EditWireCommand(QUndoCommand):
    """Undoable command for editing wire properties and endpoint routing."""
    
    def __init__(self, project_model, wire_id, old_data, new_data, refresh_callback=None):
        super().__init__(f"Edit Wire: {wire_id}")
        self.project_model = project_model
        self.wire_id = wire_id
        self.old_data = old_data
        self.new_data = new_data
        self.refresh_callback = refresh_callback

    def undo(self):
        self._apply_data(self.old_data)

    def redo(self):
        self._apply_data(self.new_data)

    def _apply_data(self, data_dict):
        if not self.project_model or not hasattr(self.project_model, "data"):
            return
        wires = self.project_model.data.setdefault("wires", [])
        for i, w in enumerate(wires):
            if w.get("wire_id") == self.wire_id:
                wires[i] = copy.deepcopy(data_dict)
                break
        if self.refresh_callback:
            self.refresh_callback()
        DatabaseManager.save_project(self.project_model.data)


class WirePropertiesDialog(QDialog):
    """Dialog for viewing and editing an existing wire with full undo stack support."""
    
    def __init__(self, wire_data: dict, project_model=None, undo_stack=None, refresh_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Wire Properties - {wire_data.get('wire_id', 'Wire')}")
        self.resize(500, 620)
        
        self.wire_data = wire_data
        self.project_model = project_model
        self.undo_stack = undo_stack
        self.refresh_callback = refresh_callback
        
        # Snapshot the original state for undo comparison
        self.old_wire_data = copy.deepcopy(wire_data)
        
        self._init_ui()
        self._load_existing_data()

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
        spec_group = QGroupBox("Technical Specifications & Master Library")
        spec_form = QFormLayout(spec_group)

        self.master_wire_combo = QComboBox()
        self._populate_master_wires()
        self.master_wire_combo.currentIndexChanged.connect(self._on_master_wire_changed)
        spec_form.addRow("Master Spec:", self.master_wire_combo)

        self.gauge_input = QLineEdit()
        spec_form.addRow("Cross-Section (mm²):", self.gauge_input)

        self.od_input = QLineEdit()
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

        start_layout = QHBoxLayout()
        self.start_combo = QComboBox()
        self.start_pin_combo = QComboBox()
        self.start_pin_combo.setEditable(True)
        self.start_pin_combo.setPlaceholderText("Pin")
        self.start_pin_combo.setMaximumWidth(100)
        start_layout.addWidget(self.start_combo, stretch=3)
        start_layout.addWidget(QLabel("Pin:"))
        start_layout.addWidget(self.start_pin_combo, stretch=1)

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
            display = f"Node {node_id} ({comp_pn})"
            self.start_combo.addItem(display, node_id)
            self.end_combo.addItem(display, node_id)

    def _load_existing_data(self):
        self.id_input.setText(self.wire_data.get("wire_id", ""))
        self.signal_input.setText(self.wire_data.get("signal_name", ""))
        self.gauge_input.setText(str(self.wire_data.get("gauge", 0.5)))
        self.od_input.setText(str(self.wire_data.get("outer_diameter_mm", 1.6)))
        self.ext_len_input.setText(str(self.wire_data.get("extra_length_mm", 0.0)))

        color_code = self.wire_data.get("color", "BK")
        for i in range(self.base_color_combo.count()):
            if self.base_color_combo.itemData(i) == color_code:
                self.base_color_combo.setCurrentIndex(i)
                break

        stripe_code = self.wire_data.get("stripe_color", "")
        for i in range(self.stripe_color_combo.count()):
            if self.stripe_color_combo.itemData(i) == stripe_code:
                self.stripe_color_combo.setCurrentIndex(i)
                break

        endpoints = self.wire_data.get("endpoints", [])
        if len(endpoints) > 0:
            start_ep = endpoints[0]
            start_node = start_ep.get("node_id", "")
            start_cavity = str(start_ep.get("cavity_id") or start_ep.get("pin", ""))
            
            for i in range(self.start_combo.count()):
                if self.start_combo.itemData(i) == start_node:
                    self.start_combo.setCurrentIndex(i)
                    break
            self._on_start_node_changed()
            self.start_pin_combo.setEditText(start_cavity)

        if len(endpoints) > 1:
            end_ep = endpoints[1]
            end_node = end_ep.get("node_id", "")
            end_cavity = str(end_ep.get("cavity_id") or end_ep.get("pin", ""))
            
            for i in range(self.end_combo.count()):
                if self.end_combo.itemData(i) == end_node:
                    self.end_combo.setCurrentIndex(i)
                    break
            self._on_end_node_changed()
            self.end_pin_combo.setEditText(end_cavity)

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
        if not self.project_model or not self.project_model.data:
            return []
        nodes = self.project_model.data.get("nodes", [])
        for n in nodes:
            if n.get("node_id") == node_id:
                cavities = n.get("cavities", n.get("pins", []))
                extracted = []
                for c in cavities:
                    if isinstance(c, dict):
                        val = c.get("cavity_id") or c.get("cavity") or c.get("pin") or c.get("id") or c.get("name")
                    else:
                        val = c
                    if val is not None:
                        extracted.append(str(val))
                if extracted:
                    return extracted
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

        endpoints = []
        start_node = self.start_combo.currentData()
        start_pin = self.start_pin_combo.currentText().strip()
        if start_node:
            endpoints.append({"node_id": start_node, "cavity_id": start_pin})

        end_node = self.end_combo.currentData()
        end_pin = self.end_pin_combo.currentText().strip()
        if end_node:
            endpoints.append({"node_id": end_node, "cavity_id": end_pin})

        # --- FIX 1: Physically bridge disconnected endpoints BEFORE routing ---
        if len(endpoints) == 2 and self.project_model:
            s_node = endpoints[0].get("node_id")
            e_node = endpoints[1].get("node_id")
            
            if s_node and e_node and s_node != e_node:
                # Dynamically construct topology if nodes are floating
                self._bridge_node_to_network(s_node)
                self._bridge_node_to_network(e_node)

        # 2. Now compute the route through the newly updated bundle network
        routed_bundle_ids = self._compute_route(endpoints)

        new_wire_data = {
            "wire_id": wire_id,
            "signal_name": self.signal_input.text().strip(),
            "gauge": gauge,
            "outer_diameter_mm": od,
            "color": base_code,
            "stripe_color": stripe_code,
            "wire_part_number": f"WIRE-{gauge}-{base_code}",
            "extra_length_mm": extra_len,
            "endpoints": endpoints,
            "routed_bundle_ids": routed_bundle_ids,
            "is_highlighted": self.wire_data.get("is_highlighted", False)
        }

        self.wire_data.update(new_wire_data)

        parent_widget = self.parent()
        if parent_widget and hasattr(parent_widget, "refresh_wires"):
            parent_widget.refresh_wires()

        main_win = self.window()
        if main_win and hasattr(main_win, "update"):
            main_win.update()

        self.accept()