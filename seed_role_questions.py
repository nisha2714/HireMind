"""Add role columns to question_bank and (re)load the fixed per-role questions. Safe to re-run."""
import sqlite3
import uuid

from config.settings import DATABASE_PATH
from data.role_questions import ROLE_QUESTIONS


def seed():
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(question_bank)")]
    if "role" not in cols:
        cur.execute("ALTER TABLE question_bank ADD COLUMN role TEXT")
    if "question_order" not in cols:
        cur.execute("ALTER TABLE question_bank ADD COLUMN question_order INTEGER DEFAULT 0")

    cur.execute("DELETE FROM question_bank WHERE role IS NOT NULL")
    for role, (difficulty, items) in ROLE_QUESTIONS.items():
        for order, (skill, text) in enumerate(items, 1):
            cur.execute(
                "INSERT INTO question_bank (id, skill_area, difficulty, question_text, category, role, question_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), skill, difficulty, text, "RoleBank", role, order),
            )
    conn.commit()
    for role, n in cur.execute("SELECT role, COUNT(*) FROM question_bank WHERE role IS NOT NULL GROUP BY role"):
        print(f"{role}: {n}")
    conn.close()


if __name__ == "__main__":
    seed()
