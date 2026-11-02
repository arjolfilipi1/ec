from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import  pyqtSignal
from PyQt5.QtWidgets import QTreeView
from models.harness_model import HarnessProjectModel

class HarnessProjectTreeView(QTreeView):
    """Renders the hierarchical harness project structure (Nodes, Bundles, Wires)."""
    wireDoubleClicked = pyqtSignal(dict)
    bundleDoubleClicked = pyqtSignal(dict)
    nodeDoubleClicked = pyqtSignal(dict)
    entitySelected = pyqtSignal(dict)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(False)
        self.setModel(QStandardItemModel(self))
        self.model().setHorizontalHeaderLabels(["Project Hierarchy", "Details"])
        self.setColumnWidth(0, 200)
        # Connect double click signal
        self.doubleClicked.connect(self._on_item_double_clicked)
        self.clicked.connect(self._on_item_clicked)
        self.wire_map = {}  # index path or storage for quick wire lookup

    def load_project(self, project_model: HarnessProjectModel):
        """Populates the tree view and attaches metadata payloads to items across multiple columns."""
        standard_model = self.model()
        standard_model.removeRows(0, standard_model.rowCount())

        root_data = project_model.data
        
        # Root Item spanning across columns
        root_item = QStandardItem(f"Project: {root_data.get('project_name', 'Untitled')}")
        root_item.setEditable(False)
        standard_model.appendRow(root_item)

        # 1. Nodes Category
        nodes_item = QStandardItem("Nodes & Connectors")
        nodes_item.setEditable(False)
        for node in root_data.get("nodes", []):
            node_label = f"{node.get('ref_designator')} ({node.get('part_number')})"
            n_item_col0 = QStandardItem(node_label)
            n_item_col0.setEditable(False)
            
            # --- FIX: Populate Column 1 with the precise ID ---
            n_item_col1 = QStandardItem(str(node.get("node_id", "")))
            n_item_col1.setEditable(False)
            
            # Attach node metadata onto the primary functional item
            n_item_col0.setData({"type": "node", "node_data": node, "id": node["node_id"]}, 32)
            
            for pin in node.get("pins", []):
                pin_label = f"Pin/Cavity {pin.get('cavity_id')} -> Signal: {pin.get('signal_name', 'Unassigned')}"
                p_item = QStandardItem(pin_label)
                p_item.setEditable(False)
                n_item_col0.appendRow(p_item) # Sub-items remain under Column 0
                
            # Append as a structural 2-column row list
            nodes_item.appendRow([n_item_col0, n_item_col1])
        root_item.appendRow(nodes_item)

        # 2. Bundles Category
        bundles_item = QStandardItem("Bundles & Pathways")
        bundles_item.setEditable(False)
        for bundle in root_data.get("bundles", []):
            b_label = f"{bundle.get('start_node_id')} ↔ {bundle.get('end_node_id')} ({bundle.get('length_mm')} mm)"
            b_item_col0 = QStandardItem(b_label)
            b_item_col0.setEditable(False)
            
            # --- FIX: Populate Column 1 with the precise Bundle ID ---
            b_item_col1 = QStandardItem(str(bundle.get("bundle_id", "")))
            b_item_col1.setEditable(False)
            
            b_item_col0.setData({"type": "bundle", "bundle_data": bundle, "id": bundle["bundle_id"]}, 32)
            bundles_item.appendRow([b_item_col0, b_item_col1])
        root_item.appendRow(bundles_item)

        # 3. Wires Category
        wires_item = QStandardItem("Wires & Circuits")
        wires_item.setEditable(False)
        for wire in root_data.get("wires", []):
            w_label = f"[{wire.get('signal_name')}] - {wire.get('color')}"
            w_item_col0 = QStandardItem(w_label)
            w_item_col0.setEditable(False)
            
            # --- FIX: Populate Column 1 with the precise Wire ID ---
            w_item_col1 = QStandardItem(str(wire.get("wire_id", "")))
            w_item_col1.setEditable(False)
            
            w_item_col0.setData({"type": "wire", "wire_data": wire, "id": wire["wire_id"]}, 32)
            wires_item.appendRow([w_item_col0, w_item_col1])
            
        root_item.appendRow(wires_item)
        self.expand(root_item.index())
        self.expand(nodes_item.index())
        
        self.collapse(bundles_item.index())
        self.collapse(wires_item.index())

    def _on_item_clicked(self, index):
        """Triggered when any tree item is clicked."""
        item = self.model().itemFromIndex(index)
        if item:
            payload = item.data(32)
            if payload:
                self.entitySelected.emit(payload)
    def _on_item_double_clicked(self, index):
        item = self.model().itemFromIndex(index)
        if item:
            payload = item.data(32)
            if payload:
                if payload.get("type") == "wire":
                    self.wireDoubleClicked.emit(payload.get("wire_data"))
                elif payload.get("type") == "bundle":
                    self.bundleDoubleClicked.emit(payload.get("bundle_data"))
                elif payload.get("type") == "node":
                    self.nodeDoubleClicked.emit(payload.get("node_data"))  # Emit node data on double click
                    