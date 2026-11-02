from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem,
                                QGraphicsLineItem,QGraphicsEllipseItem,QGraphicsItemGroup,QStyle,QLineEdit,
                                 QMenu, QInputDialog, QMessageBox,QDialog)
from PyQt5.QtCore import Qt, QPointF, pyqtSignal,QPoint
from PyQt5.QtGui import QPen, QBrush, QColor, QFont, QWheelEvent, QPainter,QPixmap,QTransform
from models.harness_model import HarnessProjectModel
import math
from copy import deepcopy
from database import DatabaseManager
from commands.harness_commands import MergeCommand
from ui.bundle_dialog import BundlePropertiesDialog
class BundlePatternFactory:
    """Generates seamlessly repeating pixmap patterns for harness bundle covering"""

    @staticmethod
    def create_corrugated_pattern(color_hex="#2C3E50", rib_color_hex="#7F8C8D"):
        """Generates a ribbed/corrugated texture pixmap.""" 
        pixmap = QPixmap(12, 20) 
        pixmap.fill(QColor(color_hex))

        painter = QPainter(pixmap)
        # Draw ribbed highlights/shadows 
        painter.setPen(QPen(QColor(rib_color_hex), 2)) 
        painter.drawLine(3, 0, 3, 20) 
        painter.setPen(QPen(QColor("#1A252F"), 2)) 
        painter.drawLine(9, 0, 9, 20)
        painter.end()

        return QBrush(pixmap)

    @staticmethod
    def create_pvc_pattern(color_hex="#34495E") -> QBrush:
        """Generates a smooth PVC sleeving texture."""
        pixmap = QPixmap(16, 16) 
        pixmap.fill(QColor(color_hex))

        painter = QPainter(pixmap)
        # Subtle longitudinal sheen lines 
        painter.setPen(QPen(QColor("#5D6D7E"), 1)) 
        painter.drawLine(0, 4, 16, 4) 
        painter.end()

        return QBrush(pixmap)

    @staticmethod
    def create_tape_pattern(color_hex="#1C2833") -> QBrush:
        """Generates a diagonal spiraled tape wrap texture.""" 
        pixmap = QPixmap(16, 16) 
        pixmap.fill(QColor(color_hex))

        painter = QPainter(pixmap) 
        painter.setPen(QPen(QColor("#566573"), 1.5)) 
        # Spiral wrap lines
        painter.drawLine(0, 16, 16, 0)
        painter.end()

        return QBrush(pixmap)

