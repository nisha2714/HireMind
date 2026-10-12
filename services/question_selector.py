"""Select/generate interview questions based on mode."""
from typing import List, Dict
from database.db_manager import DBManager
from agents.question_generator import QuestionGeneratorAgent


class QuestionSelector:
    """Select or generate questions based on interview mode."""

    @staticmethod
    def select_questions(mode: str, job_description: str, candidate_cv: str, role_level: str, job_title: str = "") -> List[Dict]:
        """
        Select or generate questions based on mode.

        Mode A: Select from database only (filtered by job role)
        Mode B: Select from database + will generate follow-ups from CV
        Mode C: Generate all questions from CV + JD using LLM

        Args:
            mode: "A", "B", or "C"
            job_description: Job description text
            candidate_cv: Candidate CV text
            role_level: "Easy" for fresher, "Medium" or "Hard" for senior
            job_title: Job title for role-based filtering in Mode A

        Returns:
            List of question dicts
        """

        if mode == "A":
            return QuestionSelector._mode_a_questions(role_level, job_title, job_description)

        elif mode == "B":
            return QuestionSelector._mode_b_questions(role_level, candidate_cv, job_title)

        elif mode == "C":
            return QuestionSelector._mode_c_questions(job_description, candidate_cv, role_level)

        else:
            raise ValueError(f"Invalid mode: {mode}")

    @staticmethod
    def _role_bank_questions(job_title: str) -> List[Dict]:
        """Return the fixed, ordered question set prepared for this role."""
        conn = DBManager()._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM question_bank WHERE role = ? ORDER BY question_order",
            (job_title,)
        )
        questions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return questions

    @staticmethod
    def _mode_a_questions(role_level: str, job_title: str = "", job_description: str = "") -> List[Dict]:
        """Mode A: only the questions prepared for the role, same set for every candidate."""
        return QuestionSelector._role_bank_questions(job_title)

    @staticmethod
    def _mode_b_questions(role_level: str, candidate_cv: str, job_title: str = "") -> List[Dict]:
        """Mode B: role question bank; CV-based follow-ups are generated per answer."""
        return QuestionSelector._role_bank_questions(job_title)

    @staticmethod
    def _mode_c_questions(job_description: str, candidate_cv: str, role_level: str) -> List[Dict]:
        """Mode C: generate all questions from CV + JD in a single LLM call."""
        generator = QuestionGeneratorAgent(mode="C")
        questions, _usage = generator.generate_cv_jd_questions(candidate_cv, job_description, role_level, num=10)
        return questions