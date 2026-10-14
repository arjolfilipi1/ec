from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem
from PyQt5.QtCore import Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QBrush, QColor, QFont, QWheelEvent, QPainter
from models.harness_model import HarnessProjectModel

class NodeGraphicsItem(QGraphicsRectItem):
    """Custom interactive rectangle representing a connector node on the canvas."""
    def __init__(self, node_id, x, y, width, height, label_text, canvas_ref):
        super().__init__(x - width/2, y - height/2, width, height)
        self.node_id = node_id
        self.canvas_ref = canvas_ref
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(QColor(52, 73, 94), 2))
        
        self.label = QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QColor(41, 128, 185))
        self.label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.label.setPos(x - width/2 + 5, y - height/2 + 5)
        
        # Track start position for undo/redo dragging
        self.drag_start_pos = {"x": x, "y": y}

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            self.canvas_ref.on_node_moved()
        return super().itemChange(change, value)

class HarnessCADCanvas(QGraphicsView):
    """Interactive 2D vector graphics workspace for harness schematic and formboard layout."""
    
    nodeDragFinished = pyqtSignal(str, dict, dict)  # Emits (node_id, old_pos, new_pos)

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
        self.active_dragging_node = None

    def load_topology(self, project_model: HarnessProjectModel):
        self.current_project = project_model
        self.scene.clear()
        self.node_items.clear()
        
        data = project_model.data
        for node in data.get("nodes", []):
            pos = node.get("position_2d", {"x": 0, "y": 0})
            x, y = pos["x"], pos["y"]
            
            label_str = f"{node.get('ref_designator')}\n{node.get('part_number')}"
            node_item = NodeGraphicsItem(node["node_id"], x, y, 90, 60, label_str, self)
            self.scene.addItem(node_item)
            self.node_items[node["node_id"]] = node_item

        self.draw_bundles()

    def draw_bundles(self):
        for item in list(self.scene.items()):
            if isinstance(item, (QGraphicsRectItem, NodeGraphicsItem)) is False:
                self.scene.removeItem(item)

        if not self.current_project:
            return

        bundle_pen = QPen(QColor(41, 128, 185), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

        for bundle in self.current_project.data.get("bundles", []):
            start_id = bundle.get("start_node_id")
            end_id = bundle.get("end_node_id")
            
            if start_id in self.node_items and end_id in self.node_items:
                item_start = self.node_items[start_id]
                item_end = self.node_items[end_id]
                
                p1 = item_start.sceneBoundingRect().center()
                p2 = item_end.sceneBoundingRect().center()
                
                self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), bundle_pen)
                
                mid_x, mid_y = (p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0
                text_item = QGraphicsTextItem(f"{bundle['bundle_id']} ({bundle['length_mm']}mm)")
                text_item.setDefaultTextColor(QColor(44, 62, 80))
                text_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                text_item.setPos(mid_x + 10, mid_y - 15)
                self.scene.addItem(text_item)

    def on_node_moved(self):
        self.draw_bundles()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        if isinstance(item, NodeGraphicsItem):
            self.active_dragging_node = (item.node_id, {"x": item.sceneBoundingRect().center().x(), "y": item.sceneBoundingRect().center().y()})

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.active_dragging_node:
            node_id, old_pos = self.active_dragging_node
            item = self.node_items.get(node_id)
            if item:
                center = item.sceneBoundingRect().center()
                new_pos = {"x": center.x(), "y": center.y()}
                
                # Only push command if position actually changed
                if old_pos["x"] != new_pos["x"] or old_pos["y"] != new_pos["y"]:
                    self.nodeDragFinished.emit(node_id, old_pos, new_pos)
            
            self.active_dragging_node = None

    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)