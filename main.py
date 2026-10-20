import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QMenuBar, QSplitter, QInputDialog, QUndoStack,QLineEdit,QDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from copy import deepcopy
# Ensure local imports resolve correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import math
from database import init_db, DatabaseManager
from models.harness_model import HarnessProjectModel
from ui.project_tree import HarnessProjectTreeView
from ui.bundle_dialog import BundlePropertiesDialog
from ui.cad_canvas import HarnessCADCanvas
from commands.harness_commands import AddNodeCommand, RemoveNodeCommand,AddWireCommand,RemoveWireCommand,MoveNodeCommand,BreakBundleCommand

class HarnessEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automotive Harness Editor - CAD / CAE Workspace")
        self.resize(1400, 900)

        # Initialize Undo Stack
        self.undo_stack = QUndoStack(self)

        # Initialize active project model
        self.current_project = HarnessProjectModel()
        self._load_sample_data()

        # Initialize UI Layout & Menus
        self._init_ui()
        self._create_menus()

        # Populate Views
        self.refresh_views()

    def refresh_views(self):
        """Refreshes tree view and canvas whenever model state changes (undo/redo/edit)."""
        self.project_tree.load_project(self.current_project)
        self.cad_canvas.load_topology(self.current_project)

    def _load_sample_data(self):
        """Loads a sample multi-branch harness project topology for demonstration[cite: 1]."""
        self.current_project.data = {"project_id": "proj-9988-aabb", "project_name": "Engine Bay Harness - Model X", "revision": "B", "units": "MM_AWG", "nodes": [{"node_id": "node_ecu", "part_number": "CONN-ECU-48P", "ref_designator": "X1", "position_2d": {"x": 41.0, "y": -222.0}, "pins": [{"cavity_id": "1", "signal_name": "CAN_H", "insertion_depth_mm": 4.5}, {"cavity_id": "2", "signal_name": "CAN_L", "insertion_depth_mm": 4.5}]}, {"node_id": "node_sensor", "part_number": "CONN-SEN-3P", "ref_designator": "X2", "position_2d": {"x": 600.0, "y": 200.0}, "pins": [{"cavity_id": "A", "signal_name": "CAN_H", "insertion_depth_mm": 3.0}, {"cavity_id": "B", "signal_name": "CAN_L", "insertion_depth_mm": 3.0}]}, {"node_id": "node_x3", "part_number": "11", "ref_designator": "x3", "position_2d": {"x": 350.0, "y": 300.0}, "pins": [{"cavity_id": "1", "signal_name": "GND", "insertion_depth_mm": 3.5}]}, {"node_id": "node_junc_19F9", "part_number": "SPLICE-JUNCTION-GEN", "ref_designator": "J1", "position_2d": {"x": 320.5, "y": -11.0}, "pins": []}], "bundles": [{"bundle_id": "BUN-4424", "start_node_id": "node_ecu", "end_node_id": "node_junc_19F9", "length_mm": 225.0, "coverings": []}, {"bundle_id": "BUN-7405", "start_node_id": "node_junc_19F9", "end_node_id": "node_sensor", "length_mm": 225.0, "coverings": []}], "wires": [{"wire_id": "W-01", "signal_name": "CAN_H", "part_number": "WIRE-FLRY-0.5-YEL", "color": "Yellow", "endpoints": [{"node_id": "node_ecu", "cavity_id": "1"}, {"node_id": "node_sensor", "cavity_id": "A"}], "routed_bundle_ids": ["BUN-4424", "BUN-7405"], "extra_length_mm": 25.0}, {"wire_id": "W-02", "signal_name": "11", "part_number": "WIRE-FLRY-0.5-GEN", "color": "Blue", "endpoints": [{"node_id": "node_x3", "cavity_id": "1"}, {"node_id": "node_ecu", "cavity_id": "2"}], "routed_bundle_ids": [], "extra_length_mm": 20.0}]}
        DatabaseManager.save_project(self.current_project.data)

    def _init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)

        # Left Dock / Tree View (Project Hierarchy)
        self.project_tree = HarnessProjectTreeView()
        self.project_tree.wireDoubleClicked.connect(self.show_wire_properties)
        self.project_tree.bundleDoubleClicked.connect(self.show_bundle_properties)
        main_splitter.addWidget(self.project_tree)

        # Center Drawing & Layout Engine Canvas Workspace
        self.cad_canvas = HarnessCADCanvas()

        self.cad_canvas = HarnessCADCanvas()
        self.cad_canvas.nodesMoved.connect(self.handle_nodes_moved)
        self.cad_canvas.nodeDeletionRequested.connect(self.remove_connector_action)
        main_splitter.addWidget(self.cad_canvas)
        self.project_tree.entitySelected.connect(self.cad_canvas.highlight_entity)
        main_splitter.setSizes([350, 1050])
        self.setCentralWidget(main_splitter)
        self.statusBar().showMessage("Ready | Undo/Redo Engine Active")

    def _create_menus(self):
        menu_bar = self.menubar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        save_action = QAction("&Save Project", self)
        save_action.triggered.connect(lambda: DatabaseManager.save_project(self.current_project.data))
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu (Connected to Undo Stack)
        edit_menu = menu_bar.addMenu("&Edit")
        
        # Create Undo action from undo stack
        undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        undo_action.setShortcut(QKeySequence.Undo)
        edit_menu.addAction(undo_action)

        # Create Redo action from undo stack
        redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        redo_action.setShortcut(QKeySequence.Redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        add_node_action = QAction("Add Connector Node...", self)
        add_node_action.triggered.connect(self.prompt_add_node)
        edit_menu.addAction(add_node_action)

        remove_node_action = QAction("Remove Selected Connector", self)
        remove_node_action.triggered.connect(self.remove_selected_node)
        edit_menu.addAction(remove_node_action)
        edit_menu.addSeparator()
        add_wire_action = QAction("Add Wire...", self)
        add_wire_action.triggered.connect(self.prompt_add_wire)
        edit_menu.addAction(add_wire_action)

        remove_wire_action = QAction("Remove Wire...", self)
        remove_wire_action.triggered.connect(self.prompt_remove_wire)
        edit_menu.addAction(remove_wire_action)
        break_bundle_action = QAction("Break Bundle / Add Branch...", self)
        break_bundle_action.triggered.connect(self.prompt_break_bundle)
        edit_menu.addAction(break_bundle_action)
        # Tools Menu
        tools_menu = menu_bar.addMenu("&Tools")
        drc_action = QAction("Run Design Rule Checker (DRC)", self)
        tools_menu.addAction(drc_action)

        formboard_action = QAction("Generate 1:1 Formboard", self)
        tools_menu.addAction(formboard_action)
    def prompt_break_bundle(self):
        """Prompt user to select a bundle to break and specify a junction reference name."""
        bundles = self.current_project.data.get("bundles", [])
        if not bundles:
            self.statusBar().showMessage("No bundles available to break.")
            return

        bundle_ids = [b["bundle_id"] for b in bundles]
        bundle_id, ok1 = QInputDialog.getItem(self, "Break Bundle", "Select Bundle to Break:", bundle_ids, 0, False)
        if not ok1 or not bundle_id:
            return

        junction_ref, ok2 = QInputDialog.getText(self, "Break Bundle", "Enter Junction/Splice Reference (e.g., J1):", QLineEdit.Normal, "J1")
        if not ok2 or not junction_ref:
            return

        # Find bundle to calculate midpoint coordinates as default placement
        target_bundle = next(b for b in bundles if b["bundle_id"] == bundle_id)
        node_map = {n["node_id"]: n for n in self.current_project.data.get("nodes", [])}
        
        start_node = node_map.get(target_bundle["start_node_id"])
        end_node = node_map.get(target_bundle["end_node_id"])
        
        mid_x, mid_y = 300.0, 300.0
        if start_node and end_node:
            p1 = start_node.get("position_2d", {"x": 0, "y": 0})
            p2 = end_node.get("position_2d", {"x": 0, "y": 0})
            mid_x = (p1["x"] + p2["x"]) / 2.0
            mid_y = (p1["y"] + p2["y"]) / 2.0

        command = BreakBundleCommand(self.current_project, bundle_id, junction_ref, mid_x, mid_y, self.refresh_views)
        self.undo_stack.push(command)
        self.statusBar().showMessage(f"Broke bundle {bundle_id} and inserted junction {junction_ref} (Undoable).")
    def prompt_add_wire(self):
        """Interactively prompt user to select start/end nodes, automatically snap/bridge 
        disconnected endpoints to the harness trunk, and wrap the transaction in an undoable command."""
        nodes = self.current_project.data.get("nodes", [])
        if len(nodes) < 2:
            self.statusBar().showMessage("At least two connector nodes are required to route a wire.")
            return

        node_labels = [f"{n['ref_designator']} ({n['node_id']})" for n in nodes]
        
        # 1. Select Start & End Nodes
        start_choice, ok1 = QInputDialog.getItem(self, "Add Wire - Start Node", "Select Start Connector:", node_labels, 0, False)
        if not ok1:
            return
        start_node = nodes[node_labels.index(start_choice)]

        start_cavities = [p['cavity_id'] for p in start_node.get("pins", [{"cavity_id": "1"}])]
        start_cavity, ok_sc = QInputDialog.getItem(self, "Add Wire - Start Cavity", f"Select Cavity on {start_node['ref_designator']}:", start_cavities, 0, False)
        if not ok_sc:
            return

        end_choice, ok2 = QInputDialog.getItem(self, "Add Wire - End Node", "Select End Connector:", node_labels, 1 if len(node_labels) > 1 else 0, False)
        if not ok2:
            return
        end_node = nodes[node_labels.index(end_choice)]

        end_cavities = [p['cavity_id'] for p in end_node.get("pins", [{"cavity_id": "1"}])]
        end_cavity, ok_ec = QInputDialog.getItem(self, "Add Wire - End Cavity", f"Select Cavity on {end_node['ref_designator']}:", end_cavities, 0, False)
        if not ok_ec:
            return

        # 2. Enter Wire Metadata first
        wire_id, ok3 = QInputDialog.getText(self, "Add Wire", "Enter Wire ID (e.g., W-02):")
        if not ok3 or not wire_id:
            return
            
        signal_name, ok4 = QInputDialog.getText(self, "Add Wire", "Enter Signal Name (e.g., LIN_BUS):")
        if not ok4 or not signal_name:
            return
            
        color, ok5 = QInputDialog.getText(self, "Add Wire", "Enter Wire Color (e.g., Blue/White):")
        if not ok5 or not color:
            return

        # Initialize Undoable Snapshot Command
        from commands.harness_commands import ModifyHarnessCommand
        command = ModifyHarnessCommand(self.current_project, f"Add Wire {wire_id} (with Auto-Routing)", self.refresh_views)

        # Helper function to ensure a given node is connected to the network
        def ensure_node_connected(target_node):
            # Count bundles connected to this node
            attached_bundles = [b for b in self.current_project.data.get("bundles", []) 
                                if b["start_node_id"] == target_node["node_id"] or b["end_node_id"] == target_node["node_id"]]
            if attached_bundles:
                return  # Already connected

            # If no bundles exist in the entire project, we can't trunk-snap; connect it to the other node
            all_bundles = self.current_project.data.get("bundles", [])
            if not all_bundles:
                other_node = end_node if target_node["node_id"] == start_node["node_id"] else start_node
                import uuid, math
                b_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"
                p1 = target_node.get("position_2d", {"x": 0, "y": 0})
                p2 = other_node.get("position_2d", {"x": 0, "y": 0})
                length = math.sqrt((p2["x"] - p1["x"])**2 + (p2["y"] - p1["y"])**2)
                self.current_project.data["bundles"].append({
                    "bundle_id": b_id,
                    "start_node_id": target_node["node_id"],
                    "end_node_id": other_node["node_id"],
                    "length_mm": round(length, 1),
                    "coverings": []
                })
                return

            # Otherwise, find nearest bundle trunk segment to snap to
            nearest_trunk = self.current_project.find_nearest_bundle_segment(target_node["node_id"])
            if nearest_trunk:
                trunk_bundle = nearest_trunk["bundle"]
                proj = nearest_trunk["projection"]
                
                # Generate Z designation (Z1, Z2...)
                z_count = sum(1 for n in self.current_project.data.get("nodes", []) if "ref_designator" in n and n["ref_designator"].startswith("Z"))
                z_ref = f"Z{z_count + 1}"
                
                # Break trunk to insert Z junction
                z_node_id = self.current_project.break_bundle(trunk_bundle["bundle_id"], z_ref, proj["x"], proj["y"])
                
                # Create breakout branch bundle from Z junction to target node
                import uuid, math
                branch_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"
                p1 = proj
                p2 = target_node.get("position_2d", {"x": 0, "y": 0})
                length = math.sqrt((p2["x"] - p1["x"])**2 + (p2["y"] - p1["y"])**2)
                
                self.current_project.data["bundles"].append({
                    "bundle_id": branch_id,
                    "start_node_id": z_node_id,
                    "end_node_id": target_node["node_id"],
                    "length_mm": round(length, 1),
                    "coverings": []
                })

        # 3. Ensure both start and end nodes are integrated into the network
        ensure_node_connected(start_node)
        ensure_node_connected(end_node)

        # 4. Now find the complete continuous bundle path between start and end nodes
        routed_bundles = self.current_project.find_bundle_path(start_node["node_id"], end_node["node_id"])
        if not routed_bundles:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Routing Error", f"Could not establish a continuous bundle path between {start_node['ref_designator']} and {end_node['ref_designator']}.")
            return

        # 5. Add the wire object
        wire_data = {
            "wire_id": wire_id,
            "signal_name": signal_name,
            "part_number": "WIRE-FLRY-0.5-GEN",
            "color": color,
            "endpoints": [
                {"node_id": start_node["node_id"], "cavity_id": start_cavity},
                {"node_id": end_node["node_id"], "cavity_id": end_cavity}
            ],
            "routed_bundle_ids": routed_bundles,
            "extra_length_mm": 20.0
        }
        self.current_project.add_wire_object(wire_data)

        # Finalize snapshot and push to undo stack
        command.set_new_state()
        self.undo_stack.push(command)
        self.statusBar().showMessage(f"Added wire {wire_id} successfully with automated path resolution (Undoable).")

    def prompt_remove_wire(self):
        """Prompt user to select and remove an existing wire."""
        wires = self.current_project.data.get("wires", [])
        if not wires:
            self.statusBar().showMessage("No wires available to remove.")
            return

        wire_ids = [w["wire_id"] for w in wires]
        wire_id, ok = QInputDialog.getItem(self, "Remove Wire", "Select Wire ID to remove:", wire_ids, 0, False)
        if ok and wire_id:
            command = RemoveWireCommand(self.current_project, wire_id, self.refresh_views)
            self.undo_stack.push(command)
            self.statusBar().showMessage(f"Removed wire {wire_id} (Undoable).")
            
    def handle_nodes_moved(self, moved_data: dict):
        """Pushes a single batched movement command for all dragged nodes onto the undo stack."""
        from commands.harness_commands import ModifyHarnessCommand
        print(moved_data)
        # Snapshot state before movement
        command = ModifyHarnessCommand(self.current_project, f"Move {len(moved_data)} Connector Node(s)", self.refresh_views)
        
        # Apply all positions to the model atomically
        for node_id, new_pos in moved_data.items():
            print(node_id,new_pos)
            self.current_project.update_node_position(node_id, new_pos["x"], new_pos["y"])
            
        # Snapshot state after movement and push once
        command.set_new_state()
        self.undo_stack.push(command)
        self.statusBar().showMessage(f"Moved {len(moved_data)} connector node(s) (Undoable).")
        
    def prompt_add_node(self):
        """Prompt user to add a new connector node and push onto undo stack."""
        ref_des, ok1 = QInputDialog.getText(self, "Add Connector", "Enter Reference Designator (e.g., X3):")
        if not ok1 or not ref_des:
            return
        part_num, ok2 = QInputDialog.getText(self, "Add Connector", "Enter Manufacturer Part Number:")
        if not ok2 or not part_num:
            return
            
        node_data = {
            "node_id": f"node_{ref_des.lower()}",
            "part_number": part_num,
            "ref_designator": ref_des,
            "position_2d": {"x": 350.0, "y": 300.0},
            "pins": [{"cavity_id": "1", "signal_name": "GND", "insertion_depth_mm": 3.5}]
        }

        # Push command to undo stack
        command = AddNodeCommand(self.current_project, node_data, self.refresh_views)
        self.undo_stack.push(command)
        self.statusBar().showMessage(f"Added connector {ref_des} (Undoable).")
    def add_connector_action(self, ref_designator: str = "X3", part_number: str = "CONN-8PIN", x: float = 100.0, y: float = 100.0):
        """Adds a new physical connector node with undo support and SQLite persistence."""
        from commands.harness_commands import ModifyHarnessCommand
        
        node_id = f"node_{uuid.uuid4().hex[:6].upper()}"
        
        # 1. Instantiate command before changes to capture old_state
        command = ModifyHarnessCommand(
            self.current_project, 
            f"Add Connector ({ref_designator})", 
            self.refresh_views
        )
        
        # 2. Add node to project model (initializing dual drawing and formboard positions)
        self.current_project.add_node(
            node_id=node_id,
            part_number=part_number,
            ref_designator=ref_designator,
            x=x, y=y,
            fb_x=x, fb_y=y,
            pins=[{"cavity_id": "1", "pin_number": "1"}, {"cavity_id": "2", "pin_number": "2"}]
        )
        
        # 3. Capture new_state and push to undo stack
        command.set_new_state()
        self.undo_stack.push(command)
        
        # 4. Save to SQLite database and refresh views
        DatabaseManager.save_project(self.current_project.data)
        self.refresh_views()
        self.statusBar().showMessage(f"Added connector {ref_designator} successfully.")

    def remove_connector_action(self, node_id: str):
        """Removes a connector node (and associated bundles/wires) with undo support and SQLite persistence."""
        from commands.harness_commands import ModifyHarnessCommand
        
        # 1. Instantiate command before changes
        command = ModifyHarnessCommand(
            self.current_project, 
            f"Remove Connector ({node_id})", 
            self.refresh_views
        )
        
        # 2. Execute model removal
        self.current_project.remove_node(node_id)
        
        # 3. Capture new_state and push to undo stack
        command.set_new_state()
        self.undo_stack.push(command)
        
        # 4. Save to SQLite database and refresh views
        DatabaseManager.save_project(self.current_project.data)
        self.refresh_views()
        self.statusBar().showMessage(f"Removed connector {node_id} and cleaned up attached pathways.")
    def remove_selected_node(self):
        """Removes selected node via undo stack command."""
        selected_items = self.cad_canvas.scene.selectedItems()
        if not selected_items:
            self.statusBar().showMessage("No connector node selected on the canvas.")
            return
            
        for item in selected_items:
            node_id = item.data(0)
            if node_id:
                command = RemoveNodeCommand(self.current_project, node_id, self.refresh_views)
                self.undo_stack.push(command)
                self.statusBar().showMessage(f"Removed connector node {node_id} (Undoable).")
    def show_bundle_properties(self, bundle_data: dict):
        """Displays the properties dialog for a bundle and explicitly updates the model by bundle_id."""
        from ui.bundle_dialog import BundlePropertiesDialog
        from commands.harness_commands import ModifyHarnessCommand
        
        bundle_id = bundle_data.get("bundle_id")
        
        # 1. Instantiate the undo command to capture old_state BEFORE changes
        command = ModifyHarnessCommand(
            self.current_project, 
            f"Edit Bundle Properties ({bundle_id})", 
            self.refresh_views
        )
        
        # 2. Open dialog
        dialog = BundlePropertiesDialog(bundle_data, self)
        
        if dialog.exec_() == QDialog.Accepted:
            # 3. Explicitly find and update the bundle in the project model by ID
            for b in self.current_project.data.get("bundles", []):
                if b["bundle_id"] == bundle_id:
                    b["length_mm"] = bundle_data.get("length_mm")
                    b["coverings"] = bundle_data.get("coverings")
                    break
            
            # 4. Capture new_state AFTER modifications
            command.set_new_state()
            self.undo_stack.push(command)
            
            # 5. Persist to SQLite database
            DatabaseManager.save_project(self.current_project.data)
            
            # 6. Refresh Canvas and Tree View
            self.refresh_views()
            self.statusBar().showMessage(f"Updated properties for bundle {bundle_id} (Undoable).")
    def show_wire_properties(self, wire_data: dict):
        """Displays the properties dialog for a wire, updates the model by wire_id, and records on undo stack."""
        from ui.wire_dialog import WirePropertiesDialog
        from commands.harness_commands import ModifyHarnessCommand
        
        wire_id = wire_data.get("wire_id")
        
        # 1. Instantiate the undo command to capture old_state BEFORE changes
        command = ModifyHarnessCommand(
            self.current_project, 
            f"Edit Wire Properties ({wire_id})", 
            self.refresh_views
        )
        
        # 2. Open the wire properties dialog
        dialog = WirePropertiesDialog(wire_data, self)
        
        if dialog.exec_() == QDialog.Accepted:
            # 3. Explicitly locate and update the wire in the project model by its unique ID
            for w in self.current_project.data.get("wires", []):
                if w["wire_id"] == wire_id:
                    w["wire_id"] = wire_data.get("wire_id")
                    w["signal_name"] = wire_data.get("signal_name")
                    w["color"] = wire_data.get("color")
                    w["gauge"] = wire_data.get("gauge")
                    w["extra_length_mm"] = wire_data.get("extra_length_mm")
                    break
            
            # 4. Capture new_state AFTER modifications and push to undo stack
            command.set_new_state()
            self.undo_stack.push(command)
            
            # 5. Save updated project state to the SQLite database cache
            DatabaseManager.save_project(self.current_project.data)
            
            # 6. Refresh Canvas and Tree View
            self.refresh_views()
            self.statusBar().showMessage(f"Updated properties for wire {wire_id} (Undoable).")
if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    window = HarnessEditorWindow()
    window.show()
    sys.exit(app.exec_())