class ConnectorTableGraphicsItem(QGraphicsRectItem):
    """Visual table attached to a connector or splice junction node displaying pin/wire mappings and sides."""
    
    def __init__(self, node_id: str, node_data: dict, project_model=None):
        super().__init__()
        self.node_id = node_id
        self.node_data = node_data
        self.project_model = project_model
        
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
        self.refresh_layout()

    def refresh_layout(self):
        """Redraws table headers and maps wire endpoints/sides to rows with safe fallbacks and geometric left/right splice orientation."""
        for child in self.childItems():
            if child.scene():
                child.scene().removeItem(child)

        config = self.node_data.get("table_config", {})
        ref_des = self.node_data.get("ref_designator", "X")
        part_num = self.node_data.get("part_number", "")
        node_id = self.node_data.get("node_id")
        
        # Explicit boolean check instead of string matching
        is_junction = self.node_data.get("is_junction", False)
        # Define columns based on node type
        columns = config.get("columns", [])
        if not columns:
            if is_junction:
                columns = [
                    {"id": "cavity_id", "label": "Port", "width": 50},
                    {"id": "side", "label": "Side", "width": 70},
                    {"id": "signal", "label": "Signal", "width": 70},
                    {"id": "wire_id", "label": "Wire", "width": 60},
                    {"id": "color", "label": "Color", "width": 45}
                ]
            else:
                columns = [
                    {"id": "cavity", "label": "Cav", "width": 35},
                    {"id": "pin", "label": "Pin", "width": 35},
                    {"id": "signal", "label": "Signal", "width": 70},
                    {"id": "wire_id", "label": "Wire", "width": 60},
                    {"id": "color", "label": "Color", "width": 45}
                ]
        row_data_list = []
        if is_junction:
            row_data_list = []
        row_data_list = []
        if is_junction:
            node_id = self.node_data.get("node_id")
            node_pos = self.node_data.get("position_2d", {"x": 0, "y": 0})
            jx = node_pos.get("x", 0)

            node_map = {}
            if self.project_model:
                node_map = {n["node_id"]: n for n in self.project_model.data.get("nodes", [])}
                
                for w in self.project_model.data.get("wires", []):
                    endpoints = w.get("endpoints", [])
                    
                    # STRICT CHECK: Only include wires connected directly to this splice endpoint
                    is_endpoint = False
                    junction_cavity = "X"  # Standard default splice cavity designation
                    
                    for ep in endpoints:
                        if ep.get("node_id") == node_id:
                            is_endpoint = True
                            # Retrieve the cavity/pin designation if defined (e.g. "X", "1", "A")
                            junction_cavity = ep.get("cavity_id", "X")
                            break
                    
                    if is_endpoint:
                        # Determine Left or Right side based on the other endpoint node's X position
                        assigned_side = "Unknown"
                        for ep in endpoints:
                            other_node_id = ep.get("node_id")
                            if other_node_id and other_node_id != node_id and other_node_id in node_map:
                                o_pos = node_map[other_node_id].get("position_2d", {"x": 0, "y": 0})
                                assigned_side = "Left" if o_pos.get("x", 0) < jx else "Right"
                                break
                        
                        row_data_list.append({
                            "cavity_id": junction_cavity, # Displays proper cavity/pin designation ("X")
                            "side": assigned_side,
                            "signal": w.get("signal_name", ""),
                            "wire_id": w.get("wire_id", ""),
                            "color": w.get("color", "")
                        })

            if not row_data_list:
                row_data_list = [{"cavity_id": "-", "side": "-", "signal": "No Wires", "wire_id": "-", "color": "-"}]
        else:
            pins = self.node_data.get("pins", [])
            if not pins:
                pins = [{"cavity_id": "1", "pin_number": "1"}, {"cavity_id": "2", "pin_number": "2"}]
            
            wire_map = {}
            if self.project_model:
                for w in self.project_model.data.get("wires", []):
                    for ep in w.get("endpoints", []):
                        if ep.get("node_id") == node_id:
                            wire_map.setdefault(ep.get("cavity_id"), []).append(w)

            for pin in pins:
                cav_id = pin.get("cavity_id", "1")
                pin_num = pin.get("pin_number", cav_id)
                connected_wires = wire_map.get(cav_id, [])
                row_data_list.append({
                    "cavity": cav_id,
                    "pin": pin_num,
                    "signal": " / ".join([w.get("signal_name", "") for w in connected_wires if w.get("signal_name")]),
                    "wire_id": " / ".join([w.get("wire_id", "") for w in connected_wires]),
                    "color": " / ".join([w.get("color", "") for w in connected_wires if w.get("color")])
                })

        # Header Title (Connector / Junction Name)
        header_text = QGraphicsTextItem(ref_des, self)
        header_text.setDefaultTextColor(QColor(180, 100, 0) if is_junction else QColor(41, 128, 185))
        header_text.setFont(QFont("Segoe UI", 9, QFont.Bold))
        header_text.setPos(-5, -20)

        total_width = sum(col.get("width", 50) for col in columns)
        row_height = 18
        header_height = 22
        total_height = header_height + (len(row_data_list) * row_height)
        
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

        # Draw Data Rows
        for row_idx, row_item in enumerate(row_data_list):
            y_pos = header_height + (row_idx * row_height)
            current_x = 0
            for col in columns:
                col_id = col.get("id")
                col_width = col.get("width", 50)
                
                val = str(row_item.get(col_id, ""))
                if val:
                    cell_text = QGraphicsTextItem(val, self)
                    cell_text.setFont(QFont("Segoe UI", 8))
                    cell_text.setDefaultTextColor(QColor(44, 62, 80))
                    cell_text.setPos(current_x + 2, y_pos)
                
                current_x += col_width
    def mousePressEvent(self, event):
        self.initial_scene_pos = self.scenePos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        new_scene_pos = self.scenePos()
        
        if new_scene_pos != self.initial_scene_pos:
            canvas = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if canvas and self.node_id in canvas.node_items:
                node_item = canvas.node_items[self.node_id]
                node_center = node_item.sceneBoundingRect().center()
                
                rel_x = new_scene_pos.x() - node_center.x()
                rel_y = new_scene_pos.y() - node_center.y()
                
                if hasattr(canvas, "tableMoved"):
                    canvas.tableMoved.emit(self.node_id, {"x": round(rel_x, 1), "y": round(rel_y, 1)})
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
        self._current_angle = 0.0
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            self.canvas_ref.on_node_moved()
        return super().itemChange(change, value)
    def set_branch_rotation(self, angle: float):
        """Sets the full rotation for the connector body, while capping the label rotation to +/- 90 degrees."""
        self._current_angle = angle
        # 1. Rotate the connector body fully
        super().setRotation(angle)
        
        # 2. Counter-rotate/cap the label so text remains readable (between -90 and +90 degrees)
        normalized_angle = angle % 360
        if normalized_angle < 0:
            normalized_angle += 360
            
        label_correction = 0.0
        if 90 < normalized_angle <= 270:
            label_correction = 180.0
        elif 270 < normalized_angle < 360:
            label_correction = 0.0
            
        # Apply counter-rotation to keep text upright
        self.label.setRotation( label_correction)

