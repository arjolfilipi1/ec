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
    @staticmethod
    def init_color_table(db_path: str = "harness_project.db"):
        """Initializes the master colors lookup table in SQLite with default automotive color codes."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS colors (
                code TEXT PRIMARY KEY,
                name TEXT,
                hex_value TEXT
            )
        ''')
        # Seed default colors if the table is empty
        cursor.execute("SELECT COUNT(*) FROM colors")
        if cursor.fetchone()[0] == 0:
            defaults = [
                ("BK", "Black", "#2C3E50"),
                ("RD", "Red", "#E74C3C"),
                ("YE", "Yellow", "#F1C40F"),
                ("BU", "Blue", "#2980B9"),
                ("WH", "White", "#7F8C8D"),
                ("GN", "Green", "#27AE60"),
                ("BN", "Brown", "#A04000"),
                ("VT", "Violet", "#8E44AD")
            ]
            cursor.executemany("INSERT OR IGNORE INTO colors (code, name, hex_value) VALUES (?, ?, ?)", defaults)
        conn.commit()
        conn.close()

    @staticmethod
    def get_colors(db_path: str = "harness_project.db") -> list:
        """Retrieves all available wire colors from the database."""
        DatabaseManager.init_color_table(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, hex_value FROM colors ORDER BY name;")
        rows = cursor.fetchall()
        conn.close()
        return [{"code": r[0], "name": r[1], "hex_value": r[2]} for r in rows]

    @staticmethod
    def add_color(code: str, name: str, hex_value: str, db_path: str = "harness_project.db"):
        """Adds a new custom color definition to the database."""
        DatabaseManager.init_color_table(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO colors (code, name, hex_value) VALUES (?, ?, ?)", (code.upper(), name, hex_value))
        conn.commit()
        conn.close()
if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")