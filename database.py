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
        CREATE TABLE IF NOT EXISTS harness_editors (
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
    DB_PATH = "harness_editor.db"
    @staticmethod
    def init_database():
        """Initializes SQLite tables including colors, master coverings, and master wires."""
        conn = sqlite3.connect(DatabaseManager.DB_PATH)
        cursor = conn.cursor()
        
        # Existing tables...
        
        # Master Wires Table (Company-wide wire component library)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS master_wires (
                part_number TEXT PRIMARY KEY,
                gauge_mm2 REAL,
                outer_diameter_mm REAL,
                description TEXT,
                default_color TEXT
            )
        """)
        
        # Seed standard automotive metric wires (FLRY-B) if empty
        cursor.execute("SELECT COUNT(*) FROM master_wires")
        if cursor.fetchone()[0] == 0:
            default_wires = [
                ("FLRY-B-0.35", 0.35, 1.2, "Automotive Wire FLRY-B 0.35 mm²", "BK"),
                ("FLRY-B-0.5", 0.50, 1.6, "Automotive Wire FLRY-B 0.50 mm²", "BK"),
                ("FLRY-B-0.75", 0.75, 1.9, "Automotive Wire FLRY-B 0.75 mm²", "BK"),
                ("FLRY-B-1.0", 1.00, 2.1, "Automotive Wire FLRY-B 1.00 mm²", "BK"),
                ("FLRY-B-1.5", 1.50, 2.4, "Automotive Wire FLRY-B 1.50 mm²", "BK"),
                ("FLRY-B-2.5", 2.50, 3.0, "Automotive Wire FLRY-B 2.50 mm²", "BK")
            ]
            cursor.executemany("INSERT OR IGNORE INTO master_wires VALUES (?, ?, ?, ?, ?)", default_wires)

        conn.commit()
        conn.close()
    @staticmethod
    def get_master_wires() -> list:
        """Retrieves all master wire components from the database."""
        conn = sqlite3.connect(DatabaseManager.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM master_wires ORDER BY gauge_mm2")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def publish_project_to_master(project_data: dict):
        """Registers project wires and components into the company master database upon final publication."""
        conn = sqlite3.connect(DatabaseManager.DB_PATH)
        cursor = conn.cursor()
        
        # Register Wires
        for w in project_data.get("wires", []):
            gauge = w.get("gauge", 0.5)
            od = w.get("outer_diameter_mm", 1.6) # Fallback outer diameter estimation
            color = w.get("color", "BK")
            p_num = w.get("wire_part_number") or f"WIRE-{gauge}-{color}"
            desc = f"Wire {w.get('signal_name', w.get('wire_id'))} ({gauge}mm²)"
            
            cursor.execute("""
                INSERT OR REPLACE INTO master_wires (part_number, gauge_mm2, outer_diameter_mm, description, default_color)
                VALUES (?, ?, ?, ?, ?)
            """, (p_num, gauge, od, desc, color))
            
        conn.commit()
        conn.close()
    @staticmethod
    def get_coverings() -> list:
        """Retrieves all master covering parts from the database."""
        conn = sqlite3.connect(DatabaseManager.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM master_coverings ORDER BY covering_type, part_number")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    @staticmethod
    def save_project(project_data: dict, db_path: str = "harness_editor.db"):
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
    def init_color_table(db_path: str = "harness_editor.db"):
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
    def get_colors(db_path: str = "harness_editor.db") -> list:
        """Retrieves all available wire colors from the database."""
        # DatabaseManager.init_color_table(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, hex_value FROM colors ORDER BY name;")
        rows = cursor.fetchall()

        conn.close()
        return [{"code": r[0], "name": r[1], "hex_value": r[2]} for r in rows]

    @staticmethod
    def add_color(code: str, name: str, hex_value: str, db_path: str = "harness_editor.db"):
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