class JunctionGraphicsItem(QGraphicsEllipseItem):
    """Custom interactive circle representing a Z-junction / splice node with merge-on-drag capabilities."""
    def __init__(self, node_id, x, y, diameter, label_text, canvas_ref):
        super().__init__(-diameter/2, -diameter/2, diameter, diameter)
        self.node_id = node_id
        self.canvas_ref = canvas_ref
        self.diameter = diameter
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
        self.setPos(x, y)
        
        # Default styling: Soft amber fill with burnt orange border
        self.default_pen = QPen(QColor(211, 84, 0), 2)
        # Highlight styling: Green outline indicating a valid merge target
        self.highlight_pen = QPen(QColor(46, 204, 113), 3, Qt.SolidLine)
        
        self.setBrush(QBrush(QColor(253, 227, 167)))
        self.setPen(self.default_pen)
        
        self.label = QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QColor(180, 100, 0))
        self.label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.label.setPos(-diameter / 2, diameter / 2 + 2)

        # Active merge targets tracked during drag
        self.target_node_id = None
        self.target_bundle_id = None
        self.proj_point = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            if self.canvas_ref:
                self.canvas_ref.on_node_moved()
        return super().itemChange(change, value)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._check_merge_targets()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        
        # Execute the merge (which may delete this item during canvas refresh)
        try:
            self._execute_merge()
        except RuntimeError:
            return  # Item was deleted during merge; exit safely

        # Reset visual state only if the item still exists in the scene
        try:
            if self.scene():
                self.setPen(self.default_pen)
                self.target_node_id = None
                self.target_bundle_id = None
        except RuntimeError:
            pass

    def _check_merge_targets(self):
        """Checks proximity to other junction nodes or bundle segments for potential merging."""
        if not self.canvas_ref or not hasattr(self.canvas_ref, "current_project"):
            return

        model = self.canvas_ref.current_project
        data = getattr(model, "data", {})
        pos = self.pos()
        px, py = pos.x(), pos.y()

        threshold = 50  # Proximity radius in pixels
        self.target_node_id = None
        self.target_bundle_id = None
        self.proj_point = None

        node_map = {n["node_id"]: n for n in data.get("nodes", [])}

        # 1. Check proximity to other junction nodes
        for n_id, node in node_map.items():
            if n_id == self.node_id:
                continue
            n_pos = node.get("position_2d", {"x": 0, "y": 0})
            dist = math.sqrt((px - n_pos["x"])**2 + (py - n_pos["y"])**2)
            if dist < threshold:
                self.target_node_id = n_id
                break

        # 2. If no node target, check proximity to bundle segments
        if not self.target_node_id:
            for b in data.get("bundles", []):
                # Exclude bundles that start or end at this junction node
                if b.get("start_node_id") == self.node_id or b.get("end_node_id") == self.node_id:
                    continue

                u_n = node_map.get(b.get("start_node_id"))
                v_n = node_map.get(b.get("end_node_id"))
                if not u_n or not v_n:
                    continue

                ux, uy = u_n["position_2d"]["x"], u_n["position_2d"]["y"]
                vx, vy = v_n["position_2d"]["x"], v_n["position_2d"]["y"]

                # Point-to-segment distance calculation
                dx, dy = vx - ux, vy - uy
                len_sq = dx*dx + dy*dy
                if len_sq == 0:
                    continue

                t = max(0.0, min(1.0, ((px - ux) * dx + (py - uy) * dy) / len_sq))
                cx, cy = ux + t * dx, uy + t * dy
                dist = math.sqrt((px - cx)**2 + (py - cy)**2)

                if dist < threshold:
                    self.target_bundle_id = b.get("bundle_id")
                    self.proj_point = (cx, cy)
                    break

        # Apply visual feedback (Green outline if a target is found)
        if self.target_node_id or self.target_bundle_id:
            self.setPen(self.highlight_pen)
        else:
            self.setPen(self.default_pen)

    def _execute_merge(self):
        """Executes the node-to-node or node-to-bundle merge upon mouse release."""
        if not self.canvas_ref or not hasattr(self.canvas_ref, "current_project"):
            return

        model = self.canvas_ref.current_project
        # 1. Snapshot state before merge
        old_data = deepcopy(model.data)
        # 2. Perform the merge operation
        if self.target_node_id:
            model.merge_nodes(self.node_id, self.target_node_id)
            desc = f"Merge Junction {self.node_id} into {self.target_node_id}"
        elif self.target_bundle_id and self.proj_point:
            model.merge_node_into_bundle(self.node_id, self.target_bundle_id, self.proj_point[0], self.proj_point[1])
            desc = f"Snap Junction {self.node_id} into Bundle {self.target_bundle_id}"
        else:
            return
        # 3. Snapshot state after merge
        new_data = deepcopy(model.data)
        undo_stack=self.canvas_ref.main_window.undo_stack
        command = MergeCommand(model, old_data, new_data, self.canvas_ref.re_load_topology, description=desc)
        undo_stack.push(command)
        # Refresh the canvas display
        if hasattr(self.canvas_ref, "refresh_canvas"):
            self.canvas_ref.refresh_canvas()
        elif hasattr(self.canvas_ref, "update"):
            self.canvas_ref.update()
        
