import math

class HarnessCalculator:
    """Implements industry-standard harness bundle diameter, packing methods, and covering fit rules."""
    
    DEFAULT_PACKING_FACTOR = 1.15  # Standard harness cross-section packing factor

    @staticmethod
    def get_wires_in_bundle(bundle: dict, project_data: dict) -> list:
        """Determines which wires pass through a given bundle based on node endpoints."""
        start_node = bundle.get("start_node_id")
        end_node = bundle.get("end_node_id")
        wires = project_data.get("wires", [])
        
        # Filter wires whose endpoints connect through or touch this bundle's nodes
        matched_wires = []
        for w in wires:
            node_ids = [ep.get("node_id") for ep in w.get("endpoints", [])]
            if start_node in node_ids or end_node in node_ids:
                matched_wires.append(w)
        
        # Fallback to all project wires if explicit endpoint mapping is empty
        return matched_wires if matched_wires else wires

    @staticmethod
    def calculate_bundle_diameter(bundle: dict, wires_in_bundle: list) -> tuple:
        """
        Computes bundle diameter using Methods 1-4 or manual override.
        Returns: (diameter_mm or None, method_name_str, status_message)
        """
        override_val = bundle.get("override_diameter_mm")
        
        # Calculate standard diameter first
        calc_val, method_name, status_msg = HarnessCalculator._compute_calculated_diameter(wires_in_bundle)

        if override_val is not None:
            if calc_val is not None and calc_val > 0:
                diff_pct = abs(override_val - calc_val) / calc_val
                if diff_pct > 0.10:
                    return override_val, "Overridden", f"WARNING: Override differs by {diff_pct*100:.1f}% (>10%) from calculated ({calc_val:.2f}mm)!"
            return override_val, "Overridden", "OK (Manual Override)"

        return calc_val, method_name, status_msg

    @staticmethod
    def _compute_calculated_diameter(wires: list) -> tuple:
        """Internal router for Methods 1, 2, 3, 4."""
        if not wires:
            return None, "Not calculated", "No wires assigned"

        diameters = []
        for w in wires:
            od = w.get("outer_diameter_mm")
            if od is None or od <= 0:
                return None, "Not calculated", f"Wire {w.get('wire_id')} missing Outer Diameter"
            diameters.append(od)

        item_count = len(diameters)

        # Method 1: Single item
        if item_count == 1:
            return diameters[0], "Method 1: Single item", "OK"

        # Method 2: Pair
        if item_count == 2:
            d_sum = diameters[0] + diameters[1]
            return d_sum, "Method 2: Pair", "OK"

        # Method 3 & 4: Three or more items
        sum_sq = sum(d ** 2 for d in diameters)
        method_3_val = HarnessCalculator.DEFAULT_PACKING_FACTOR * math.sqrt(sum_sq)

        sorted_diams = sorted(diameters, reverse=True)
        method_4_val = sorted_diams[0] + sorted_diams[1]

        if method_3_val < method_4_val:
            return method_4_val, "Method 4: Two largest", "OK"
        else:
            return method_3_val, "Method 3: Packed", "OK"

    @staticmethod
    def calculate_overall_diameter(bundle_diameter: float, coverings: list) -> float:
        """Calculates final Overall Diameter over all nested protective coverings."""
        if bundle_diameter is None:
            return None
            
        current_od = bundle_diameter
        for cov in coverings:
            wall = cov.get("wall_thickness_mm", 0.0)
            cov_type = cov.get("covering_type", "").lower()
            
            if "corrugated" in cov_type:
                current_od = cov.get("outer_diameter_mm", current_od + (wall * 2))
            else:
                current_od += (wall * 2.0)
                
        return current_od

    @staticmethod
    def evaluate_covering_fit(inner_diameter: float, covering: dict) -> tuple:
        """Evaluates covering fit against the diameter directly inside it."""
        cov_type = covering.get("covering_type", "").lower()
        if inner_diameter is None or inner_diameter <= 0:
            return "Not Checked (No Bundle OD)", False

        if "sleeving" in cov_type or "spiral" in cov_type:
            min_d = covering.get("min_diameter_mm", 0.0)
            max_d = covering.get("max_diameter_mm", 999.0)
            if min_d <= inner_diameter <= max_d:
                return "PASS", False
            return "WARNING: Outside Sleeving Min/Max range", True

        elif "tubing" in cov_type and "corrugated" not in cov_type:
            rec_d = covering.get("recovered_diameter_mm", 0.0)
            sup_d = covering.get("supplied_diameter_mm", 999.0)
            if rec_d <= inner_diameter <= sup_d:
                return "PASS", False
            return "WARNING: Outside Tubing Recovered/Supplied range", True

        elif "corrugated" in cov_type or "custom" in cov_type:
            inner_d = covering.get("inner_diameter_mm", 0.0)
            if inner_d > 0 and inner_diameter <= inner_d:
                return "PASS", False
            return "WARNING: Bundle OD exceeds Corrugated Inner Diameter", True

        elif "tape" in cov_type:
            return "PASS (Tape)", False

        return "PASS", False