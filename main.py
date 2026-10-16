import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QMenuBar, QSplitter, QInputDialog, QUndoStack,QLineEdit
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
        self.current_project.data = {
            "project_id": "proj-9988-aabb",
          "project_name": "Engine Bay Harness - Model X",
          "revision": "B",
          "units": "MM_AWG",
          "nodes": [
            {
              "node_id": "node_ecu",
              "part_number": "CONN-ECU-48P",
              "ref_designator": "X1",
              "position_2d": {
                "x": 41.0,
                "y": -222.0
              },
              "pins": [
                {
                  "cavity_id": "1",
                  "signal_name": "CAN_H",
                  "insertion_depth_mm": 4.5
                },
                {
                  "cavity_id": "2",
                  "signal_name": "CAN_L",
                  "insertion_depth_mm": 4.5
                }
              ]
            },
            {
              "node_id": "node_sensor",
              "part_number": "CONN-SEN-3P",
              "ref_designator": "X2",
              "position_2d": {
                "x": 600.0,
                "y": 200.0
              },
              "pins": [
                {
                  "cavity_id": "A",
                  "signal_name": "CAN_H",
                  "insertion_depth_mm": 3.0
                },
                {
                  "cavity_id": "B",
                  "signal_name": "CAN_L",
                  "insertion_depth_mm": 3.0
                }
              ]
            },
            {
              "node_id": "node_x3",
              "part_number": "11",
              "ref_designator": "x3",
              "position_2d": {
                "x": 350.0,
                "y": 300.0
              },
              "pins": [
                {
                  "cavity_id": "1",
                  "signal_name": "GND",
                  "insertion_depth_mm": 3.5
                }
              ]
            }
          ],
          "bundles": [
            {
              "bundle_id": "BUN-01",
              "start_node_id": "node_ecu",
              "end_node_id": "node_sensor",
              "length_mm": 450.0,
              "coverings": [
                {
                  "covering_part_number": "SLEEVE-NYLON-10MM",
                  "start_offset_mm": 0,
                  "end_offset_mm": 450
                }
              ]
            }
          ],
          "wires": [
            {
              "wire_id": "W-01",
              "signal_name": "CAN_H",
              "part_number": "WIRE-FLRY-0.5-YEL",
              "color": "Yellow",
              "endpoints": [
                {
                  "node_id": "node_ecu",
                  "cavity_id": "1"
                },
                {
                  "node_id": "node_sensor",
                  "cavity_id": "A"
                }
              ],
              "routed_bundle_ids": [
                "BUN-01"
              ],
              "extra_length_mm": 25.0
            },
            {
              "wire_id": "W-02",
              "signal_name": "11",
              "part_number": "WIRE-FLRY-0.5-GEN",
              "color": "Blue",
              "endpoints": [
                {
                  "node_id": "node_x3",
                  "cavity_id": "1"
                },
                {
                  "node_id": "node_ecu",
                  "cavity_id": "2"
                }
              ],
              "routed_bundle_ids": [
                
              ],
              "extra_length_mm": 20.0
            }
          ]
        }
        DatabaseManager.save_project(self.current_project.data)

    def _init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)

        # Left Dock / Tree View (Project Hierarchy)
        self.project_tree = HarnessProjectTreeView()
        main_splitter.addWidget(self.project_tree)

        # Center Drawing & Layout Engine Canvas Workspace
        self.cad_canvas = HarnessCADCanvas()
        self.cad_canvas.nodeDragFinished.connect(self.handle_node_dragged)
        main_splitter.addWidget(self.cad_canvas)

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
        """Interactively prompt user to select start/end nodes, check bundle routing, 
        automatically bridge missing pathways, and wrap the entire transaction in an undoable snapshot command."""
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

        # 2. Enter Wire Metadata first so we have the ID ready for the command description
        wire_id, ok3 = QInputDialog.getText(self, "Add Wire", "Enter Wire ID (e.g., W-02):")
        if not ok3 or not wire_id:
            return
            
        signal_name, ok4 = QInputDialog.getText(self, "Add Wire", "Enter Signal Name (e.g., LIN_BUS):")
        if not ok4 or not signal_name:
            return
            
        color, ok5 = QInputDialog.getText(self, "Add Wire", "Enter Wire Color (e.g., Blue/White):")
        if not ok5 or not color:
            return

        # Initialize the Undoable Snapshot Command
        from commands.harness_commands import ModifyHarnessCommand
        command = ModifyHarnessCommand(self.current_project, f"Add Wire {wire_id} (with Auto-Bundle)", self.refresh_views)

        # 3. Check for physical bundle pathway
        routed_bundles = self.current_project.find_bundle_path(start_node["node_id"], end_node["node_id"])
        if not routed_bundles:
            from PyQt5.QtWidgets import QMessageBox
            
            nearest = self.current_project.find_nearest_node(start_node["node_id"])
            nearest_hint = f"\n\nHint: The closest connector to {start_node['ref_designator']} is {nearest['ref_designator']}." if nearest else ""
            
            reply = QMessageBox.question(
                self, 
                "Missing Bundle Pathway", 
                f"No continuous physical bundle pathway found between {start_node['ref_designator']} and {end_node['ref_designator']}.{nearest_hint}\n\n"
                "Would you like to automatically create a connecting bundle between them?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                import uuid, math
                new_bundle_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"
                
                p1 = start_node.get("position_2d", {"x": 0, "y": 0})
                p2 = end_node.get("position_2d", {"x": 0, "y": 0})
                approx_length = math.sqrt((p2["x"] - p1["x"])**2 + (p2["y"] - p1["y"])**2)
                
                bundle_data = {
                    "bundle_id": new_bundle_id,
                    "start_node_id": start_node["node_id"],
                    "end_node_id": end_node["node_id"],
                    "length_mm": round(approx_length, 1),
                    "coverings": []
                }
                
                # Mutate model state inside command scope
                self.current_project.data["bundles"].append(bundle_data)
                routed_bundles = [new_bundle_id]
            else:
                return

        # 4. Add the wire object to the model
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

        # Finalize snapshot state and push onto undo stack
        command.set_new_state()
        self.undo_stack.push(command)
        self.statusBar().showMessage(f"Added wire {wire_id} (and bridge bundle if needed) successfully (Undoable).")

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
            
    def handle_node_dragged(self, node_id: str, old_pos: dict, new_pos: dict):
        """Pushes a node movement command onto the undo/redo stack."""
        command = MoveNodeCommand(self.current_project, node_id, old_pos, new_pos, self.refresh_views)
        self.undo_stack.push(command)
        self.statusBar().showMessage(f"Moved connector {node_id} (Undoable).")
        
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

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    window = HarnessEditorWindow()
    window.show()
    sys.exit(app.exec_())