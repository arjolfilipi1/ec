from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel, QListWidgetItem
from PyQt5.QtCore import Qt

class ProjectSelectorDialog(QDialog):
    """Dialog allowing users to select an available project from the central database."""
    
    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Central Database Project")
        self.resize(420, 300)
        
        self.projects = projects
        self.selected_project = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Available projects found in central database:"))
        
        self.list_widget = QListWidget()
        for p in self.projects:
            display_text = f"{p.get('project_name')} (Project ID: {p.get('project_id')})"
            item = QListWidgetItem(display_text)
            # Store the full project dictionary payload inside user role data
            item.setData(Qt.UserRole, p)
            self.list_widget.addItem(item)
            
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            
        layout.addWidget(self.list_widget)

        # Dialog Action Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept_selection(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            self.selected_project = current_item.data(Qt.UserRole)
            self.accept()
        else:
            self.reject()