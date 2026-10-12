#!/usr/bin/env python3
"""One-time setup: creates the database, loads the 10 jobs and the per-role question bank, and
writes the sample inputs (JD files, question bank JSON/CSV, 10 sample CVs).

    python setup.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import DATABASE_PATH  # noqa: E402
from database.db_manager import DBManager  # noqa: E402


def main():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    DBManager().init_db()  # idempotent: CREATE TABLE IF NOT EXISTS

    import build_sample_inputs
    import seed_role_questions

    build_sample_inputs.write_jds()          # creates/updates the 10 jobs from the JD definitions
    seed_role_questions.seed()               # fixed 10 questions per role
    build_sample_inputs.write_question_bank()
    build_sample_inputs.write_cvs()
    print("\nSetup complete. Add OPENAI_API_KEY to .env, then run:  streamlit run app.py")


if __name__ == "__main__":
    main()
