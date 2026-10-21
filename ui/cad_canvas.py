from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem,
                                QGraphicsLineItem,QGraphicsEllipseItem)
from PyQt5.QtCore import Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QBrush, QColor, QFont, QWheelEvent, QPainter
from models.harness_model import HarnessProjectModel
import math

class ConnectorTableGraphicsItem(QGraphicsRectItem):
    """Visual table attached to a connector node displaying pin/wire mappings and pairings."""
    
    def __init__(self, node_id: str, node_data: dict, project_model=None):
        super().__init__()
        self.node_data = node_data
        self.project_model = project_model
        self.node_id = node_id
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
        offset = node_data.get("table_config", {}).get("offset_2d", {"x": 50, "y": -40})
        self.setPos(offset["x"], offset["y"])
        self.setPen(QPen(QColor(127, 140, 141), 1, Qt.SolidLine))
        
        self.setBrush(QBrush(QColor(255, 255, 255, 245)))
        self.refresh_layout()
    def mousePressEvent(self, event):
        self.initial_scene_pos = self.pos()
        super().mousePressEvent(event)
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        new_scene_pos = self.scenePos()
        
        if new_scene_pos != self.initial_scene_pos:
            # Find parent node to calculate new relative offset (dx, dy)
            canvas = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if canvas and self.node_id in canvas.node_items:
                node_item = canvas.node_items[self.node_id]
                node_center = node_item.sceneBoundingRect().center()
                
                # Compute relative offset from node center
                rel_x = new_scene_pos.x() - node_center.x()
                rel_y = new_scene_pos.y() - node_center.y()
                
                if hasattr(canvas, "tableMoved"):
                    canvas.tableMoved.emit(self.node_id, {"x": round(rel_x, 1), "y": round(rel_y, 1)})
    def refresh_layout(self):
        """Redraws table headers and maps wire endpoints to node cavity/pin rows with safe fallbacks."""
        for child in self.childItems():
            if child.scene():
                child.scene().removeItem(child)

        config = self.node_data.get("table_config", {})
        
        # 1. Fallback default columns if missing or empty
        columns = config.get("columns", [])
        if not columns:
            columns = [
                {"id": "cavity", "label": "Cav", "width": 35},
                {"id": "pin", "label": "Pin", "width": 35},
                {"id": "signal", "label": "Signal", "width": 70},
                {"id": "wire_id", "label": "Wire", "width": 60},
                {"id": "color", "label": "Color", "width": 45}
            ]

        # 2. Fallback default pins if missing or empty so the table expands properly
        pins = self.node_data.get("pins", [])
        if not pins:
            pins = [
                {"cavity_id": "1", "pin_number": "1"}, 
                {"cavity_id": "2", "pin_number": "2"}
            ]

        ref_des = self.node_data.get("ref_designator", "X")
        node_id = self.node_data.get("node_id")

        # Header Title (Connector Name)
        header_text = QGraphicsTextItem(ref_des, self)
        header_text.setDefaultTextColor(QColor(41, 128, 185))
        header_text.setFont(QFont("Segoe UI", 9, QFont.Bold))
        header_text.setPos(4, 2)

        total_width = sum(col.get("width", 50) for col in columns)
        row_height = 18
        header_height = 22
        total_height = header_height + (len(pins) * row_height)
        
        self.setRect(0, 0, total_width, total_height)

        # Draw Column Headers
        current_x = 0
        for col in columns:
            col_width = col.get("width", 50)
            col_label = col.get("label", "")
            
            lbl = QGraphicsTextItem(col_label, self)
            lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
            lbl.setDefaultTextColor(QColor(52, 73, 94))
            lbl.setPos(current_x + 2, header_height - 18)
            current_x += col_width

        # Build map of wires connected to this node's cavities
        wire_map = {}
        if self.project_model:
            for w in self.project_model.data.get("wires", []):
                for ep in w.get("endpoints", []):
                    if ep.get("node_id") == node_id:
                        wire_map[ep.get("cavity_id")] = w

        # Draw Rows for Each Pin / Cavity
        for row_idx, pin in enumerate(pins):
            y_pos = header_height + (row_idx * row_height)
            cavity_id = pin.get("cavity_id", str(row_idx + 1))
            pin_num = pin.get("pin_number", cavity_id)
            
            connected_wire = wire_map.get(cavity_id, {})
            signal = connected_wire.get("signal_name", "")
            wire_id = connected_wire.get("wire_id", "")
            color = connected_wire.get("color", "")

            current_x = 0
            for col in columns:
                col_id = col.get("id")
                col_width = col.get("width", 50)
                
                val = ""
                if col_id == "cavity":
                    val = str(cavity_id)
                elif col_id == "pin":
                    val = str(pin_num)
                elif col_id == "signal":
                    val = str(signal)
                elif col_id == "wire_id":
                    val = str(wire_id)
                elif col_id == "color":
                    val = str(color)

                if val:
                    cell_text = QGraphicsTextItem(val, self)
                    cell_text.setFont(QFont("Segoe UI", 8))
                    cell_text.setDefaultTextColor(QColor(44, 62, 80))
                    cell_text.setPos(current_x + 2, y_pos)
                
                current_x += col_width
        