class BundleGraphicsItem(QGraphicsLineItem):
    """Custom interactive bundle with branch length label, inline editing, and pen-based selection highlight."""
    
    def __init__(self, bundle_id, start_pos, end_pos, bundle_data: dict, canvas_ref):
        super().__init__()
        self.bundle_id = bundle_id
        self.bundle_data = bundle_data
        self.canvas_ref = canvas_ref
        self.editor = None
        
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setLine(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y())
        
        # Calculate angle for pattern transformation
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        self.angle_deg = math.degrees(math.atan2(dy, dx))
        
        # Create branch length label (shows length only)
        length = self.bundle_data.get("length_mm", 0.0)
        self.label_item = QGraphicsTextItem(f"{length:.1f} mm", self)
        self.label_item.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.label_item.setDefaultTextColor(QColor(44, 62, 80))
        
        # Position label at midpoint of the line
        self._update_label_position()
        self.update_covering_style()
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)

    def contextMenuEvent(self, event):
        """Displays the right-click context menu for bundle options."""
        menu = QMenu()
        
        break_action = menu.addAction("Break Bundle")
        edit_len_action = menu.addAction("Edit Length...")
        props_action = menu.addAction("Properties...")
        highlight_action = menu.addAction("Highlight Connections")
        
        # Execute menu at cursor screen position
        action = menu.exec_(event.screenPos())
        
        if action == break_action:
            self._break_bundle(event.scenePos())
        elif action == edit_len_action:
            self._edit_length()
        elif action == props_action:
            self._show_properties()
        elif action == highlight_action:
            self._highlight_connections()

    def _break_bundle(self, scene_pos: QPointF):
        """Breaks the bundle at the clicked scene position by inserting a new Z-junction."""
        if not self.canvas_ref or not hasattr(self.canvas_ref, "current_project"):
            return
            
        model = self.canvas_ref.current_project
        junction_ref, ok = QInputDialog.getText(
            None, "Break Bundle", "Enter Junction Reference (e.g., J3):", text="J3"
        )
        if ok and junction_ref:
            model.break_bundle(self.bundle_id, junction_ref, scene_pos.x(), scene_pos.y())
            # Refresh the canvas display
            self.canvas_ref.load_topology(model)

    def _edit_length(self):
        """Opens an input dialog to modify the physical length of the bundle."""
        if not self.canvas_ref or not hasattr(self.canvas_ref, "current_project"):
            return
            
        model = self.canvas_ref.current_project
        bundles = model.data.get("bundles", model.data.get("branches", []))
        bundle_data = next((b for b in bundles if (b.get("bundle_id") or b.get("branch_id") or b.get("id")) == self.bundle_id), None)
        
        if not bundle_data:
            return
            
        current_len = bundle_data.get("length_mm", 0.0)
        new_len, ok = QInputDialog.getDouble(
            None, "Edit Bundle Length", f"Length for {self.bundle_id} (mm):", 
            value=current_len, min=0.0, max=10000.0, decimals=1
        )
        
        if ok:
            bundle_data["length_mm"] = new_len
            # Refresh the canvas display
            self.canvas_ref.load_topology(model)

    def _show_properties(self):
        """Opens the full BundlePropertiesDialog for editing bundle length and coverings."""
        if not self.canvas_ref or not hasattr(self.canvas_ref, "current_project"):
            return
            
        model = self.canvas_ref.current_project
        bundles = model.data.get("bundles", [])
        bundle_data = next((b for b in bundles if (b.get("bundle_id") or b.get("branch_id") or b.get("id")) == self.bundle_id), None)
        
        if not bundle_data:
            return
            
        # Open the full BundlePropertiesDialog modal
        dialog = BundlePropertiesDialog(bundle_data, parent=None)
        if dialog.exec_() == QDialog.Accepted:
            # Save project data changes and refresh canvas upon confirmation
            # DatabaseManager.save_project(model.data)
            self.canvas_ref.re_load_topology()
            

    def _highlight_connections(self):
        """Highlights all wires whose routed paths traverse this bundle segment."""
        if not self.canvas_ref or not hasattr(self.canvas_ref, "current_project"):
            return
            
        model = self.canvas_ref.current_project
        wires = model.data.get("wires", [])
        
        for w in wires:
            routed = w.get("routed_bundle_ids", [])
            # Toggle highlight on if bundle is in route, off otherwise (or set true for matching)
            if self.bundle_id in routed:
                w["is_highlighted"] = True
            else:
                w["is_highlighted"] = False
                
        self.canvas_ref.load_topology(model)

        self.canvas_ref.main_window.wires_tab.refresh_wires()


    def update_covering_style(self):
        """Applies normal covering styles and saves base pen."""
        coverings = self.bundle_data.get("coverings", [])
        line_width = 8
        base_color = QColor(127, 140, 141)
        pen = QPen(base_color, line_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        
        if coverings:
            primary_cov = coverings[0].get("part_number", "").upper()
            pattern_transform = QTransform().rotate(self.angle_deg)
            
            if "CORR" in primary_cov:
                line_width = 14
                brush = BundlePatternFactory.create_corrugated_pattern()
                brush.setTransform(pattern_transform)
                pen = QPen(brush, line_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            elif "SLV" in primary_cov or "PVC" in primary_cov:
                line_width = 11
                brush = BundlePatternFactory.create_pvc_pattern()
                brush.setTransform(pattern_transform)
                pen = QPen(brush, line_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            elif "TAPE" in primary_cov:
                line_width = 9
                brush = BundlePatternFactory.create_tape_pattern()
                brush.setTransform(pattern_transform)
                pen = QPen(brush, line_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

        self.base_pen = pen
        self.setPen(pen)

    def paint(self, painter, option, widget=None):
        """Suppresses the default dotted selection box and highlights via branch pen."""
        # Remove State_Selected so Qt doesn't draw the dotted bounding rectangle
        option.state &= ~QStyle.State_Selected
        
        if self.isSelected():
            # Highlight branch with a glowing accent pen when selected
            highlight_pen = QPen(QColor(41, 128, 185), self.base_pen.width() + 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(highlight_pen)
            painter.drawLine(self.line())
            
        super().paint(painter, option, widget)

    def mouseDoubleClickEvent(self, event):
        """Opens an inline QLineEdit text input right over the canvas to edit branch length."""
        if self.canvas_ref and hasattr(self.canvas_ref, "mapFromScene"):
            # Map the mouse scene position directly to view coordinates
            view_pos = self.canvas_ref.mapFromScene(event.scenePos())
            self._open_inline_editor(self.canvas_ref, view_pos)
        super().mouseDoubleClickEvent(event)

    def _update_label_position(self):
        """Positions the label at the midpoint, offset perpendicularly so it sits cleanly above the bundle."""
        p1 = self.line().p1()
        p2 = self.line().p2()
        mid_x = (p1.x() + p2.x()) / 2
        mid_y = (p1.y() + p2.y()) / 2
        
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        
        width = self.label_item.document().idealWidth()
        height = self.label_item.document().size().height()
        
        if length > 1e-5:
            # Calculate perpendicular normal vector (nx, ny)
            nx = -dy / length
            ny = dx / length
            
            # Offset distance in pixels above the bundle line
            offset = -16.0
            pos_x = mid_x + (nx * offset) - (width / 2)
            pos_y = mid_y + (ny * offset) - (height / 2)
        else:
            pos_x = mid_x - (width / 2)
            pos_y = mid_y - (height / 2)
            
        self.label_item.setPos(pos_x, pos_y)

    def _open_inline_editor(self, parent_widget, view_pos):
        if self.editor is not None:
            self.editor.deleteLater()
            
        self.editor = QLineEdit(parent_widget)
        current_len = self.bundle_data.get("length_mm", 0.0)
        self.editor.setText(str(current_len))
        self.editor.setGeometry(int(view_pos.x() - 45), int(view_pos.y() - 15), 90, 26)
        self.editor.setStyleSheet("background: white; border: 2px solid #3498db; border-radius: 4px; font-weight: bold;")
        self.editor.show()
        self.editor.setFocus()
        self.editor.selectAll()
        
        def commit_length():
            try:
                new_val = float(self.editor.text().strip())
                self.bundle_data["length_mm"] = new_val
                self.label_item.setPlainText(f"{new_val:.1f} mm")
                
                # Re-center cleanly using synchronous ideal width
                self._update_label_position()
                
            except ValueError:
                pass
            if self.editor:
                self.editor.deleteLater()
                self.editor = None
                
        self.editor.editingFinished.connect(commit_length)
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
                
            self.label_item.setRotation(angle_deg)
            
            # Compute perpendicular normal vector for clean offset x (e.g., 14 pixels above the line)
            nx = -dy / length
            ny = dx / length
            offset_dist = 14.0
            
            # Center transformation origin for proper rotation
            self.label_item.setTransformOriginPoint(self.label_item.boundingRect().center())
            self.label_item.setPos(mid_x + nx * offset_dist - self.label_item.boundingRect().width() / 2, 
                              mid_y + ny * offset_dist - self.label_item.boundingRect().height() / 2)


class WireGraphicsItem(QGraphicsItemGroup):
    """Custom interactive graphics item representing an electrical wire trace with base and stripe colors."""
    def __init__(self, wire_id, color_code, stripe_code, canvas_ref):
        super().__init__()
        self.wire_id = wire_id
        self.canvas_ref = canvas_ref
        
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        
        # Fetch color map from database
        color_map = {c['code']: c['hex_value'] for c in DatabaseManager.get_colors()}
        
        base_hex = color_map.get(str(color_code).upper(), "#7F8C8D")
        stripe_hex = color_map.get(str(stripe_code).upper(), "") if stripe_code else ""

        # Primary base line
        self.base_line = QGraphicsLineItem()
        self.base_line.setPen(QPen(QColor(base_hex), 3, Qt.SolidLine))
        self.addToGroup(self.base_line)

        # Secondary stripe overlay line (if dual-color is specified)
        if stripe_hex:
            self.stripe_line = QGraphicsLineItem()
            # Render stripe as a dashed contrasting center line
            self.stripe_line.setPen(QPen(QColor(stripe_hex), 1.5, Qt.DashLine))
            self.addToGroup(self.stripe_line)
        else:
            self.stripe_line = None

    def update_geometry(self, p1: QPointF, p2: QPointF, offset: float):
        ox1 = p1.x() + offset
        oy1 = p1.y() + offset
        ox2 = p2.x() + offset
        oy2 = p2.y() + offset
        
        self.base_line.setLine(ox1, oy1, ox2, oy2)
        if self.stripe_line:
            self.stripe_line.setLine(ox1, oy1, ox2, oy2)

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
        # Enable anti-aliasing and smooth rendering
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.main_window = parent
        # Panning state variables
        self._panning = False
        self._pan_start_pos = QPoint()
        
        self.current_project = None
        self.node_items = {}
        self.bundle_items = {}
        self.wire_items = {}
        self.table_items = {}  # Added to track table items
        self.active_dragging_nodes = {}
    def re_load_topology(self):
        self.load_topology(self.current_project)
        self.update()
    def load_topology(self, current_project: HarnessProjectModel):
        self.current_project = current_project
        self.scene.clear()
        self.node_items.clear()
        self.bundle_items.clear()
        self.wire_items.clear()
        self.table_items.clear()
        
        data = current_project.data
        
        # 1. Create Node, Junction & Attached Table Items
        for node in data.get("nodes", []):
            pos = node.get("position_2d", {"x": 0, "y": 0})
            x, y = pos["x"], pos["y"]
            label_str = f"{node.get('ref_designator')}\n{node.get('part_number')}"
            
            n_id = node["node_id"]
            is_junction = node.get("is_junction", False) # Clean explicit boolean check
            node_map = {n["node_id"]: n for n in data.get("nodes", [])}
            node_angle = 0.0
            if not is_junction:
                connected_bundles = [
                    b for b in data.get("bundles", []) 
                    if b.get("start_node_id") == n_id or b.get("end_node_id") == n_id
                ]
                if connected_bundles:
                    # Take the first connected bundle to determine branch angle
                    b = connected_bundles[0]
                    s_id = b.get("start_node_id")
                    e_id = b.get("end_node_id")
                    
                    if s_id in node_map and e_id in node_map:
                        sp = node_map[s_id].get("position_2d", {"x": 0, "y": 0})
                        ep = node_map[e_id].get("position_2d", {"x": 0, "y": 0})
                        
                        dx = ep["x"] - sp["x"]
                        dy = ep["y"] - sp["y"]
                        
                        # Calculate angle in degrees
                        rad = math.atan2(dy, dx)
                        node_angle = math.degrees(rad)
                        
                        # If this node is the end node of the bundle, point outward (add 180 deg)
                        if e_id == n_id:
                            node_angle += 180.0

            if is_junction:
                node_item = JunctionGraphicsItem(n_id, x, y, 45, label_str, self)
                self.scene.addItem(node_item)
            else:
                node_item = NodeGraphicsItem(n_id, x, y, 90, 60, label_str, self)
                node_item.set_branch_rotation(node_angle)  # Align connector rotation with branch angle!
                self.scene.addItem(node_item)
                
            # Table items and positioning logic follows...
            table_config = node.get("table_config", {})
            show_table = table_config.get("visible", True)
            
            if is_junction and current_project:
                wire_count = sum(1 for w in data.get("wires", []) for ep in w.get("endpoints", []) if ep.get("node_id") == n_id)
                if wire_count == 0:
                    show_table = False

            if show_table:
                table_item = ConnectorTableGraphicsItem(n_id, node, project_model=current_project)
                offset = table_config.get("offset_2d", {"x": 50, "y": -40})
                table_item.setPos(x + offset["x"], y + offset["y"])
                self.scene.addItem(table_item)
                self.table_items[n_id] = table_item
                
            self.node_items[n_id] = node_item

        # 2. Create Persistent Bundle Items
        for bundle in data.get("bundles", []):
            
            b_id = bundle["bundle_id"]
            s_id = bundle["start_node_id"]
            e_id = bundle["end_node_id"]
            
            if s_id in node_map and e_id in node_map:
                sp_data = node_map[s_id].get("position_2d", {"x": 0, "y": 0})
                ep_data = node_map[e_id].get("position_2d", {"x": 0, "y": 0})
                
                sp = QPointF(sp_data["x"], sp_data["y"])
                ep = QPointF(ep_data["x"], ep_data["y"])
                
                b_item = BundleGraphicsItem(
                    b_id,
                    sp,
                    ep,
                    bundle,  # Passes the full bundle dictionary so coverings and styling can be read
                    self
                )
                self.scene.addItem(b_item)
                self.bundle_items[b_id] = b_item

        # 3. Create Persistent Wire Trace Items
        for wire in data.get("wires", []):
            w_id = wire["wire_id"]
            base_col = wire.get("color", "BK")
            stripe_col = wire.get("stripe_color", "")
            
            w_item = WireGraphicsItem(w_id, base_col, stripe_col, self)
            self.scene.addItem(w_item)
            self.wire_items[w_id] = w_item

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
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
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
    def mouseMoveEvent(self, event):
        """Handles dragging motion while the middle mouse button is held down."""
        if self._panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            
            # Adjust scrollbar values to pan the view
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            
            event.accept()
            return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event):
        """Restores cursor and ends panning state when middle mouse button is released."""
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
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
    def draw_highlighted_wires(self, painter: QPainter):
        """Renders highlighted wires directly along their stored routed_bundle_ids."""
        if not self.current_project or not hasattr(self.current_project, "data"):
            return
            
        data = self.current_project.data
        wires = data.get("wires", [])
        
        # Build a quick lookup dictionary for nodes and bundles
        nodes = {n.get("node_id"): n for n in data.get("nodes", [])}
        # Support both 'bundles' or 'branches' key variants depending on your schema
        bundles = {b.get("bundle_id") or b.get("branch_id") or b.get("id"): b for b in data.get("bundles", data.get("branches", []))}
        
        # Filter for currently highlighted wires
        highlighted_wires = [w for w in wires if w.get("is_highlighted", False)]
        if not highlighted_wires:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        for wire_idx, wire in enumerate(highlighted_wires):
            routed_bundle_ids = wire.get("routed_bundle_ids", [])
            if not routed_bundle_ids:
                continue
                
            color_code = wire.get("color", "BK")
            stripe_code = wire.get("stripe_code", "")
            base_hex = self._get_color_hex(color_code)
            stripe_hex = self._get_color_hex(stripe_code) if stripe_code else None
            
            base_color = QColor(base_hex)
            
            # Make the wire thick enough to stand out over bundles (e.g., width 6)
            pen_width = 6.0
            pen = QPen(base_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            if stripe_hex:
                pen.setStyle(Qt.DashLine)

            for bundle_id in routed_bundle_ids:
                bundle = bundles.get(bundle_id)
                if not bundle:
                    continue
                    
                u = bundle.get("start_node_id") or bundle.get("from_node")
                v = bundle.get("end_node_id") or bundle.get("to_node")
                
                if u not in nodes or v not in nodes:
                    continue
                    
                pt1 = self._get_node_position(nodes[u])
                pt2 = self._get_node_position(nodes[v])
                
                offset_vector = self._calculate_parallel_offset(pt1, pt2, wire_idx)
                
                # 1. Draw a contrasting outer halo (e.g., white or dark border) so it stands out against any bundle style
                halo_pen = QPen(QColor(255, 255, 255), pen_width + 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(halo_pen)
                painter.drawLine(pt1 + offset_vector, pt2 + offset_vector)
                
                # 2. Draw the actual wire on top
                painter.setPen(pen)
                painter.drawLine(pt1 + offset_vector, pt2 + offset_vector)

        painter.restore()

    def _get_node_position(self, node_dict: dict) -> QPointF:
        pos = node_dict.get("position_2d", {})
        x = pos.get("x", node_dict.get("x", 0.0))
        y = pos.get("y", node_dict.get("y", 0.0))
        return QPointF(x, y)

    def _calculate_parallel_offset(self, pt1: QPointF, pt2: QPointF, index: int) -> QPointF:
        if index == 0:
            return QPointF(0, 0)
        
        dx = pt2.x() - pt1.x()
        dy = pt2.y() - pt1.y()
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length == 0:
            return QPointF(0, 0)
            
        nx = -dy / length
        ny = dx / length
        spacing = 3.0
        multiplier = ((index + 1) // 2) * (1 if index % 2 != 0 else -1)
        
        return QPointF(nx * spacing * multiplier, ny * spacing * multiplier)

    def _get_color_hex(self, code: str) -> str:
        try:
            colors = DatabaseManager.get_colors()
            for col in colors:
                print(col.get("code"),code,col.get("code")==code)
                if col.get("code") == code:
                    h = col.get("hex") or col.get("hex_value")
                    if h:
                        print("found ",code)
                        return h
        except Exception as e:
            print(str(e))
            pass
            
        mapping = {
            "BK": "#1a1a1a"
        }
        def_code = mapping.get(code.upper(), "#7F7F7F")
        print("not found",code)
        return def_code
    def drawForeground(self, painter: QPainter, rect):
        """Automatically transformed to Scene coordinates by QGraphicsView."""
        super().drawForeground(painter, rect)
        self.draw_highlighted_wires(painter)
    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)