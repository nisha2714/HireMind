import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import uuid

from config.settings import DATABASE_PATH, PROJECT_ROOT


class DBManager:
    """SQLite database manager for interview system."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.schema_path = PROJECT_ROOT / "database" / "schema.sql"
        self._migrate()

    def _migrate(self):
        """Add columns introduced after the database was first created."""
        if not os.path.exists(self.db_path):
            return  # never create an empty database file as a side effect
        try:
            conn = sqlite3.connect(self.db_path)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(interviews)")]
            if cols and "feedback_json" not in cols:
                conn.execute("ALTER TABLE interviews ADD COLUMN feedback_json TEXT")
                conn.commit()
            if cols and "planned_questions" not in cols:
                conn.execute("ALTER TABLE interviews ADD COLUMN planned_questions TEXT")
                conn.commit()
            conn.close()
        except sqlite3.Error:
            pass

    def init_db(self):
        """Initialize database with schema."""
        with open(self.schema_path, 'r') as f:
            schema = f.read()

        conn = sqlite3.connect(self.db_path)
        conn.executescript(schema)
        conn.commit()
        conn.close()
        self._migrate()
        print(f"Database initialized at {self.db_path}")

    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # Candidate Operations
    def create_candidate(self, name: str, email: str, phone: str = None, cv_path: str = None) -> str:
        """Create a new candidate, or reuse the existing one with the same email (so a returning candidate can continue)."""
        candidate_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        existing = cursor.execute("SELECT id FROM candidates WHERE email = ?", (email,)).fetchone()
        if existing:
            cursor.execute(
                "UPDATE candidates SET name = ?, phone = COALESCE(?, phone), cv_path = COALESCE(?, cv_path) WHERE id = ?",
                (name, phone, cv_path, existing['id'])
            )
            conn.commit()
            conn.close()
            return existing['id']

        cursor.execute(
            "INSERT INTO candidates (id, name, email, phone, cv_path) VALUES (?, ?, ?, ?, ?)",
            (candidate_id, name, email, phone, cv_path)
        )

        conn.commit()
        conn.close()
        return candidate_id

    def get_candidate(self, candidate_id: str) -> Optional[Dict]:
        """Get candidate by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_candidates(self) -> List[Dict]:
        """List all candidates."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidates ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Job Operations
    def create_job(self, title: str, description: str, required_skills: str = None) -> str:
        """Create a job posting."""
        job_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO jobs (id, title, description, required_skills) VALUES (?, ?, ?, ?)",
            (job_id, title, description, required_skills)
        )

        conn.commit()
        conn.close()
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_jobs(self) -> List[Dict]:
        """List all jobs."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Interview Operations
    def create_interview(self, candidate_id: str, job_id: str, mode: str) -> str:
        """Create a new interview."""
        interview_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO interviews (id, candidate_id, job_id, mode) VALUES (?, ?, ?, ?)",
            (interview_id, candidate_id, job_id, mode)
        )

        conn.commit()
        conn.close()
        return interview_id

    def get_interview(self, interview_id: str) -> Optional[Dict]:
        """Get interview with related data."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        interview = dict(row)

        # Get candidate and job info
        interview['candidate'] = self.get_candidate(interview['candidate_id'])
        interview['job'] = self.get_job(interview['job_id'])

        # Get questions
        cursor.execute(
            "SELECT * FROM questions WHERE interview_id = ? ORDER BY question_order",
            (interview_id,)
        )
        interview['questions'] = [dict(q) for q in cursor.fetchall()]

        # Get scores
        cursor.execute(
            "SELECT * FROM scores WHERE interview_id = ?",
            (interview_id,)
        )
        interview['scores'] = [dict(s) for s in cursor.fetchall()]

        # Get recommendation
        cursor.execute(
            "SELECT * FROM recommendations WHERE interview_id = ?",
            (interview_id,)
        )
        rec = cursor.fetchone()
        interview['recommendation'] = dict(rec) if rec else None

        # Get human review
        cursor.execute(
            "SELECT * FROM human_reviews WHERE interview_id = ?",
            (interview_id,)
        )
        review = cursor.fetchone()
        interview['human_review'] = dict(review) if review else None

        conn.close()
        return interview

    def update_interview_status(self, interview_id: str, status: str):
        """Update interview status."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if status == 'completed':
            cursor.execute(
                "UPDATE interviews SET status = ?, end_time = ? WHERE id = ?",
                (status, datetime.now().isoformat(), interview_id)
            )
        else:
            cursor.execute(
                "UPDATE interviews SET status = ? WHERE id = ?",
                (status, interview_id)
            )

        conn.commit()
        conn.close()

    # Resume support
    def save_planned_questions(self, interview_id: str, questions: List[Dict]):
        """Freeze the question list chosen for this interview so it is identical after a reconnect."""
        conn = self._get_connection()
        conn.execute("UPDATE interviews SET planned_questions = ? WHERE id = ?",
                     (json.dumps(questions, default=str), interview_id))
        conn.commit()
        conn.close()

    def get_planned_questions(self, interview_id: str) -> List[Dict]:
        """Return the frozen question list, or [] if none was saved."""
        conn = self._get_connection()
        row = conn.execute("SELECT planned_questions FROM interviews WHERE id = ?", (interview_id,)).fetchone()
        conn.close()
        try:
            data = json.loads(row['planned_questions']) if row and row['planned_questions'] else []
        except (ValueError, TypeError):
            return []
        return data if isinstance(data, list) else []

    def get_resume_state(self, interview_id: str) -> Dict[str, int]:
        """Work out where an interrupted interview stands from the answers already saved.

        question_index: first base question that has no saved answer yet.
        followup_q_used: questions that already received at least one answered follow-up.
        """
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT q.question_order AS ord, COUNT(*) AS n
               FROM questions q JOIN answers a ON a.question_id = q.id
               WHERE q.interview_id = ? GROUP BY q.question_order""",
            (interview_id,)
        ).fetchall()
        conn.close()
        return {
            'question_index': (max(r['ord'] for r in rows) + 1) if rows else 0,
            'followup_q_used': sum(1 for r in rows if r['n'] > 1),
        }

    def list_resumable_interviews(self) -> List[Dict]:
        """Interviews that were started but not finished, newest first."""
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT i.id, i.mode, i.status, i.start_time, c.name AS candidate_name, c.email AS candidate_email,
                      j.title AS job_title,
                      (SELECT COUNT(DISTINCT q.question_order) FROM questions q
                         JOIN answers a ON a.question_id = q.id WHERE q.interview_id = i.id) AS answered
               FROM interviews i
               JOIN candidates c ON c.id = i.candidate_id
               JOIN jobs j ON j.id = i.job_id
               WHERE i.status IN ('in_progress', 'paused')
               ORDER BY i.start_time DESC"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # Question Operations
    def create_question(self, interview_id: str, question_text: str, skill_area: str,
                       difficulty: str, source: str, question_order: int) -> str:
        """Create a question for interview."""
        question_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO questions (id, interview_id, base_question, skill_area,
               difficulty, source, question_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (question_id, interview_id, question_text, skill_area, difficulty, source, question_order)
        )

        conn.commit()
        conn.close()
        return question_id

    def get_questions(self, interview_id: str) -> List[Dict]:
        """Get all questions for interview."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM questions WHERE interview_id = ? ORDER BY question_order",
            (interview_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Answer Operations
    def save_answer(self, question_id: str, response_type: str, transcript: str,
                   candidate_response: str = None, video_path: str = None) -> str:
        """Save answer to question."""
        answer_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO answers (id, question_id, candidate_response, response_type,
               transcript, video_path) VALUES (?, ?, ?, ?, ?, ?)""",
            (answer_id, question_id, candidate_response, response_type, transcript, video_path)
        )

        cursor.execute("SELECT interview_id, base_question FROM questions WHERE id = ?", (question_id,))
        q_row = cursor.fetchone()
        conn.commit()
        conn.close()

        # Flag prompt-injection attempts in the answer
        if q_row and transcript:
            from utils.injection_detector import InjectionDetector
            flags = InjectionDetector().scan(transcript, f"Candidate answer to: {q_row['base_question'][:80]}")
            self.add_injection_flags(q_row['interview_id'], flags)
        return answer_id

    def add_injection_flags(self, interview_id: str, flags: List[Dict]):
        """Append detected injection attempts to the interview record."""
        if not flags:
            return
        existing = self.get_injection_flags(interview_id)
        known = {(f.get('type'), f.get('excerpt'), f.get('source')) for f in existing}
        existing += [f for f in flags if (f.get('type'), f.get('excerpt'), f.get('source')) not in known]

        conn = self._get_connection()
        conn.execute(
            "UPDATE interviews SET injection_detected = 1, injection_details = ? WHERE id = ?",
            (json.dumps(existing), interview_id)
        )
        conn.commit()
        conn.close()

    def save_feedback(self, interview_id: str, feedback: Dict):
        """Store strengths / gaps / next-round focus produced at scoring time."""
        conn = self._get_connection()
        conn.execute("UPDATE interviews SET feedback_json = ? WHERE id = ?", (json.dumps(feedback), interview_id))
        conn.commit()
        conn.close()

    def get_feedback(self, interview_id: str) -> Dict:
        conn = self._get_connection()
        row = conn.execute("SELECT feedback_json FROM interviews WHERE id = ?", (interview_id,)).fetchone()
        conn.close()
        try:
            return json.loads(row['feedback_json']) if row and row['feedback_json'] else {}
        except (ValueError, TypeError):
            return {}

    def purge_expired(self, transcript_days: int, video_days: int) -> Dict[str, int]:
        """Enforce retention: delete old video files and blank out old transcripts."""
        import os
        conn = self._get_connection()
        videos = 0
        rows = conn.execute(
            "SELECT id, video_path FROM answers WHERE video_path IS NOT NULL AND created_at < datetime('now', ?)",
            (f'-{int(video_days)} days',)).fetchall()
        for r in rows:
            try:
                if os.path.exists(r['video_path']):
                    os.remove(r['video_path'])
            except OSError:
                continue
            conn.execute("UPDATE answers SET video_path = NULL WHERE id = ?", (r['id'],))
            videos += 1
        cur = conn.execute(
            "UPDATE answers SET transcript = '[removed after retention period]', candidate_response = NULL "
            "WHERE created_at < datetime('now', ?) AND transcript != '[removed after retention period]'",
            (f'-{int(transcript_days)} days',))
        transcripts = cur.rowcount
        conn.commit()
        conn.close()
        return {'videos_deleted': videos, 'transcripts_removed': transcripts}

    def get_injection_flags(self, interview_id: str) -> List[Dict]:
        """Return injection attempts recorded for this interview."""
        conn = self._get_connection()
        row = conn.execute("SELECT injection_details FROM interviews WHERE id = ?", (interview_id,)).fetchone()
        conn.close()
        try:
            return json.loads(row['injection_details']) if row and row['injection_details'] else []
        except (ValueError, TypeError):
            return []

    def get_answer(self, answer_id: str) -> Optional[Dict]:
        """Get answer by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM answers WHERE id = ?", (answer_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_answer_by_question(self, question_id: str) -> Optional[Dict]:
        """Get answer for a question."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM answers WHERE question_id = ?", (question_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # Score Operations
    def save_score(self, interview_id: str, skill_area: str, score: int,
                  justification: str, evidence_quote: str, question_id: str = None) -> str:
        """Save score for interview."""
        score_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO scores (id, interview_id, skill_area, score, justification,
               evidence_quote, evidence_question_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (score_id, interview_id, skill_area, score, justification, evidence_quote, question_id)
        )

        conn.commit()
        conn.close()
        return score_id

    def get_scores(self, interview_id: str) -> List[Dict]:
        """Get all scores for interview."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM scores WHERE interview_id = ? ORDER BY scoring_timestamp ASC",
            (interview_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Recommendation Operations
    def save_recommendation(self, interview_id: str, recommendation: str,
                           confidence: str, reason: str, scores: Dict[str, float]) -> str:
        """Save AI recommendation."""
        rec_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        final_score = sum(scores.values()) / len(scores) if scores else 0.0

        cursor.execute(
            """INSERT INTO recommendations
               (id, interview_id, ai_recommendation, confidence, reason_summary,
                technical_score, domain_score, problem_solving_score, communication_score, final_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rec_id, interview_id, recommendation, confidence, reason,
             scores.get('Technical Skills', 0),
             scores.get('Domain Understanding', 0),
             scores.get('Problem Solving', 0),
             scores.get('Communication Clarity', 0),
             final_score)
        )

        conn.commit()
        conn.close()
        return rec_id

    def get_recommendation(self, interview_id: str) -> Optional[Dict]:
        """Get recommendation for interview."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM recommendations WHERE interview_id = ?", (interview_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # Human Review Operations
    def save_human_review(self, interview_id: str, interviewer_id: str,
                         original_rec: str, final_rec: str, override_reason: str = None, notes: str = None):
        """Save human review and override."""
        review_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO human_reviews
               (id, interview_id, interviewer_id, original_recommendation, final_recommendation, override_reason, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (review_id, interview_id, interviewer_id, original_rec, final_rec, override_reason, notes)
        )

        conn.commit()
        conn.close()
        return review_id

    # Usage Logging
    def log_usage(self, interview_id: str, agent_name: str, model: str,
                 input_tokens: int, output_tokens: int, latency_ms: int,
                 cost_usd: float, status: str = 'success', error_msg: str = None):
        """Log LLM usage."""
        log_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO usage_logs
               (id, interview_id, agent_name, model_used, input_tokens, output_tokens,
                latency_ms, cost_usd, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (log_id, interview_id, agent_name, model, input_tokens, output_tokens,
             latency_ms, cost_usd, status, error_msg)
        )

        conn.commit()
        conn.close()

    def get_usage_logs(self, interview_id: str) -> List[Dict]:
        """Get usage logs for interview."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM usage_logs WHERE interview_id = ? ORDER BY timestamp DESC",
            (interview_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Question Bank Operations
    def load_question_bank(self) -> List[Dict]:
        """Load question bank."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM question_bank")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_question_to_bank(self, skill_area: str, difficulty: str,
                            question_text: str, category: str = None) -> str:
        """Add question to question bank."""
        question_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO question_bank (id, skill_area, difficulty, question_text, category)
               VALUES (?, ?, ?, ?, ?)""",
            (question_id, skill_area, difficulty, question_text, category)
        )

        conn.commit()
        conn.close()
        return question_id

    # Consent Operations
    def save_consent(self, interview_id: str, candidate_id: str, consent_given: bool):
        """Save consent record."""
        consent_id = str(uuid.uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO consent_records (id, interview_id, candidate_id, consent_given)
               VALUES (?, ?, ?, ?)""",
            (consent_id, interview_id, candidate_id, 1 if consent_given else 0)
        )

        conn.commit()
        conn.close()

    def get_consent(self, interview_id: str) -> Optional[Dict]:
        """Get consent record."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM consent_records WHERE interview_id = ?", (interview_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