class NodeGraphicsItem(QGraphicsRectItem):
    """Custom interactive rectangle representing a physical connector node."""
    def __init__(self, node_id, x, y, width, height, label_text, canvas_ref):
        # Define local rect centered at (0,0)
        super().__init__(-width/2, -height/2, width, height)
        self.node_id = node_id
        self.canvas_ref = canvas_ref
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
        # Position item in scene coordinates
        self.setPos(x, y)
        
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(QColor(52, 73, 94), 2))
        
        self.label = QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QColor(41, 128, 185))
        self.label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.label.setPos(-width/2 + 5, -height/2 + 5)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            self.canvas_ref.on_node_moved()
        return super().itemChange(change, value)


class JunctionGraphicsItem(QGraphicsEllipseItem):
    """Custom interactive circle representing a Z-junction / splice node."""
    def __init__(self, node_id, x, y, diameter, label_text, canvas_ref):
        # Define local ellipse centered at (0,0)
        super().__init__(-diameter/2, -diameter/2, diameter, diameter)
        self.node_id = node_id
        self.canvas_ref = canvas_ref
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
        # Position item in scene coordinates
        self.setPos(x, y)
        
        # Soft amber fill with burnt orange border for Z splices
        self.setBrush(QBrush(QColor(253, 227, 167)))
        self.setPen(QPen(QColor(211, 84, 0), 2))
        
        self.label = QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QColor(180, 100, 0))
        self.label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        
        # Place label neatly just below the circle center
        self.label.setPos(-diameter / 2, diameter / 2 + 2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            self.canvas_ref.on_node_moved()
        return super().itemChange(change, value)


class BundleGraphicsItem(QGraphicsLineItem):
    """Custom interactive graphics item representing a physical bundle / routing pathway with upright rotated labels."""
    def __init__(self, bundle_id, start_id, end_id, length_mm, canvas_ref):
        super().__init__()
        self.bundle_id = bundle_id
        self.start_id = start_id
        self.end_id = end_id
        self.canvas_ref = canvas_ref
        
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setPen(QPen(QColor(41, 128, 185), 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        
        # Child text label for bundle ID and length
        self.label = QGraphicsTextItem(f"{bundle_id} ({length_mm}mm)", self)
        self.label.setDefaultTextColor(QColor(44, 62, 80))
        self.label.setFont(QFont("Segoe UI", 9, QFont.Bold))

    def update_endpoints(self, p1: QPointF, p2: QPointF):
        """Updates line geometry, matches bundle rotation, and normalizes angle to stay upright."""
        self.setLine(p1.x(), p1.y(), p2.x(), p2.y())
        
        mid_x = (p1.x() + p2.x()) / 2.0
        mid_y = (p1.y() + p2.y()) / 2.0
        
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        
        if length > 0:
            # Calculate angle in degrees
            angle_deg = math.degrees(math.atan2(dy, dx))
            
            # Normalize angle to the range [-90, 90] so text stays upright and readable
            if angle_deg > 90:
                angle_deg -= 180
            elif angle_deg < -90:
                angle_deg += 180
                
            self.label.setRotation(angle_deg)
            
            # Compute perpendicular normal vector for clean offset x (e.g., 14 pixels above the line)
            nx = -dy / length
            ny = dx / length
            offset_dist = 14.0
            
            # Center transformation origin for proper rotation
            self.label.setTransformOriginPoint(self.label.boundingRect().center())
            self.label.setPos(mid_x + nx * offset_dist - self.label.boundingRect().width() / 2, 
                              mid_y + ny * offset_dist - self.label.boundingRect().height() / 2)


class WireGraphicsItem(QGraphicsLineItem):
    """Custom interactive graphics item representing an electrical wire trace."""
    def __init__(self, wire_id, color_str, canvas_ref):
        super().__init__()
        self.wire_id = wire_id
        self.canvas_ref = canvas_ref
        
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        
        wire_colors = {
            "Yellow": QColor(241, 196, 15),
            "Blue/White": QColor(41, 128, 185),
            "White": QColor(0, 0, 0),
            "Red": QColor(231, 76, 60),
            "Black": QColor(44, 62, 80)
        }
        color = wire_colors.get(color_str, QColor(127, 140, 141))
        self.setPen(QPen(color, 2, Qt.DashLine))

    def update_geometry(self, p1: QPointF, p2: QPointF, offset: float):
        self.setLine(p1.x() + offset, p1.y() + offset, p2.x() + offset, p2.y() + offset)

class HarnessCADCanvas(QGraphicsView):
    """Interactive 2D vector graphics workspace for harness schematic and formboard layout[cite: 1]."""
    
    nodesMoved = pyqtSignal(dict)
    nodeDeletionRequested = pyqtSignal(str)
    tableMoved = pyqtSignal(str, dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setRenderHints(
            QPainter.Antialiasing | 
            QPainter.TextAntialiasing | 
            QPainter.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setBackgroundBrush(QBrush(QColor(240, 242, 245)))
        
        self.current_project = None
        self.node_items = {}
        self.bundle_items = {}
        self.wire_items = {}
        self.table_items = {}  # Added to track table items
        self.active_dragging_nodes = {}

    def load_topology(self, project_model: HarnessProjectModel):
        self.current_project = project_model
        self.scene.clear()
        self.node_items.clear()
        self.bundle_items.clear()
        self.wire_items.clear()
        self.table_items.clear()
        
        data = project_model.data
        
        # 1. Create Node, Junction & Attached Table Items
        for node in data.get("nodes", []):
            pos = node.get("position_2d", {"x": 0, "y": 0})
            x, y = pos["x"], pos["y"]
            label_str = f"{node.get('ref_designator')}\n{node.get('part_number')}"
            
            ref_des = node.get("ref_designator", "")
            n_id = node["node_id"]
            part_num = node.get("part_number", "")
            
            if "SPLICE" in part_num or ref_des.startswith(("Z", "J")) or "junc" in n_id or "z" in n_id.lower():
                node_item = JunctionGraphicsItem(n_id, x, y, 45, label_str, self)
                self.scene.addItem(node_item)
            else:
                node_item = NodeGraphicsItem(n_id, x, y, 90, 60, label_str, self)
                self.scene.addItem(node_item)
                
                # Add independent connector table
                table_config = node.get("table_config", {})
                if table_config.get("visible", True):
                    table_item = ConnectorTableGraphicsItem(n_id, node, project_model=project_model)
                    # Position table at Node Center + relative offset
                    offset = table_config.get("offset_2d", {"x": 50, "y": -40})
                    table_item.setPos(x + offset["x"], y + offset["y"])
                    
                    self.scene.addItem(table_item)
                    self.table_items[n_id] = table_item
                
            self.node_items[n_id] = node_item

        # 2. Create Persistent Bundle Items
        for bundle in data.get("bundles", []):
            b_item = BundleGraphicsItem(
                bundle["bundle_id"], 
                bundle["start_node_id"], 
                bundle["end_node_id"], 
                bundle["length_mm"], 
                self
            )
            self.scene.addItem(b_item)
            self.bundle_items[bundle["bundle_id"]] = b_item

        # 3. Create Persistent Wire Trace Items
        for wire in data.get("wires", []):
            w_item = WireGraphicsItem(wire["wire_id"], wire.get("color", "Black"), self)
            self.scene.addItem(w_item)
            self.wire_items[wire["wire_id"]] = w_item

        self.update_geometries()
    def keyPressEvent(self, event):
        """Handles keyboard shortcuts like Delete key on selected connectors/nodes."""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            selected_items = self.scene.selectedItems()
            for item in selected_items:
                if hasattr(item, "node_id"):
                    self.nodeDeletionRequested.emit(item.node_id)
                    event.accept()
                    return
        super().keyPressEvent(event)
    def update_geometries(self):
        if not self.current_project:
            return

        # Update bundles
        for bundle in self.current_project.data.get("bundles", []):
            b_id = bundle["bundle_id"]
            b_item = self.bundle_items.get(b_id)
            if b_item:
                s_item = self.node_items.get(bundle["start_node_id"])
                e_item = self.node_items.get(bundle["end_node_id"])
                if s_item and e_item:
                    p1 = s_item.sceneBoundingRect().center()
                    p2 = e_item.sceneBoundingRect().center()
                    b_item.update_endpoints(p1, p2)

        # Update connector tables to follow their parent nodes if not actively being dragged
        for node in self.current_project.data.get("nodes", []):
            n_id = node["node_id"]
            node_item = self.node_items.get(n_id)
            table_item = self.table_items.get(n_id)
            if node_item and table_item and not table_item.isSelected():
                node_center = node_item.sceneBoundingRect().center()
                offset = node.get("table_config", {}).get("offset_2d", {"x": 50, "y": -40})
                table_item.setPos(node_center.x() + offset["x"], node_center.y() + offset["y"])

        # Update wires
        for wire in self.current_project.data.get("wires", []):
            w_id = wire["wire_id"]
            w_item = self.wire_items.get(w_id)
            if w_item:
                routed = wire.get("routed_bundle_ids", [])
                if routed and routed[0] in self.bundle_items:
                    b_item = self.bundle_items[routed[0]]
                    line = b_item.line()
                    p1 = QPointF(line.x1(), line.y1())
                    p2 = QPointF(line.x2(), line.y2())
                    w_item.update_geometry(p1, p2, offset=-4)

    def on_node_moved(self):
        self.update_geometries()

    def highlight_entity(self, payload: dict):
        entity_type = payload.get("type")
        entity_id = payload.get("id")

        for item in self.scene.selectedItems():
            item.setSelected(False)

        if entity_type == "node":
            node_item = self.node_items.get(entity_id)
            if node_item:
                node_item.setSelected(True)
                self.centerOn(node_item)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        
        node_item = None
        if hasattr(item, 'node_id'):
            node_item = item
        elif item and hasattr(item.parentItem(), 'node_id'):
            node_item = item.parentItem()
        
        if node_item:
            if not (event.modifiers() & Qt.ControlModifier):
                for sel in self.scene.selectedItems():
                    if sel != node_item:
                    # Check if sel has node_id attribute before calling setSelected
                        if hasattr(sel, 'node_id'):
                            sel.setSelected(False)
                node_item.setSelected(True)

            self.active_dragging_nodes = {}
            for sel in self.scene.selectedItems():
                if hasattr(sel, 'node_id'):
                    center = sel.sceneBoundingRect().center()
                    self.active_dragging_nodes[sel.node_id] = {"x": center.x(), "y": center.y()}
        else:
            if not (event.modifiers() & Qt.ControlModifier):
                for sel in self.scene.selectedItems():
                    if hasattr(sel, 'node_id'):
                        sel.setSelected(False)
            self.active_dragging_nodes = {}

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        
        if hasattr(self, 'active_dragging_nodes') and self.active_dragging_nodes:
            moved_data = {}
            for node_id, old_pos in self.active_dragging_nodes.items():
                item = self.node_items.get(node_id)
                if item:
                    center = item.sceneBoundingRect().center()
                    new_pos = {"x": center.x(), "y": center.y()}
                    
                    if old_pos["x"] != new_pos["x"] or old_pos["y"] != new_pos["y"]:
                        moved_data[node_id] = new_pos
            
            if moved_data:
                self.nodesMoved.emit(moved_data)
            
            self.active_dragging_nodes = {}

    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)