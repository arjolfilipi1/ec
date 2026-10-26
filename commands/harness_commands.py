from PyQt5.QtWidgets import QUndoCommand
from copy import deepcopy
class BreakBundleCommand(QUndoCommand):
    """Undo/redo command for breaking a bundle segment and inserting a junction node."""
    def __init__(self, project_model, bundle_id, junction_ref, x, y, update_callback):
        super().__init__(f"Break Bundle {bundle_id}")
        self.project_model = project_model
        self.bundle_id = bundle_id
        self.junction_ref = junction_ref
        self.x = x
        self.y = y
        self.update_callback = update_callback
        
        self.snapshot_before = deepcopy(project_model.data)
        self.snapshot_after = None

    def undo(self):
        self.project_model.data = deepcopy(self.snapshot_before)
        self.update_callback()

    def redo(self):
        if not self.snapshot_after:
            self.project_model.break_bundle(self.bundle_id, self.junction_ref, self.x, self.y)
            self.snapshot_after = deepcopy(self.project_model.data)
        else:
            self.project_model.data = deepcopy(self.snapshot_after)
        self.update_callback()
class ModifyHarnessCommand(QUndoCommand):
    """Generic undo/redo command that snapshots project state before and after modification."""
    
    def __init__(self, project_model, description, update_callback):
        super().__init__(description)
        self.project_model = project_model
        self.update_callback = update_callback
        
        # Capture state before change
        self.old_state = deepcopy(project_model.data)
        # Placeholder for state after change
        self.new_state = None

    def set_new_state(self):
        """Captures the state after the change has been applied."""
        self.new_state = deepcopy(self.project_model.data)

    def undo(self):
        if self.old_state:
            self.project_model.data = deepcopy(self.old_state)
            self.update_callback()

    def redo(self):
        if self.new_state:
            self.project_model.data = deepcopy(self.new_state)
            self.update_callback()


class AddNodeCommand(QUndoCommand):
    """Explicit undo/redo command for adding a connector node."""
    
    def __init__(self, project_model, node_data, update_callback):
        super().__init__(f"Add Connector {node_data['ref_designator']}")
        self.project_model = project_model
        self.node_data = node_data
        self.update_callback = update_callback

    def undo(self):
        # Remove the node using model's removal logic
        self.project_model.remove_node(self.node_data["node_id"])
        self.update_callback()

    def redo(self):
        # Re-add the node
        self.project_model.data["nodes"].append(self.node_data)
        self.update_callback()

class AddWireCommand(QUndoCommand):
    """Explicit undo/redo command for adding an electrical wire."""
    def __init__(self, project_model, wire_data, update_callback):
        super().__init__(f"Add Wire {wire_data['wire_id']}")
        self.project_model = project_model
        self.wire_data = wire_data
        self.update_callback = update_callback

    def undo(self):
        self.project_model.remove_wire(self.wire_data["wire_id"])
        self.update_callback()

    def redo(self):
        print(self.wire_data)
        self.project_model.add_wire_object(self.wire_data)
        self.update_callback()

class MoveNodeCommand(QUndoCommand):
    """Undo/redo command for moving a connector node on the canvas."""
    def __init__(self, project_model, node_id, old_pos, new_pos, update_callback):
        super().__init__(f"Move Connector {node_id}")
        self.project_model = project_model
        self.node_id = node_id
        self.old_pos = old_pos  # dict: {"x": ..., "y": ...}
        self.new_pos = new_pos  # dict: {"x": ..., "y": ...}
        self.update_callback = update_callback

    def undo(self):
        self.project_model.update_node_position(self.node_id, self.old_pos["x"], self.old_pos["y"])
        self.update_callback()

    def redo(self):
        self.project_model.update_node_position(self.node_id, self.new_pos["x"], self.new_pos["y"])
        self.update_callback()
class RemoveWireCommand(QUndoCommand):
    """Explicit undo/redo command for removing an electrical wire."""
    def __init__(self, project_model, wire_id, update_callback):
        super().__init__(f"Remove Wire {wire_id}")
        self.project_model = project_model
        self.wire_id = wire_id
        self.update_callback = update_callback
        
        # Snapshot state before removal to restore on undo
        self.snapshot_before = deepcopy(project_model.data)

    def undo(self):
        self.project_model.data = deepcopy(self.snapshot_before)
        self.update_callback()

    def redo(self):
        self.project_model.remove_wire(self.wire_id)
        self.update_callback()

class RemoveNodeCommand(QUndoCommand):
    """Explicit undo/redo command for removing a connector node and its connected elements."""
    
    def __init__(self, project_model, node_id, update_callback):
        super().__init__(f"Remove Connector {node_id}")
        self.project_model = project_model
        self.node_id = node_id
        self.update_callback = update_callback
        
        # Snapshot state before removal to allow full restoration on undo
        self.snapshot_before = deepcopy(project_model.data)

    def undo(self):
        # Restore entire state prior to node deletion
        self.project_model.data = deepcopy(self.snapshot_before)
        self.update_callback()

    def redo(self):
        self.project_model.remove_node(self.node_id)
        self.update_callback()