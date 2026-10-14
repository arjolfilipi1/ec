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
    """Manages CRUD operations and caching for components and projects."""
    @staticmethod
    def save_project(project_data: dict):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        project_id = project_data["project_id"]
        project_name = project_data["project_name"]
        revision = project_data.get("revision", "A")
        units = project_data.get("units", "MM_AWG")
        raw_json = json.dumps(project_data)

        cursor.execute("""
            INSERT INTO harness_projects (project_id, project_name, revision, units, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(project_id) DO UPDATE SET
                project_name=excluded.project_name,
                revision=excluded.revision,
                units=excluded.units,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
        """, (project_id, project_name, revision, units, raw_json))
        
        conn.commit()
        conn.close()

    @staticmethod
    def load_project(project_id: str) -> dict:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT raw_json FROM harness_projects WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()
        return json.loads(row[0]) if row else None

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")