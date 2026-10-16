import json
from typing import List, Dict, Optional
from collections import deque
import math,uuid
class HarnessProjectModel:
    """Manages the hierarchical in-memory representation of a harness project,
    including validation, topology traversal, and wire routing."""
    
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
                "wires": []
            }

    @property
    def project_id(self) -> str:
        return self.data.get("project_id", "")

    @property
    def project_name(self) -> str:
        return self.data.get("project_name", "")

    def add_node(self, node_id: str, part_number: str, ref_designator: str, x: float, y: float, pins: Optional[List[dict]] = None):
        """Adds a physical connection point (connector, splice, or device) to the topology[cite: 1]."""
        node = {
            "node_id": node_id,
            "part_number": part_number,
            "ref_designator": ref_designator,
            "position_2d": {"x": x, "y": y},
            "pins": pins or []
        }
        self.data["nodes"].append(node)

    def add_bundle(self, bundle_id: str, start_node_id: str, end_node_id: str, length_mm: float, coverings: Optional[List[dict]] = None):
        """Adds a physical routing segment (bundle/pathway) between two nodes[cite: 1]."""
        bundle = {
            "bundle_id": bundle_id,
            "start_node_id": start_node_id,
            "end_node_id": end_node_id,
            "length_mm": length_mm,
            "coverings": coverings or []
        }
        self.data["bundles"].append(bundle)

    def add_wire(self, wire_id: str, signal_name: str, part_number: str, color: str, endpoints: List[dict], routed_bundle_ids: List[str], extra_length_mm: float = 0.0):
        """Adds an electrical conductor routed through specific bundle paths[cite: 1]."""
        wire = {
            "wire_id": wire_id,
            "signal_name": signal_name,
            "part_number": part_number,
            "color": color,
            "endpoints": endpoints,
            "routed_bundle_ids": routed_bundle_ids,
            "extra_length_mm": extra_length_mm
        }
        self.data["wires"].append(wire)
    def remove_node(self, node_id: str):
        """Removes a node and cleans up associated bundles and wires referencing it."""
        # Remove node
        self.data["nodes"] = [n for n in self.data["nodes"] if n["node_id"] != node_id]

        # Remove bundles connected to this node
        removed_bundles = []
        active_bundles = []
        for b in self.data["bundles"]:
            if b["start_node_id"] == node_id or b["end_node_id"] == node_id:
                removed_bundles.append(b["bundle_id"])
            else:
                active_bundles.append(b)
        self.data["bundles"] = active_bundles

        # Remove wires referencing removed bundles or endpoints on this node
        active_wires = []
        for w in self.data["wires"]:
            # Check if wire endpoint is on this node
            has_endpoint_on_node = any(ep["node_id"] == node_id for ep in w.get("endpoints", []))
            # Check if wire traverses a removed bundle
            traverses_removed_bundle = any(b_id in removed_bundles for b_id in w.get("routed_bundle_ids", []))
            
            if not has_endpoint_on_node and not traverses_removed_bundle:
                active_wires.append(w)
        self.data["wires"] = active_wires
    def find_bundle_path(self, start_node_id: str, end_node_id: str) -> list:
        """Finds the ordered list of bundle IDs connecting start_node_id to end_node_id 
        using a Breadth-First Search (BFS) over the bundle topology graph."""
        if start_node_id == end_node_id:
            return []

        # Build an adjacency map: node_id -> list of (neighbor_node_id, bundle_id)
        graph = {}
        for bundle in self.data.get("bundles", []):
            b_id = bundle["bundle_id"]
            u = bundle["start_node_id"]
            v = bundle["end_node_id"]
            
            graph.setdefault(u, []).append((v, b_id))
            graph.setdefault(v, []).append((u, b_id))

        if start_node_id not in graph or end_node_id not in graph:
            return []  # One or both nodes are isolated

        # BFS queue storing (current_node, path_of_bundles)
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

        return []  # No physical bundle pathway exists between these nodes
    def calculate_wire_length(self, wire_id: str) -> float:
        """Computes total wire length dynamically based on bundle lengths and physical correction parameters[cite: 1]."""
        wire = next((w for w in self.data["wires"] if w["wire_id"] == wire_id), None)
        if not wire:
            return 0.0

        # Sum lengths of all bundles traversed by the wire
        bundle_map = {b["bundle_id"]: b["length_mm"] for b in self.data["bundles"]}
        total_bundle_length = sum(bundle_map.get(b_id, 0.0) for b_id in wire.get("routed_bundle_ids", []))

        # Add user-defined extra length (strain relief / slack)
        extra_length = wire.get("extra_length_mm", 0.0)

        # Retrieve endpoint insertion depths from nodes if specified
        insertion_depth_total = 0.0
        node_map = {n["node_id"]: n for n in self.data["nodes"]}
        
        for ep in wire.get("endpoints", []):
            node = node_map.get(ep.get("node_id"))
            if node:
                for pin in node.get("pins", []):
                    if pin.get("cavity_id") == ep.get("cavity_id"):
                        insertion_depth_total += pin.get("insertion_depth_mm", 0.0)

        return total_bundle_length + insertion_depth_total + extra_length
    def add_wire_object(self, wire_data: dict):
        """Adds an electrical conductor routed through bundle paths."""
        self.data["wires"].append(wire_data)

    def remove_wire(self, wire_id: str):
        """Removes an electrical conductor by its wire_id."""
        self.data["wires"] = [w for w in self.data["wires"] if w["wire_id"] != wire_id]
    def update_node_position(self, node_id: str, x: float, y: float):
        """Updates the 2D position coordinates of a node."""
        for node in self.data.get("nodes", []):
            if node["node_id"] == node_id:
                node["position_2d"]["x"] = x
                node["position_2d"]["y"] = y
                break
    def to_json(self) -> str:
        """Serializes the project model to JSON format for database persistence[cite: 1]."""
        return json.dumps(self.data, indent=2)
    def find_nearest_node(self, target_node_id: str) -> dict:
        """Finds the geometrically nearest node to the target node using 2D canvas coordinates."""
        target_node = next((n for n in self.data.get("nodes", []) if n["node_id"] == target_node_id), None)
        if not target_node:
            return None

        t_pos = target_node.get("position_2d", {"x": 0, "y": 0})
        tx, ty = t_pos["x"], t_pos["y"]

        nearest_node = None
        min_distance = float('inf')

        for node in self.data.get("nodes", []):
            if node["node_id"] == target_node_id:
                continue
            
            n_pos = node.get("position_2d", {"x": 0, "y": 0})
            nx, ny = n_pos["x"], n_pos["y"]

            # Euclidean distance calculation
            distance = math.sqrt((nx - tx) ** 2 + (ny - ty) ** 2)
            if distance < min_distance:
                min_distance = distance
                nearest_node = node

        return nearest_node
    def break_bundle(self, bundle_id: str, junction_ref: str, junction_x: float, junction_y: float) -> str:
        """
        Breaks an existing bundle into two sub-segments by inserting a new splice/junction node.
        Returns the new junction node ID.
        """
        # 1. Find the target bundle
        bundle_to_break = next((b for b in self.data.get("bundles", []) if b["bundle_id"] == bundle_id), None)
        if not bundle_to_break:
            return None

        start_node_id = bundle_to_break["start_node_id"]
        end_node_id = bundle_to_break["end_node_id"]
        total_length = bundle_to_break["length_mm"]

        # 2. Create a new junction/splice node
        junction_node_id = f"node_junc_{uuid.uuid4().hex[:4].upper()}"
        junction_node = {
            "node_id": junction_node_id,
            "part_number": "SPLICE-JUNCTION-GEN",
            "ref_designator": junction_ref,
            "position_2d": {"x": junction_x, "y": junction_y},
            "pins": []
        }
        self.data["nodes"].append(junction_node)

        # 3. Remove the original bundle
        self.data["bundles"] = [b for b in self.data["bundles"] if b["bundle_id"] != bundle_id]

        # 4. Create two new sub-bundles proportional to length or split evenly
        sub_len = total_length / 2.0
        
        b1_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"
        b2_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"

        self.data["bundles"].append({
            "bundle_id": b1_id,
            "start_node_id": start_node_id,
            "end_node_id": junction_node_id,
            "length_mm": round(sub_len, 1),
            "coverings": []
        })

        self.data["bundles"].append({
            "bundle_id": b2_id,
            "start_node_id": junction_node_id,
            "end_node_id": end_node_id,
            "length_mm": round(sub_len, 1),
            "coverings": []
        })

        # 5. Update any wires traversing the old bundle to traverse the new sub-bundles instead
        for wire in self.data.get("wires", []):
            routed = wire.get("routed_bundle_ids", [])
            if bundle_id in routed:
                idx = routed.index(bundle_id)
                # Replace old bundle ID with the two new sub-bundles in sequence
                routed[idx:idx+1] = [b1_id, b2_id]

        return junction_node_id