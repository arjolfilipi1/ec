import sqlite3
import json
import os

DB_NAME = "harness_editor.db"

def init_db():
    """Initializes the SQLite database with Component Library and Harness Project schemas."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Component Library Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS component_library (
            part_number TEXT PRIMARY KEY,
            manufacturer TEXT NOT NULL,
            component_type TEXT NOT NULL,
            description TEXT,
            raw_json TEXT NOT NULL
        )
    """)

    # Harness Projects Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS harness_projects (
            project_id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            revision TEXT,
            units TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

class DatabaseManager:
    @staticmethod
    def save_project(project_data: dict, db_path: str = "harness_project.db"):
        """Saves project JSON state into a local SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT,
                project_data TEXT
            )
        ''')
        # Clear old records or update primary project
        cursor.execute("DELETE FROM projects")
        cursor.execute(
            "INSERT INTO projects (project_id, project_data) VALUES (?, ?)",
            (project_data.get("project_id", "PROJ-01"), json.dumps(project_data))
        )
        conn.commit()
        conn.close()

    @staticmethod
    def load_project(db_path: str) -> dict:
        """Loads and parses project JSON data from a SQLite database file."""
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects';")
        if not cursor.fetchone():
            conn.close()
            raise ValueError("Invalid harness database schema: 'projects' table missing.")
            
        cursor.execute("SELECT project_data FROM projects LIMIT 1;")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            return json.loads(row[0])
        return {}
    @staticmethod
    def list_projects(db_path: str) -> list:
        """Queries and returns a list of all available projects stored in the central database."""
        if not os.path.exists(db_path):
            return []
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects';")
        if not cursor.fetchone():
            conn.close()
            return []
            
        cursor.execute("SELECT id, project_id, project_data FROM projects;")
        rows = cursor.fetchall()
        conn.close()
        
        projects = []
        for row in rows:
            db_id, proj_id, proj_data_str = row
            try:
                data = json.loads(proj_data_str)
                proj_name = data.get("project_name", proj_id)
                projects.append({
                    "db_id": db_id,
                    "project_id": proj_id,
                    "project_name": proj_name,
                    "data": data
                })
            except Exception:
                projects.append({
                    "db_id": db_id,
                    "project_id": proj_id,
                    "project_name": proj_id,
                    "data": {}
                })
        return projects
if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")