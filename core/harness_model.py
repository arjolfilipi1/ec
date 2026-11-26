import json
import math
import copy
from collections import deque
from typing import List, Dict, Optional,Tuple, Any
import uuid
class HarnessProjectModel:
    """Manages the hierarchical in-memory representation of a harness project,
    supporting dual coordinates, composite cables, coverings, and topology routing."""
    VALID_ORIENTATIONS = ("front", "left", "right", "up", "down")
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
                "twisted_pairs": [],
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
                 is_junction: bool = False,
                 orientation: str = "front"):
        """Adds a physical node with explicit is_junction designation and mounting orientation."""
        norm_orientation = orientation.lower().strip() if orientation else "front"
        if norm_orientation not in self.VALID_ORIENTATIONS:
            raise ValueError(
                f"Invalid orientation '{orientation}'. Must be one of {self.VALID_ORIENTATIONS}."
            )

        # ... existing default_columns and default_offset logic ...

        node = {
            "node_id": node_id,
            "part_number": part_number,
            "ref_designator": ref_designator,
            "orientation": norm_orientation,
            "position_2d": {"x": x, "y": y},
            "formboard_position_2d": {"x": fb_x if fb_x is not None else x, "y": fb_y if fb_y is not None else y},
            "pins": pins or [],
            "is_junction": is_junction,
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
        return bundle
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
    def add_wire(self, wire_id: str, signal_name: str, gauge: float, color: str, stripe_color: str = "", endpoints: Optional[list] = None, outer_diameter_mm: float = 1.6):
        """Adds an electrical wire with gauge, diameter, color properties, and endpoints."""
        wire = {
            "wire_id": wire_id,
            "signal_name": signal_name,
            "gauge": gauge,
            "color": color,
            "stripe_color": stripe_color,
            "outer_diameter_mm": outer_diameter_mm,
            "wire_part_number": f"WIRE-{gauge}-{color}",
            "endpoints": endpoints or [],
            "extra_length_mm": 0.0
        }
        self.data["wires"].append(wire)
    def add_wire_object(self, wire_data: dict):
        """Adds a single-core electrical conductor."""
        self.data["wires"].append(wire_data)

    def remove_wire(self, wire_id: str):
        self.data["wires"] = [w for w in self.data["wires"] if w["wire_id"] != wire_id]

        # Dissolve any twisted pair that referenced the deleted wire
        surviving_pairs = []
        orphaned_partner_ids = set()
        for tp in self.data.get("twisted_pairs", []):
            if wire_id in tp.get("wire_ids", []):
                orphaned_partner_ids.update(wid for wid in tp["wire_ids"] if wid != wire_id)
            else:
                surviving_pairs.append(tp)

        self.data["twisted_pairs"] = surviving_pairs
        for w in self.data.get("wires", []):
            if w["wire_id"] in orphaned_partner_ids:
                w.pop("twisted_pair_id", None)

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
        """Inserts a Z-junction node, splitting an existing bundle proportionally while preserving coverings."""
        bundle_to_break = next((b for b in self.data.get("bundles", []) if b["bundle_id"] == bundle_id), None)
        if not bundle_to_break:
            return None

        start_node_id = bundle_to_break["start_node_id"]
        end_node_id = bundle_to_break["end_node_id"]
        total_length = bundle_to_break.get("length_mm", 0.0)
        original_coverings = bundle_to_break.get("coverings", [])

        # Compute exact proportional split ratio along the bundle
        t = self._compute_split_ratio(start_node_id, end_node_id, junction_x, junction_y)
        len_1 = round(total_length * t, 1)
        len_2 = round(total_length - len_1, 1)
        cov_1, cov_2 = self._split_coverings(original_coverings, t)

        junction_node_id = (
            f"node_z_{uuid.uuid4().hex[:4].upper()}"
            if not junction_ref.lower().startswith("node_")
            else junction_ref
        )

        self.add_node(
            node_id=junction_node_id,
            part_number="SPLICE-Z-JUNCTION",
            ref_designator=junction_ref,
            x=junction_x,
            y=junction_y,
            fb_x=junction_x,
            fb_y=junction_y,
            pins=[],
            is_junction=True
        )

        self.data["bundles"] = [b for b in self.data["bundles"] if b["bundle_id"] != bundle_id]

        b1_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"
        b2_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"

        self.add_bundle(b1_id, start_node_id, junction_node_id, len_1, coverings=cov_1)
        self.add_bundle(b2_id, junction_node_id, end_node_id, len_2, coverings=cov_2)

        # Update routed paths for wires and cables, respecting traversal direction
        for collection_key in ("wires", "cables"):
            for item in self.data.get(collection_key, []):
                routed = item.get("routed_bundle_ids", [])
                if bundle_id in routed:
                    idx = routed.index(bundle_id)
                    # Determine traversal direction to order [b1_id, b2_id] vs [b2_id, b1_id]
                    is_reversed = False
                    if idx > 0:
                        prev_b = next((b for b in self.data["bundles"] if b["bundle_id"] == routed[idx - 1]), None)
                        if prev_b and end_node_id in (prev_b["start_node_id"], prev_b["end_node_id"]):
                            is_reversed = True
                    elif len(routed) > idx + 1:
                        next_b = next((b for b in self.data["bundles"] if b["bundle_id"] == routed[idx + 1]), None)
                        if next_b and start_node_id in (next_b["start_node_id"], next_b["end_node_id"]):
                            is_reversed = True
                    else:
                        # Single-bundle route: check first endpoint node
                        eps = item.get("endpoints", [])
                        if eps and eps[0].get("node_id") == end_node_id:
                            is_reversed = True

                    routed[idx:idx + 1] = [b2_id, b1_id] if is_reversed else [b1_id, b2_id]

        return junction_node_id

    def calculate_wire_length(self, wire_id: str) -> float:
        """Calculates total wire cut length including bundle lengths, twist take-up, and insertion depths."""
        wire = next((w for w in self.data["wires"] if w["wire_id"] == wire_id), None)
        if not wire:
            return 0.0

        bundle_map = {b["bundle_id"]: b["length_mm"] for b in self.data["bundles"]}
        total_bundle_length = sum(bundle_map.get(b_id, 0.0) for b_id in wire.get("routed_bundle_ids", []))
        extra_length = wire.get("extra_length_mm", 0.0)

        # Apply twist take-up allowance if this wire belongs to a twisted pair
        pair_id = wire.get("twisted_pair_id")
        if pair_id:
            pair = next((tp for tp in self.data.get("twisted_pairs", []) if tp["pair_id"] == pair_id), None)
            if pair:
                untwisted = pair.get("untwisted_start_mm", 0.0) + pair.get("untwisted_end_mm", 0.0)
                twisted_run = max(0.0, total_bundle_length - untwisted)
                takeup_factor = pair.get("twist_takeup_factor", 1.03)
                total_bundle_length = untwisted + (twisted_run * takeup_factor)

        insertion_depth_total = 0.0
        node_map = {n["node_id"]: n for n in self.data.get("nodes", [])}

        for ep in wire.get("endpoints", []):
            node = node_map.get(ep.get("node_id"))
            if node:
                for pin in node.get("pins", []):
                    if pin.get("cavity_id") == ep.get("cavity_id"):
                        insertion_depth_total += pin.get("insertion_depth_mm", 0.0)

        return round(total_bundle_length + insertion_depth_total + extra_length, 1)

    def to_json(self) -> str:
        return json.dumps(self.data, indent=2)
    def merge_nodes(self, source_id: str, target_id: str):
        """Merges source_id into target_id, collapsing self-loops and recalculating affected wire/cable routes."""
        if source_id == target_id:
            return

        # 1. Re-route bundles connected to source_id -> target_id
        collapsed_bundle_ids = set()
        surviving_bundles = []

        for b in self.data.get("bundles", []):
            if b["start_node_id"] == source_id:
                b["start_node_id"] = target_id
            if b["end_node_id"] == source_id:
                b["end_node_id"] = target_id

            # If a bundle bridged source_id and target_id, it is now a zero-length collapsed edge
            if b["start_node_id"] == b["end_node_id"]:
                collapsed_bundle_ids.add(b["bundle_id"])
            else:
                surviving_bundles.append(b)

        self.data["bundles"] = surviving_bundles

        # 2. Update endpoints and repair routed_bundle_ids on wires and cables
        for collection_key in ("wires", "cables"):
            for item in self.data.get(collection_key, []):
                endpoints = item.get("endpoints", [])
                touched_merge = any(ep.get("node_id") in (source_id, target_id) for ep in endpoints)

                for ep in endpoints:
                    if ep.get("node_id") == source_id:
                        ep["node_id"] = target_id

                routed = item.get("routed_bundle_ids", [])
                if not routed:
                    continue

                had_collapsed = any(bid in collapsed_bundle_ids for bid in routed)
                if had_collapsed:
                    # Strip collapsed bundle IDs
                    item["routed_bundle_ids"] = [bid for bid in routed if bid not in collapsed_bundle_ids]

                # If endpoints changed or a bridge bundle collapsed, verify path continuity and re-route if needed
                if (touched_merge or had_collapsed) and len(endpoints) >= 2:
                    ep_a = endpoints[0].get("node_id")
                    ep_b = endpoints[-1].get("node_id")
                    if ep_a and ep_b:
                        if ep_a == ep_b:
                            # Both endpoints collapsed onto the same node
                            item["routed_bundle_ids"] = []
                        elif not item["routed_bundle_ids"]:
                            # Recompute shortest topological path if route became empty
                            item["routed_bundle_ids"] = self.find_bundle_path(ep_a, ep_b)
    def _compute_split_ratio(self, start_node_id: str, end_node_id: str, split_x: float, split_y: float) -> float:
        """Computes the normalized projection ratio t in [0.0, 1.0] of (split_x, split_y) along a bundle."""
        node_map = {n["node_id"]: n for n in self.data.get("nodes", [])}
        start_n = node_map.get(start_node_id)
        end_n = node_map.get(end_node_id)
        if not start_n or not end_n:
            return 0.5

        ax = start_n.get("position_2d", {}).get("x", 0.0)
        ay = start_n.get("position_2d", {}).get("y", 0.0)
        bx = end_n.get("position_2d", {}).get("x", 0.0)
        by = end_n.get("position_2d", {}).get("y", 0.0)

        ab_x, ab_y = bx - ax, by - ay
        ab_len_sq = ab_x ** 2 + ab_y ** 2
        if ab_len_sq == 0:
            return 0.5

        t = ((split_x - ax) * ab_x + (split_y - ay) * ab_y) / ab_len_sq
        return max(0.0, min(1.0, t))

    def _split_coverings(self, coverings: List[dict], t: float) -> Tuple[List[dict], List[dict]]:
        """Splits and re-normalizes bundle coverings at ratio t into (first_half, second_half)."""
        cov_1: List[dict] = []
        cov_2: List[dict] = []

        for cov in coverings:
            s = cov.get("start_ratio", 0.0)
            e = cov.get("end_ratio", 1.0)

            # Overlap with first sub-segment [0.0, t]
            if t > 0.0 and s < t:
                c1 = copy.deepcopy(cov)
                c1["start_ratio"] = round(s / t, 4)
                c1["end_ratio"] = round(min(e, t) / t, 4)
                if c1["end_ratio"] > c1["start_ratio"]:
                    cov_1.append(c1)

            # Overlap with second sub-segment [t, 1.0]
            if t < 1.0 and e > t:
                c2 = copy.deepcopy(cov)
                c2["start_ratio"] = round((max(s, t) - t) / (1.0 - t), 4)
                c2["end_ratio"] = round((e - t) / (1.0 - t), 4)
                if c2["end_ratio"] > c2["start_ratio"]:
                    cov_2.append(c2)

        return cov_1, cov_2
    def merge_node_into_bundle(self, node_id: str, bundle_id: str, drop_x: float, drop_y: float):
        """Snaps an existing node onto a bundle segment, splitting length and coverings proportionally."""
        bundle_to_break = next((b for b in self.data.get("bundles", []) if b["bundle_id"] == bundle_id), None)
        if not bundle_to_break:
            return

        start_node_id = bundle_to_break["start_node_id"]
        end_node_id = bundle_to_break["end_node_id"]

        # Guard against snapping a bundle's own endpoint onto itself
        if node_id in (start_node_id, end_node_id):
            return

        total_length = bundle_to_break.get("length_mm", 0.0)
        original_coverings = bundle_to_break.get("coverings", [])

        # Compute split ratio before moving the node
        t = self._compute_split_ratio(start_node_id, end_node_id, drop_x, drop_y)
        len_1 = round(total_length * t, 1)
        len_2 = round(total_length - len_1, 1)
        cov_1, cov_2 = self._split_coverings(original_coverings, t)

        # Update node position to the projection point
        self.update_node_position(node_id, drop_x, drop_y, is_formboard=False)
        self.update_node_position(node_id, drop_x, drop_y, is_formboard=True)

        self.data["bundles"] = [b for b in self.data["bundles"] if b["bundle_id"] != bundle_id]

        b1_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"
        b2_id = f"BUN-{uuid.uuid4().hex[:4].upper()}"

        self.add_bundle(b1_id, start_node_id, node_id, len_1, coverings=cov_1)
        self.add_bundle(b2_id, node_id, end_node_id, len_2, coverings=cov_2)

        for collection_key in ("wires", "cables"):
            for item in self.data.get(collection_key, []):
                routed = item.get("routed_bundle_ids", [])
                if bundle_id in routed:
                    idx = routed.index(bundle_id)
                    is_reversed = False
                    if idx > 0:
                        prev_b = next((b for b in self.data["bundles"] if b["bundle_id"] == routed[idx - 1]), None)
                        if prev_b and end_node_id in (prev_b["start_node_id"], prev_b["end_node_id"]):
                            is_reversed = True
                    elif len(routed) > idx + 1:
                        next_b = next((b for b in self.data["bundles"] if b["bundle_id"] == routed[idx + 1]), None)
                        if next_b and start_node_id in (next_b["start_node_id"], next_b["end_node_id"]):
                            is_reversed = True
                    else:
                        eps = item.get("endpoints", [])
                        if eps and eps[0].get("node_id") == end_node_id:
                            is_reversed = True

                    routed[idx:idx + 1] = [b2_id, b1_id] if is_reversed else [b1_id, b2_id]
    def highlight_wires_in_bundle(self, bundle_id: Optional[str], clear_others: bool = True) -> List[str]:
        """
        Sets `is_highlighted = True` for all wires (and composite cables) routed through `bundle_id`.
        Pass `bundle_id=None` to clear all wire highlights.
        Returns a list of highlighted wire IDs.
        """
        highlighted_ids: List[str] = []

        for wire in self.data.get("wires", []):
            is_in_bundle = bool(bundle_id) and (bundle_id in wire.get("routed_bundle_ids", []))
            if is_in_bundle:
                wire["is_highlighted"] = True
                highlighted_ids.append(wire["wire_id"])
            elif clear_others:
                wire["is_highlighted"] = False

        # Also update composite cables (and their inner conductors if present)
        for cable in self.data.get("cables", []):
            is_in_bundle = bool(bundle_id) and (bundle_id in cable.get("routed_bundle_ids", []))
            if is_in_bundle:
                cable["is_highlighted"] = True
            elif clear_others:
                cable["is_highlighted"] = False

        return highlighted_ids
    def set_node_orientation(self, node_id: str, orientation: str) -> bool:
        """Sets the connector installation orientation ('front', 'left', 'right', 'up', 'down')."""
        norm_orientation = orientation.lower().strip()
        if norm_orientation not in self.VALID_ORIENTATIONS:
            raise ValueError(
                f"Invalid orientation '{orientation}'. Must be one of {self.VALID_ORIENTATIONS}."
            )

        for node in self.data.get("nodes", []):
            if node["node_id"] == node_id:
                node["orientation"] = norm_orientation
                return True
        return False

    def cycle_node_orientation(self, node_id: str) -> Optional[str]:
        """Cycles a node through VALID_ORIENTATIONS and returns the new orientation."""
        for node in self.data.get("nodes", []):
            if node["node_id"] == node_id:
                current = node.get("orientation", "front")
                idx = self.VALID_ORIENTATIONS.index(current) if current in self.VALID_ORIENTATIONS else -1
                next_orientation = self.VALID_ORIENTATIONS[(idx + 1) % len(self.VALID_ORIENTATIONS)]
                node["orientation"] = next_orientation
                return next_orientation
        return None
    def add_twisted_pair(
        self,
        pair_id: str,
        wire_id_1: str,
        wire_id_2: str,
        signal_group: str = "",
        twist_pitch_mm: float = 20.0,
        untwisted_start_mm: float = 30.0,
        untwisted_end_mm: float = 30.0,
        twist_takeup_factor: float = 1.03,
        sync_routing: bool = True
    ) -> dict:
        """Pairs two existing wires into a twisted pair and optionally synchronizes their bundle route."""
        if wire_id_1 == wire_id_2:
            raise ValueError("A twisted pair requires two distinct wire IDs.")

        w1 = next((w for w in self.data.get("wires", []) if w["wire_id"] == wire_id_1), None)
        w2 = next((w for w in self.data.get("wires", []) if w["wire_id"] == wire_id_2), None)
        if not w1 or not w2:
            raise ValueError(f"Both wires ('{wire_id_1}', '{wire_id_2}') must exist in project wires.")

        # Synchronize routed_bundle_ids if requested and w1 has a route
        if sync_routing and w1.get("routed_bundle_ids"):
            w2["routed_bundle_ids"] = list(w1["routed_bundle_ids"])

        w1["twisted_pair_id"] = pair_id
        w2["twisted_pair_id"] = pair_id

        pair = {
            "pair_id": pair_id,
            "signal_group": signal_group,
            "wire_ids": [wire_id_1, wire_id_2],
            "twist_pitch_mm": twist_pitch_mm,
            "untwisted_start_mm": untwisted_start_mm,
            "untwisted_end_mm": untwisted_end_mm,
            "twist_takeup_factor": twist_takeup_factor
        }
        self.data.setdefault("twisted_pairs", []).append(pair)
        return pair

    def remove_twisted_pair(self, pair_id: str, delete_wires: bool = False):
        """Unpairs two wires (or optionally deletes both underlying wires)."""
        pair = next((tp for tp in self.data.get("twisted_pairs", []) if tp["pair_id"] == pair_id), None)
        if not pair:
            return

        w_ids = set(pair.get("wire_ids", []))
        if delete_wires:
            self.data["wires"] = [w for w in self.data.get("wires", []) if w["wire_id"] not in w_ids]
        else:
            for w in self.data.get("wires", []):
                if w["wire_id"] in w_ids and w.get("twisted_pair_id") == pair_id:
                    w.pop("twisted_pair_id", None)

        self.data["twisted_pairs"] = [
            tp for tp in self.data.get("twisted_pairs", []) if tp["pair_id"] != pair_id
        ]