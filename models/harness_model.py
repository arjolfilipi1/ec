import json
import math
from collections import deque
from typing import List, Dict, Optional
import uuid
class HarnessProjectModel:
    """Manages the hierarchical in-memory representation of a harness project,
    supporting dual coordinates, composite cables, coverings, and topology routing."""
    
    def __init__(self, project_data: Optional[dict] = None):
        if project_data:
            self.data = project_data
        else:
            self.data = {
                "project_id": "",
                "project_name": "New Harness Project",
                "revision": "A",
                "units": "MM_AWG",
                "nodes": [],
                "bundles": [],
                "wires": [],
                "cables": []
            }

    @property
    def project_id(self) -> str:
        return self.data.get("project_id", "")

    @property
    def project_name(self) -> str:
        return self.data.get("project_name", "")

    def add_node(self, node_id: str, part_number: str, ref_designator: str, 
                 x: float, y: float, 
                 fb_x: Optional[float] = None, fb_y: Optional[float] = None, 
                 pins: Optional[List[dict]] = None,
                 table_config: Optional[dict] = None,
                 is_junction: bool = False):
        """Adds a physical node with explicit is_junction designation."""
        
        default_columns = table_config.get("columns", []) if table_config else []
        if not default_columns:
            if is_junction:
                default_columns = [
                    {"id": "cavity_id", "label": "Port", "width": 35},
                    {"id": "side", "label": "Side", "width": 45},
                    {"id": "signal", "label": "Signal", "width": 70},
                    {"id": "wire_id", "label": "Wire", "width": 60},
                    {"id": "color", "label": "Color", "width": 45}
                ]
            else:
                default_columns = [
                    {"id": "cavity", "label": "Cav", "width": 35},
                    {"id": "pin", "label": "Pin", "width": 35},
                    {"id": "signal", "label": "Signal", "width": 70},
                    {"id": "wire_id", "label": "Wire", "width": 60},
                    {"id": "color", "label": "Color", "width": 45}
                ]

        default_offset = table_config.get("offset_2d", {"x": 50, "y": -40}) if table_config else {"x": 50, "y": -40}

        node = {
            "node_id": node_id,
            "part_number": part_number,
            "ref_designator": ref_designator,
            "position_2d": {"x": x, "y": y},
            "formboard_position_2d": {"x": fb_x if fb_x is not None else x, "y": fb_y if fb_y is not None else y},
            "pins": pins or [],
            "is_junction": is_junction, # Explicit boolean flag
            "table_config": {
                "offset_2d": default_offset,
                "columns": default_columns,
                "visible": True
            }
        }
        self.data["nodes"].append(node)

    def update_node_position(self, node_id: str, x: float, y: float, is_formboard: bool = False):
        """Updates either the drawing position or the 1:1 formboard position of a node."""
        for node in self.data.get("nodes", []):
            if node["node_id"] == node_id:
                key = "formboard_position_2d" if is_formboard else "position_2d"
                node[key]["x"] = x
                node[key]["y"] = y
                break

    def add_bundle(self, bundle_id: str, start_node_id: str, end_node_id: str, length_mm: float = 0.0, coverings: Optional[list] = None):
        """Adds a physical bundle segment with support for assigned protective coverings."""
        bundle = {
            "bundle_id": bundle_id,
            "start_node_id": start_node_id,
            "end_node_id": end_node_id,
            "length_mm": length_mm,
            "coverings": coverings or []  # List of dicts: e.g., [{"part_number": "CORR-NW-10", "start_ratio": 0.0, "end_ratio": 1.0}]
        }
        self.data["bundles"].append(bundle)

    def add_cable(self, cable_id: str, signal_name: str, part_number: str, 
                  cable_type: str, endpoints: List[dict], routed_bundle_ids: List[str], 
                  conductors: List[dict], has_shield: bool = True, drain_wire_connected: bool = True):
        """Adds a composite cable (twisted pair / shielded) routed through bundles[cite: 1]."""
        cable = {
            "cable_id": cable_id,
            "signal_name": signal_name,
            "part_number": part_number,
            "cable_type": cable_type, # e.g., "TWISTED_PAIR", "SHIELDED_MULTI_CORE"
            "endpoints": endpoints,
            "routed_bundle_ids": routed_bundle_ids,
            "has_shield": has_shield,
            "drain_wire_connected": drain_wire_connected,
            "conductors": conductors # List of inner wires/cores
        }
        self.data.setdefault("cables", []).append(cable)

    def add_wire_object(self, wire_data: dict):
        """Adds a single-core electrical conductor."""
        self.data["wires"].append(wire_data)

    def remove_wire(self, wire_id: str):
        self.data["wires"] = [w for w in self.data["wires"] if w["wire_id"] != wire_id]

    def remove_node(self, node_id: str):
        """Removes a node, cascading deletions to connected bundles and orphaned wires."""
        # 1. Remove the node itself
        self.data["nodes"] = [n for n in self.data["nodes"] if n["node_id"] != node_id]
        
        # 2. Identify and remove connected bundles
        removed_bundles = []
        active_bundles = []
        for b in self.data["bundles"]:
            if b["start_node_id"] == node_id or b["end_node_id"] == node_id:
                removed_bundles.append(b["bundle_id"])
            else:
                active_bundles.append(b)
        self.data["bundles"] = active_bundles

        # 3. Clean up wires whose endpoints or routed paths touch the removed elements
        active_wires = []
        for w in self.data["wires"]:
            has_ep = any(ep.get("node_id") == node_id for ep in w.get("endpoints", []))
            traverses_rem = any(b_id in removed_bundles for b_id in w.get("routed_bundle_ids", []))
            if not has_ep and not traverses_rem:
                active_wires.append(w)
        self.data["wires"] = active_wires

    def find_bundle_path(self, start_node_id: str, end_node_id: str) -> list:
        """Finds the ordered sequence of bundle IDs connecting two nodes via BFS."""
        if start_node_id == end_node_id:
            return []

        graph = {}
        for bundle in self.data.get("bundles", []):
            b_id = bundle["bundle_id"]
            u = bundle["start_node_id"]
            v = bundle["end_node_id"]
            graph.setdefault(u, []).append((v, b_id))
            graph.setdefault(v, []).append((u, b_id))

        if start_node_id not in graph or end_node_id not in graph:
            return []

        queue = deque([(start_node_id, [])])
        visited = {start_node_id}

        while queue:
            current_node, path = queue.popleft()
            if current_node == end_node_id:
                return path

            for neighbor, bundle_id in graph.get(current_node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [bundle_id]))

        return []

    def find_nearest_bundle_segment(self, node_id: str) -> Optional[dict]:
        """Finds the nearest physical bundle trunk segment for trunk-snapping branches."""
        target_node = next((n for n in self.data.get("nodes", []) if n["node_id"] == node_id), None)
        if not target_node:
            return None

        p_pos = target_node.get("position_2d", {"x": 0, "y": 0})
        px, py = p_pos["x"], p_pos["y"]
        node_map = {n["node_id"]: n for n in self.data.get("nodes", [])}
        nearest_data = None
        min_dist = float('inf')

        for bundle in self.data.get("bundles", []):
            start_n = node_map.get(bundle["start_node_id"])
            end_n = node_map.get(bundle["end_node_id"])
            if not start_n or not end_n:
                continue

            a = start_n.get("position_2d", {"x": 0, "y": 0})
            b = end_n.get("position_2d", {"x": 0, "y": 0})
            ax, ay = a["x"], a["y"]
            bx, by = b["x"], b["y"]

            ab_x, ab_y = bx - ax, by - ay
            ap_x, ap_y = px - ax, py - ay
            ab_len_sq = ab_x**2 + ab_y**2

            if ab_len_sq == 0:
                continue

            t = max(0.0, min(1.0, (ap_x * ab_x + ap_y * ab_y) / ab_len_sq))
            cx, cy = ax + t * ab_x, ay + t * ab_y
            dist = math.sqrt((px - cx)**2 + (py - cy)**2)

            if dist < min_dist:
                min_dist = dist
                nearest_data = {
                    "bundle": bundle,
                    "projection": {"x": round(cx, 1), "y": round(cy, 1)},
                    "distance": dist
                }

        return nearest_data

    def break_bundle(self, bundle_id: str, junction_ref: str, junction_x: float, junction_y: float) -> Optional[str]:
        """Inserts a Z-junction node, splitting an existing bundle into two sub-segments."""
        bundle_to_break = next((b for b in self.data.get("bundles", []) if b["bundle_id"] == bundle_id), None)
        if not bundle_to_break:
            return None

        start_node_id = bundle_to_break["start_node_id"]
        end_node_id = bundle_to_break["end_node_id"]
        total_length = bundle_to_break["length_mm"]

        junction_node_id = f"node_z_{uuid.uuid4().hex[:4].upper()}" if not junction_ref.lower().startswith("node_") else junction_ref
        
        # Add node with dual coordinates initialized to the break point
        self.add_node(
            node_id=junction_node_id,
            part_number="SPLICE-Z-JUNCTION",
            ref_designator=junction_ref,
            x=junction_x, y=junction_y,
            fb_x=junction_x, fb_y=junction_y,
            pins=[]
        )

        self.data["bundles"] = [b for b in self.data["bundles"] if b["bundle_id"] != bundle_id]

        sub_len = total_length / 2.0
        b1_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"
        b2_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"

        self.add_bundle(b1_id, start_node_id, junction_node_id, round(sub_len, 1))
        self.add_bundle(b2_id, junction_node_id, end_node_id, round(sub_len, 1))

        # Update routed paths for single wires
        for wire in self.data.get("wires", []):
            routed = wire.get("routed_bundle_ids", [])
            if bundle_id in routed:
                idx = routed.index(bundle_id)
                routed[idx:idx+1] = [b1_id, b2_id]

        # Update routed paths for composite cables
        for cable in self.data.get("cables", []):
            routed = cable.get("routed_bundle_ids", [])
            if bundle_id in routed:
                idx = routed.index(bundle_id)
                routed[idx:idx+1] = [b1_id, b2_id]

        return junction_node_id

    def calculate_wire_length(self, wire_id: str) -> float:
        """Calculates total wire length including bundle lengths and insertion depths[cite: 1]."""
        wire = next((w for w in self.data["wires"] if w["wire_id"] == wire_id), None)
        if not wire:
            return 0.0

        bundle_map = {b["bundle_id"]: b["length_mm"] for b in self.data["bundles"]}
        total_bundle_length = sum(bundle_map.get(b_id, 0.0) for b_id in wire.get("routed_bundle_ids", []))
        extra_length = wire.get("extra_length_mm", 0.0)

        insertion_depth_total = 0.0
        node_map = {n["node_id"]: n for n in self.data.get("nodes", [])}
        
        for ep in wire.get("endpoints", []):
            node = node_map.get(ep.get("node_id"))
            if node:
                for pin in node.get("pins", []):
                    if pin.get("cavity_id") == ep.get("cavity_id"):
                        insertion_depth_total += pin.get("insertion_depth_mm", 0.0)

        return total_bundle_length + insertion_depth_total + extra_length

    def to_json(self) -> str:
        return json.dumps(self.data, indent=2)