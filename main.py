import sys
import os,uuid

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QMenuBar, QSplitter, QInputDialog, QUndoStack,QLineEdit,QDialog
    ,QFileDialog,QMessageBox,QTabWidget
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
from ui.wires_tab import WiresTabWidget
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
        
    def load_project_action(self):
        """Opens a file dialog to load an existing harness project from SQLite or JSON."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Harness Project", 
            "", 
            "SQLite Database (*.db);;JSON Project Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                project_data = {}
                if file_path.endswith(".db"):
                    project_data = DatabaseManager.load_project(file_path)
                elif file_path.endswith(".json"):
                    import json
                    with open(file_path, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                
                if project_data:
                    # Initialize project model with loaded data
                    self.current_project = HarnessProjectModel(project_data)
                    
                    # Clear undo history stack for the new project state
                    self.undo_stack.clear()
                    
                    # Refresh tree view and CAD canvas graphics
                    self.refresh_views()
                    
                    self.statusBar().showMessage(f"Successfully loaded project from {file_path}")
                else:
                    QMessageBox.warning(self, "Load Warning", "The selected file contained no valid project data.")
                    
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load project file:\n{str(e)}")
                
    def refresh_views(self):
        """Refreshes tree view and canvas whenever model state changes (undo/redo/edit)."""
        self.project_tree.load_project(self.current_project)
        self.cad_canvas.load_topology(self.current_project)
        self.wires_tab.refresh_wires()
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
                    "position_2d": {"x": 41.0, "y": -222.0}, 
                    "pins": [{"cavity_id": "1", "signal_name": "CAN_H", "insertion_depth_mm": 4.5}, {"cavity_id": "2", "signal_name": "CAN_L", "insertion_depth_mm": 4.5}]
                }, 
                {
                    "node_id": "node_sensor", 
                    "part_number": "CONN-SEN-3P", 
                    "ref_designator": "X2", 
                    "position_2d": {"x": 600.0, "y": 200.0}, 
                    "pins": [{"cavity_id": "A", "signal_name": "CAN_H", "insertion_depth_mm": 3.0}, {"cavity_id": "B", "signal_name": "CAN_L", "insertion_depth_mm": 3.0}]
                }, 
                {
                    "node_id": "node_x3", 
                    "part_number": "CONN-X3-2P", 
                    "ref_designator": "X3", 
                    "position_2d": {"x": 350.0, "y": 300.0}, 
                    "pins": [{"cavity_id": "1", "signal_name": "GND", "insertion_depth_mm": 3.5}]
                }, 
                {
                    "node_id": "node_junc_19F9", 
                    "part_number": "SPLICE-JUNCTION-GEN", 
                    "ref_designator": "J1", 
                    "position_2d": {"x": 320.5, "y": -11.0}, 
                    "pins": []
                }
            ], 
            "bundles": [
                {"bundle_id": "BUN-4424", "start_node_id": "node_ecu", "end_node_id": "node_junc_19F9", "length_mm": 225.0, "coverings": []}, 
                {"bundle_id": "BUN-7405", "start_node_id": "node_junc_19F9", "end_node_id": "node_sensor", "length_mm": 225.0, "coverings": []},
                # Added physical bundle connecting node_x3 to the junction network
                {"bundle_id": "BUN-9999", "start_node_id": "node_x3", "end_node_id": "node_junc_19F9", "length_mm": 180.0, "coverings": []}
            ], 
            "wires": [
                {
                    "wire_id": "W-01", 
                    "signal_name": "CAN_H", 
                    "part_number": "WIRE-FLRY-0.5-YEL", 
                    "color": "Yellow", 
                    "endpoints": [{"node_id": "node_ecu", "cavity_id": "1"}, {"node_id": "node_sensor", "cavity_id": "A"}], 
                    "routed_bundle_ids": ["BUN-4424", "BUN-7405"], 
                    "extra_length_mm": 25.0
                }, 
                {
                    "wire_id": "W-02", 
                    "signal_name": "GND", 
                    "part_number": "WIRE-FLRY-0.5-GEN", 
                    "color": "Blue", 
                    "endpoints": [{"node_id": "node_x3", "cavity_id": "1"}, {"node_id": "node_ecu", "cavity_id": "2"}], 
                    "routed_bundle_ids": ["BUN-9999", "BUN-4424"], # Now has a continuous connected path!
                    "extra_length_mm": 20.0
                }
            ]
        }
        # DatabaseManager.save_project(self.current_project.data)

    def _init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)

        # Left Dock / Tree View (Project Hierarchy)
        self.project_tree = HarnessProjectTreeView()
        self.project_tree.wireDoubleClicked.connect(self.show_wire_properties)
        self.project_tree.bundleDoubleClicked.connect(self.show_bundle_properties)
        self.project_tree.nodeDoubleClicked.connect(self.show_connector_properties)
        self.sidebar_tabs = QTabWidget()

        # Existing Project Tree Tab
        self.sidebar_tabs.addTab(self.project_tree, "Project")

        # New Wires Tab
        self.wires_tab = WiresTabWidget(self.current_project,self.undo_stack, self)
        self.sidebar_tabs.addTab(self.wires_tab, "Wires")
        main_splitter.addWidget(self.sidebar_tabs)

        # Center Drawing & Layout Engine Canvas Workspace
        self.cad_canvas = HarnessCADCanvas()

        self.cad_canvas = HarnessCADCanvas()
        self.cad_canvas.nodesMoved.connect(self.handle_nodes_moved)
        self.cad_canvas.nodeDeletionRequested.connect(self.remove_connector_action)
        self.cad_canvas.tableMoved.connect(self.handle_table_moved)
        main_splitter.addWidget(self.cad_canvas)
        self.project_tree.entitySelected.connect(self.cad_canvas.highlight_entity)
        main_splitter.setSizes([350, 1050])
        self.setCentralWidget(main_splitter)
        self.statusBar().showMessage("Ready | Undo/Redo Engine Active")

    def _create_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        # --- New Project Action ---
        new_action = file_menu.addAction("&New Project...")
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_project_action)

        file_menu.addSeparator()

        # --- Local (JSON Format) ---
        local_open_action = file_menu.addAction("Open Local Project (.json)...")
        local_open_action.setShortcut("Ctrl+O")
        local_open_action.triggered.connect(self.load_local_json_action)

        local_save_action = file_menu.addAction("Save Local Project (.json)...")
        local_save_action.setShortcut("Ctrl+S")
        local_save_action.triggered.connect(self.save_local_json_action)

        file_menu.addSeparator()

        # --- Central (SQLite Database) ---
        central_open_action = file_menu.addAction("Open Central Project (.db)...")
        central_open_action.setShortcut("Ctrl+Shift+O")
        central_open_action.triggered.connect(self.load_central_db_action)

        central_save_action = file_menu.addAction("Save Central Project (.db)...")
        central_save_action.setShortcut("Ctrl+Shift+S")
        central_save_action.triggered.connect(self.save_central_db_action)

        file_menu.addSeparator()

        # --- Exit ---
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # Edit Menu (Connected to Undo Stack)
        edit_menu = menubar.addMenu("&Edit")
        
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
        tools_menu = menubar.addMenu("&Tools")
        routing_action = tools_menu.addAction("Wire Routing Manager...")
        routing_action.triggered.connect(self.open_wire_routing_manager)
        drc_action = QAction("Run Design Rule Checker (DRC)", self)
        tools_menu.addAction(drc_action)

        formboard_action = QAction("Generate 1:1 Formboard", self)
        tools_menu.addAction(formboard_action)
        # Analysis Menu
        analysis_menu = menubar.addMenu("&Analysis")
        diamter_action = analysis_menu.addAction("Bundle Diameter Manager...")
        diamter_action.triggered.connect(self.open_branch_analysis)


    def _init_toolbar(self):
        """Optional: Adds quick-access buttons to a main window toolbar."""
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setMovable(False)

        # New Project Toolbar Button
        new_btn = toolbar.addAction("New")
        new_btn.triggered.connect(self.new_project_action)

        toolbar.addSeparator()

        # Save Local Toolbar Button
        save_btn = toolbar.addAction("Save Local")
        save_btn.triggered.connect(self.save_local_json_action)
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
        """Opens the unified single-window AddWireDialog."""
        from ui.wire_dialog import AddWireDialog
        from commands.harness_commands import ModifyHarnessCommand
        
        dialog = AddWireDialog(self.current_project, self)
        if dialog.exec_() == QDialog.Accepted:
            new_wire = dialog.wire_data
            
            # Record undoable command
            command = ModifyHarnessCommand(
                self.current_project, 
                f"Add Wire ({new_wire['wire_id']})", 
                self.refresh_views
            )
            
            self.current_project.data.setdefault("wires", []).append(new_wire)
            
            command.set_new_state()
            self.undo_stack.push(command)
            DatabaseManager.save_project(self.current_project.data)
            self.refresh_views()
            self.statusBar().showMessage(f"Added wire {new_wire['wire_id']}.")

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
        # Snapshot state before movement
        command = ModifyHarnessCommand(self.current_project, f"Move {len(moved_data)} Connector Node(s)", self.refresh_views)
        
        # Apply all positions to the model atomically
        for node_id, new_pos in moved_data.items():
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
        # DatabaseManager.save_project(self.current_project.data)
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
        # DatabaseManager.save_project(self.current_project.data)
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
            # DatabaseManager.save_project(self.current_project.data)
            
            # 6. Refresh Canvas and Tree View
            self.refresh_views()
            self.statusBar().showMessage(f"Updated properties for bundle {bundle_id} (Undoable).")
    def show_wire_properties(self, wire_data: dict):
        """Displays properties dialog for a wire, recording changes on the undo stack."""
        from ui.wire_dialog import WirePropertiesDialog
        from commands.harness_commands import ModifyHarnessCommand
        
        wire_id = wire_data.get("wire_id")
        
        # 1. Instantiate command before changes to capture old_state
        command = ModifyHarnessCommand(
            self.current_project, 
            f"Edit Wire ({wire_id})", 
            self.refresh_views
        )
        
        # 2. Open dialog
        dialog = WirePropertiesDialog(wire_data, self.current_project,self.undo_stack, self.wires_tab.refresh_wires,self)
        
        if dialog.exec_() == QDialog.Accepted:
            for w in self.current_project.data.get("wires", []):
                if w["wire_id"] == wire_id:
                    w["wire_id"] = wire_data.get("wire_id")
                    w["signal_name"] = wire_data.get("signal_name")
                    w["color"] = wire_data.get("color")
                    w["stripe_color"] = wire_data.get("stripe_color")
                    w["gauge"] = wire_data.get("gauge")
                    w["outer_diameter_mm"] = wire_data.get("outer_diameter_mm")  # <--- Added this line
                    w["extra_length_mm"] = wire_data.get("extra_length_mm")
                    break
            
            # 4. Capture new_state and push to undo stack
            command.set_new_state()
            self.undo_stack.push(command)
            
            # 5. Save to SQLite database
            DatabaseManager.save_project(self.current_project.data)
            
            # 6. Refresh Canvas and Tree View
            self.refresh_views()
            self.statusBar().showMessage(f"Updated properties for wire {wire_id} (Undoable).")
    def save_local_json_action(self):
        """Saves the current harness project as a portable local JSON file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Local Project (JSON)", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    # Use model's internal data dictionary formatted with indentation
                    json.dump(self.current_project.data, f, indent=2)
                self.statusBar().showMessage(f"Successfully saved local JSON project to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save local JSON file:\n{str(e)}")

    def load_local_json_action(self):
        """Loads a harness project from a portable local JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Local Project (JSON)", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                
                if project_data:
                    self.current_project = HarnessProjectModel(project_data)
                    self.undo_stack.clear()
                    self.refresh_views()
                    self.wires_tab.refresh_wires()
                    self.statusBar().showMessage(f"Successfully loaded local JSON project from {file_path}")
                else:
                    QMessageBox.warning(self, "Load Warning", "The selected JSON file is empty.")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to parse local JSON file:\n{str(e)}")

    def save_central_db_action(self):
        """Saves the current harness project to a central SQLite database file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Central Project (Database)", "", "SQLite Database (*.db);;All Files (*)"
        )
        if file_path:
            try:
                DatabaseManager.save_project(self.current_project.data, file_path)
                self.statusBar().showMessage(f"Successfully saved central project to database {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save to central database:\n{str(e)}")

    def load_central_db_action(self):
        """Opens a central database file, lists available projects, and loads the user's selection."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Central Database", "", "SQLite Database (*.db);;All Files (*)"
        )
        if file_path:
            try:
                # 1. Fetch available projects from database
                projects = DatabaseManager.list_projects(file_path)
                if not projects:
                    QMessageBox.warning(self, "Central Database", "No valid projects found in the selected database.")
                    return
                
                # 2. Open selection dialog
                from ui.project_selector_dialog import ProjectSelectorDialog
                dialog = ProjectSelectorDialog(projects, self)
                
                if dialog.exec_() == QDialog.Accepted and dialog.selected_project:
                    project_data = dialog.selected_project.get("data")
                    if project_data:
                        # 3. Load selected project data into the model
                        self.current_project = HarnessProjectModel(project_data)
                        self.undo_stack.clear()
                        self.refresh_views()
                        
                        proj_name = dialog.selected_project.get('project_name')
                        self.statusBar().showMessage(f"Successfully loaded project '{proj_name}' from central database.")
                    else:
                        QMessageBox.warning(self, "Load Warning", "The selected project record contains empty data.")
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to load project from central database:\n{str(e)}")
    def handle_table_moved(self, node_id: str, new_offset: dict):
            """Records table movement in the model, pushes an undo command, and saves to database."""
            from commands.harness_commands import ModifyHarnessCommand
            
            # 1. Instantiate command before state change to capture old_state
            command = ModifyHarnessCommand(
                self.current_project, 
                f"Move Table ({node_id})", 
                self.refresh_views
            )
            
            # 2. Update offset in current project model
            for node in self.current_project.data.get("nodes", []):
                if node["node_id"] == node_id:
                    if "table_config" not in node:
                        node["table_config"] = {}
                    node["table_config"]["offset_2d"] = new_offset
                    break
                    
            # 3. Capture new_state and push to undo stack
            command.set_new_state()
            self.undo_stack.push(command)
            
            # 4. Save to SQLite database cache
            # DatabaseManager.save_project(self.current_project.data)
            
            self.statusBar().showMessage(f"Updated relative position for connector table {node_id} (Undoable).")
    def handle_table_moved(self, node_id: str, new_offset: dict):
        """Records table movement in the model, pushes an undo command, and saves to database."""
        from commands.harness_commands import ModifyHarnessCommand
        
        # 1. Instantiate command before state change to capture old_state
        command = ModifyHarnessCommand(
            self.current_project, 
            f"Move Table ({node_id})", 
            self.refresh_views
        )
        
        # 2. Update offset in current project model
        for node in self.current_project.data.get("nodes", []):
            if node["node_id"] == node_id:
                if "table_config" not in node:
                    node["table_config"] = {}
                node["table_config"]["offset_2d"] = new_offset
                break
                
        # 3. Capture new_state and push to undo stack
        command.set_new_state()
        self.undo_stack.push(command)
        
        # 4. Save to SQLite database cache
        # DatabaseManager.save_project(self.current_project.data)
        
        self.statusBar().showMessage(f"Updated relative position for connector table {node_id} (Undoable).")
    def open_wire_routing_manager(self):
        """Opens the interactive wire routing and pathfinding manager dialog."""
        from ui.wire_routing_dialog import WireRoutingManagerDialog
        from commands.harness_commands import ModifyHarnessCommand
        
        command = ModifyHarnessCommand(
            self.current_project, 
            "Update Wire Routing Paths", 
            self.refresh_views
        )
        
        dialog = WireRoutingManagerDialog(self.current_project, self)
        
        if dialog.exec_() == QDialog.Accepted:
            command.set_new_state()
            self.undo_stack.push(command)
            # DatabaseManager.save_project(self.current_project.data)
            self.refresh_views()
            self.statusBar().showMessage("Updated wire routing pathways successfully.")
    def new_project_action(self):
        """Creates a brand new empty harness project with prompt safeguard."""
        # Optional safeguard if current project has items
        if self.current_project and (self.current_project.data.get("nodes") or self.current_project.data.get("wires")):
            reply = QMessageBox.question(
                self, 
                "New Project", 
                "Create a new project? Any unsaved changes will be lost.",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Initialize fresh default project structure
        fresh_data = {
            "project_id": f"proj-{uuid.uuid4().hex[:8]}",
            "project_name": "New Harness Project",
            "revision": "A",
            "units": "MM_AWG",
            "nodes": [],
            "bundles": [],
            "wires": [],
            "cables": []
        }
        
        self.current_project = HarnessProjectModel(fresh_data)
        
        # Clear undo history stack for the clean project state
        self.undo_stack.clear()
        
        # Refresh tree view and CAD canvas graphics
        self.refresh_views()
        
        self.statusBar().showMessage("Created new harness project.")
    def show_connector_properties(self, node_data: dict):
        """Displays properties & cavity manager dialog for a connector node, recording changes on the undo stack."""
        from ui.connector_dialog import ConnectorPropertiesDialog
        from commands.harness_commands import ModifyHarnessCommand
        
        node_id = node_data.get("node_id")
        
        # 1. Instantiate command before changes to capture old_state
        command = ModifyHarnessCommand(
            self.current_project, 
            f"Edit Node & Cavities ({node_data.get('ref_designator')})", 
            self.refresh_views
        )
        
        # 2. Open dialog
        dialog = ConnectorPropertiesDialog(node_data, self)
        
        if dialog.exec_() == QDialog.Accepted:
            # 3. Explicitly find and update the node in the project model by its ID
            for n in self.current_project.data.get("nodes", []):
                if n["node_id"] == node_id:
                    n["ref_designator"] = node_data.get("ref_designator")
                    n["part_number"] = node_data.get("part_number")
                    n["pins"] = node_data.get("pins")
                    n["is_junction"] = node_data.get("is_junction")  # <--- Added this line!
                    break
            
            # 4. Capture new_state and push to undo stack
            command.set_new_state()
            self.undo_stack.push(command)
            
            # 5. Save to SQLite database
            DatabaseManager.save_project(self.current_project.data)
            
            # 6. Refresh Canvas and Tree View
            self.refresh_views()
            self.statusBar().showMessage(f"Updated properties for node {node_id} (Undoable).")
    def open_branch_analysis(self):
        """Opens the Branch & Covering Analysis Report window."""
        from ui.branch_analysis_dialog import BranchAnalysisDialog
        dialog = BranchAnalysisDialog(self.current_project, self)
        dialog.exec_()
if __name__ == "__main__":
    DatabaseManager.init_database()
    init_db()
    app = QApplication(sys.argv)
    window = HarnessEditorWindow()
    window.show()
    sys.exit(app.exec_())