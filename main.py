from fastmcp import FastMCP
import os
import sqlite3
from pathlib import Path
from datetime import date, timedelta
import json

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "habits.db"
CATEGORIES_PATH = BASE_DIR / "category.json"

mcp = FastMCP("HabitTracker")


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Habbitlogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                habit TEXT NOT NULL,
                habit_description TEXT NOT NULL,
                category TEXT NOT NULL,
                sub_category TEXT NOT NULL,
                completed BOOLEAN NOT NULL,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
init_db()

@mcp.tool()
def log_habit(user_id: int, habit: str, habit_description: str, category: str, sub_category: str, completed: bool) -> dict:
    """
    Log a habit for a user.

    Args:
        user_id (int): The ID of the user.
        habit (str): The name of the habit.
        habit_description (str): A description of the habit.
        category (str): The category of the habit.
        sub_category (str): The sub-category of the habit.
        completed (bool): Whether the habit was completed or not.
    """
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO Habbitlogs(user_id, habit, habit_description, category, sub_category, completed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, habit.strip(), habit_description.strip(), category, sub_category, completed)
        )
    return {"message": "Habit logged successfully.", "status": "success", "id":conn.execute("SELECT last_insert_rowid()").fetchone()[0]}

@mcp.tool()
def get_habits(user_id: int)->list[dict]:
    """
    get all habits for the user.

    Args:
        user_id (int): The ID of the user.
    """
    with get_conn() as conn:
        rows = conn.execute(
        """
        SELECT * FROM Habbitlogs 
        WHERE user_id = ?
        """,
        (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]

@mcp.tool()
def get_habit_progress(user_id: int, category: str, days: int = 30) -> dict:
    """Get chronological habit logs and consistency metrics for a user and category over the past N days."""
    if days < 1:
        return {"error": "days must be at least 1"}

    today = date.today()
    start_date = today - timedelta(days=days - 1)

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                habit,
                habit_description,
                sub_category,
                completed,
                logged_at,
                DATE(logged_at) AS log_date
            FROM Habbitlogs
            WHERE user_id = ?
              AND LOWER(category) = LOWER(?)
              AND DATE(logged_at) BETWEEN ? AND ?
            ORDER BY logged_at ASC
            """,
            (
                user_id,
                category.strip(),
                start_date.isoformat(),
                today.isoformat(),
            ),
        ).fetchall()

    entries = [
        {
            "id": row["id"],
            "habit": row["habit"],
            "habit_description": row["habit_description"],
            "sub_category": row["sub_category"],
            "completed": bool(row["completed"]),
            "logged_at": row["logged_at"],
        }
        for row in rows
    ]

    completed_days = {row["log_date"] for row in rows if row["completed"]}
    completed_entries = sum(1 for e in entries if e["completed"])

    return {
        "user_id": user_id,
        "category": category.strip().lower(),
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": today.isoformat(),
            "days": days,
        },
        "summary": {
            "total_entries": len(entries),
            "completed_entries": completed_entries,
            "days_completed": len(completed_days),
            "consistency_rate_pct": round((len(completed_days) / days) * 100, 1),
        },
        "entries": entries,
    }

@mcp.resource("habits://categories", mime_type="application/json")
def get_categories() -> list[dict]:
    """
    Get all categories from the category.json file.
    """
    if not CATEGORIES_PATH.exists():
        return {"error": "Categories file not found."}

    with open(CATEGORIES_PATH, "r") as f:
        categories = json.load(f)

    return categories
if __name__ == "__main__":
    mcp.run()

