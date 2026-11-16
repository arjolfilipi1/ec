# core/routing_engine.py
import math
import uuid
from collections import deque
from typing import Optional

class HarnessRoutingEngine:
    """Pure geometric projection, auto-bridging, and BFS pathfinding engine."""

    @staticmethod
    def find_nearest_bundle_segment(data: dict, node_id: str) -> Optional[dict]:
        """Finds the nearest bundle trunk segment to a given node using position_2d."""
        node_map = {n["node_id"]: n for n in data.get("nodes", [])}
        target_node = node_map.get(node_id)
        if not target_node:
            return None

        p_pos = target_node.get("position_2d", {"x": 0.0, "y": 0.0})
        px, py = p_pos.get("x", 0.0), p_pos.get("y", 0.0)

        nearest_data = None
        min_dist = float("inf")

        for bundle in data.get("bundles", []):
            start_n = node_map.get(bundle.get("start_node_id"))
            end_n = node_map.get(bundle.get("end_node_id"))
            if not start_n or not end_n:
                continue

            ax = start_n.get("position_2d", {}).get("x", 0.0)
            ay = start_n.get("position_2d", {}).get("y", 0.0)
            bx = end_n.get("position_2d", {}).get("x", 0.0)
            by = end_n.get("position_2d", {}).get("y", 0.0)

            ab_x, ab_y = bx - ax, by - ay
            ab_len_sq = ab_x ** 2 + ab_y ** 2
            if ab_len_sq == 0:
                cx, cy = ax, ay
            else:
                t = max(0.0, min(1.0, ((px - ax) * ab_x + (py - ay) * ab_y) / ab_len_sq))
                cx, cy = ax + t * ab_x, ay + t * ab_y

            dist = math.hypot(px - cx, py - cy)
            if dist < min_dist:
                min_dist = dist
                nearest_data = {
                    "bundle": bundle,
                    "projection": {"x": round(cx, 1), "y": round(cy, 1)},
                    "distance": dist,
                }

        return nearest_data

    @staticmethod
    def bridge_node_to_network(project_model, target_node_id: str, tolerance: float = 2.0):
        """Connects an isolated node to the nearest bundle, splitting the trunk if needed."""
        data = project_model.data
        bundles = data.get("bundles", [])
        if not bundles:
            return

        connected_nodes = {b["start_node_id"] for b in bundles} | {b["end_node_id"] for b in bundles}
        if target_node_id in connected_nodes:
            return

        nearest = HarnessRoutingEngine.find_nearest_bundle_segment(data, target_node_id)
        if not nearest:
            return

        best_bundle = nearest["bundle"]
        proj_x, proj_y = nearest["projection"]["x"], nearest["projection"]["y"]
        dist = nearest["distance"]

        node_map = {n["node_id"]: n for n in data.get("nodes", [])}
        u_id, v_id = best_bundle["start_node_id"], best_bundle["end_node_id"]
        u_pos = node_map[u_id].get("position_2d", {"x": 0.0, "y": 0.0})
        v_pos = node_map[v_id].get("position_2d", {"x": 0.0, "y": 0.0})

        if math.hypot(proj_x - u_pos["x"], proj_y - u_pos["y"]) < tolerance:
            junction_id = u_id
        elif math.hypot(proj_x - v_pos["x"], proj_y - v_pos["y"]) < tolerance:
            junction_id = v_id
        else:
            junction_id = project_model.break_bundle(
                best_bundle["bundle_id"], f"J_{uuid.uuid4().hex[:4].upper()}", proj_x, proj_y
            )

        if junction_id:
            project_model.add_bundle(
                bundle_id=f"BUN-{uuid.uuid4().hex[:4].upper()}",
                start_node_id=junction_id,
                end_node_id=target_node_id,
                length_mm=round(dist, 1),
            )

    @staticmethod
    def find_bundle_path(data: dict, start_node_id: str, end_node_id: str) -> list:
        """Finds the ordered sequence of bundle IDs connecting two nodes via BFS."""
        if not start_node_id or not end_node_id or start_node_id == end_node_id:
            return []

        graph = {}
        for bundle in data.get("bundles", []):
            b_id = bundle["bundle_id"]
            u, v = bundle["start_node_id"], bundle["end_node_id"]
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