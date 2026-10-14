from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QTreeView
from models.harness_model import HarnessProjectModel

class HarnessProjectTreeView(QTreeView):
    """Renders the hierarchical harness project structure (Nodes, Bundles, Wires)."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(False)
        self.setModel(QStandardItemModel(self))
        self.model().setHorizontalHeaderLabels(["Project Hierarchy", "Details"])
        self.setColumnWidth(0, 200)

    def load_project(self, project_model: HarnessProjectModel):
        """Populates the tree view from a HarnessProjectModel instance."""
        standard_model = self.model()
        standard_model.removeRows(0, standard_model.rowCount())

        root_data = project_model.data
        root_item = QStandardItem(f"Project: {root_data.get('project_name', 'Untitled')}")
        root_item.setEditable(False)
        standard_model.appendRow(root_item)

        # 1. Nodes Category (Connectors, Splices, Devices)
        nodes_item = QStandardItem("Nodes & Connectors")
        nodes_item.setEditable(False)
        for node in root_data.get("nodes", []):
            node_label = f"{node.get('ref_designator')} ({node.get('part_number')})"
            n_item = QStandardItem(node_label)
            n_item.setEditable(False)
            
            # Add pins/cavities under each node
            for pin in node.get("pins", []):
                pin_label = f"Pin/Cavity {pin.get('cavity_id')} -> Signal: {pin.get('signal_name', 'Unassigned')}"
                p_item = QStandardItem(pin_label)
                p_item.setEditable(False)
                n_item.appendRow(p_item)
                
            nodes_item.appendRow(n_item)
        root_item.appendRow(nodes_item)

        # 2. Bundles Category (Physical Routing Segments)
        bundles_item = QStandardItem("Bundles & Pathways")
        bundles_item.setEditable(False)
        for bundle in root_data.get("bundles", []):
            b_label = f"{bundle.get('bundle_id')}: {bundle.get('start_node_id')} ↔ {bundle.get('end_node_id')} ({bundle.get('length_mm')} mm)"
            b_item = QStandardItem(b_label)
            b_item.setEditable(False)
            bundles_item.appendRow(b_item)
        root_item.appendRow(bundles_item)

        # 3. Wires Category (Electrical Conductors)
        wires_item = QStandardItem("Wires & Circuits")
        wires_item.setEditable(False)
        for wire in root_data.get("wires", []):
            w_label = f"{wire.get('wire_id')} [{wire.get('signal_name')}] - {wire.get('color')}"
            w_item = QStandardItem(w_label)
            w_item.setEditable(False)
            wires_item.appendRow(w_item)
        root_item.appendRow(wires_item)

        self.expandAll()