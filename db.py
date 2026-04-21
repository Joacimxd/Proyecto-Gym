import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gym.db")


def _get_connection():
    """Return a new connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # access columns by name
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrency
    return conn


def init_db():
    """
    Create the machines table if it doesn't exist and seed it with
    default machines when the table is empty.
    """
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS machines (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL UNIQUE,
                average_time  INTEGER NOT NULL DEFAULT 15,
                max_concurrent INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.commit()

        # Seed only if the table is empty
        count = conn.execute("SELECT COUNT(*) FROM machines").fetchone()[0]
    finally:
        conn.close()


def get_all_machines():
    """Return a list of dicts for every machine in the database."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, average_time, max_concurrent FROM machines ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_machine_by_name(name):
    """Return a single machine dict by name, or None."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, average_time, max_concurrent FROM machines WHERE name = ?",
            (name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_machine_by_id(machine_id):
    """Return a single machine dict by id, or None."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, average_time, max_concurrent FROM machines WHERE id = ?",
            (machine_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_machine(name, average_time=15, max_concurrent=1):
    """Insert a new machine. Returns the new row id or None on conflict."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO machines (name, average_time, max_concurrent) VALUES (?, ?, ?)",
            (name, average_time, max_concurrent),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def update_machine(machine_id, name=None, average_time=None, max_concurrent=None):
    """Update fields of an existing machine. Only non-None values are changed."""
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if average_time is not None:
        fields.append("average_time = ?")
        values.append(average_time)
    if max_concurrent is not None:
        fields.append("max_concurrent = ?")
        values.append(max_concurrent)

    if not fields:
        return False

    values.append(machine_id)
    conn = _get_connection()
    try:
        conn.execute(
            f"UPDATE machines SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def delete_machine(machine_id):
    """Delete a machine by id. Returns True if a row was deleted."""
    conn = _get_connection()
    try:
        cursor = conn.execute("DELETE FROM machines WHERE id = ?", (machine_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_machines_dict():
    """
    Return a dict in the legacy format used by the scheduler:
    { "Machine Name": {"average_time": int, "max_concurrent": int}, ... }
    """
    machines = get_all_machines()
    return {
        m["name"]: {
            "average_time": m["average_time"],
            "max_concurrent": m["max_concurrent"],
        }
        for m in machines
    }
