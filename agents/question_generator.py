import json
from typing import Dict, List, Optional
from services.openai_service import OpenAIService
from config.settings import LLM_TEMPERATURES
from utils.injection_detector import InjectionDetector, safe_block, UNTRUSTED_NOTICE


class QuestionGeneratorAgent:
    """Generates interview questions based on mode and context."""

    SYSTEM_PROMPT = """You are an expert technical interviewer and question designer.
Your role is to create interview questions that effectively assess candidate skills.

Guidelines:
1. Questions should be specific and open-ended
2. Avoid yes/no questions
3. Test practical knowledge and problem-solving
4. Adapt to candidate's experience level
5. Be fair and non-discriminatory

For Mode A: Select from question bank matching skill area and difficulty.
For Mode B: Select from bank AND adapt based on CV context.
For Mode C: Generate custom questions based on CV and JD.

Always return ONLY the question text, no explanations.""" + "\n\n" + UNTRUSTED_NOTICE

    def __init__(self, mode: str = "A"):
        self.llm = OpenAIService(agent_name=f"QuestionGenerator-Mode{mode}")
        self.mode = mode
        if mode not in ["A", "B", "C"]:
            raise ValueError(f"Invalid mode: {mode}. Must be A, B, or C")

    MAX_RETRIES = 2

    def next_followup(self, history: List[Dict], cv: str = "", job_description: str = "",
                      max_followups: int = 2) -> tuple[Optional[str], Dict]:
        """Decide if ONE more follow-up is warranted given the Q&A so far; return it or None.

        history: [{"q": ..., "a": ...}, ...] - the base question first, then any follow-ups.
        """
        asked = len(history) - 1
        thread = safe_block("\n".join(f"Q{i + 1}: {h['q']}\nA{i + 1}: {h['a'][:1200]}" for i, h in enumerate(history)), "candidate_answer")
        strictness = (
            "DEFAULT to needs_followup=false. Set it true ONLY if the answer is vague, very short, factually wrong, "
            "lacks any concrete example, or contradicts the CV. An answer that is correct, specific and gives an example is COMPLETE."
            if asked == 0 else
            "A follow-up was already asked. DEFAULT to needs_followup=false; ask another ONLY if the last answer "
            "is still vague or clearly misses an important point."
        )
        prompt = f"""You are interviewing a candidate. Review the exchange and decide whether ONE more follow-up question is truly needed.

Exchange so far:
{thread}

Candidate CV (excerpt):
{safe_block(cv[:2000] or '(not provided)', 'candidate_cv')}

Job description (excerpt):
{safe_block(job_description[:600], 'job_description')}

{strictness}
If the answer was already clear and thorough, no follow-up is needed - most answers should NOT get one.
If the candidate says they do not know or cannot answer, set needs_followup=false (do not rephrase, hint or re-ask).A follow-up must build directly on the candidate's LAST answer (and may verify a CV claim), be open-ended, and not repeat earlier questions.
This would be follow-up number {asked + 1} of at most {max_followups}.

Return JSON only: {{"needs_followup": true or false, "question": "<follow-up text, or empty>"}}"""

        data, usage = self.llm.call_json(
            prompt=prompt,
            temperature=0.2,
            max_tokens=150,
            system_prompt=self.SYSTEM_PROMPT,
        )
        question = str(data.get("question", "")).strip()
        if data.get("needs_followup") and question:
            return question, usage
        return None, usage

    def generate_cv_followups(self, base_question: str, answer: str, cv: str,
                              job_description: str = "", num: int = 2) -> tuple[List[str], Dict]:
        """Mode B: one call returning `num` distinct follow-ups that verify CV claims."""
        prompt = f"""A candidate answered an interview question. Write {num} DISTINCT follow-up questions
that verify claims made in their CV and probe the depth of their answer.

Question asked: {base_question}
Candidate's answer:
{safe_block(answer[:1500], 'candidate_answer')}

Candidate CV:
{safe_block(cv[:2500], 'candidate_cv')}

Job description (context):
{safe_block(job_description[:600], 'job_description')}

Rules: each follow-up must reference a specific item from the CV (project, skill, tool or claim),
be open-ended, and test something different from the other. Do not repeat the original question.
Return JSON only: {{"followups": ["...", "..."]}}"""

        total = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        for _ in range(self.MAX_RETRIES + 1):
            data, usage = self.llm.call_json(
                prompt=prompt,
                temperature=LLM_TEMPERATURES["question_generator_mode_b"],
                max_tokens=300,
                system_prompt=self.SYSTEM_PROMPT,
            )
            for k in total:
                total[k] += usage.get(k, 0)
            items = [str(x).strip() for x in data.get("followups", []) if str(x).strip()]
            unique = list(dict.fromkeys(items))
            if len(unique) >= num:
                return unique[:num], total
        raise ValueError("Could not generate distinct CV follow-ups")

    def generate_cv_jd_questions(self, cv: str, job_description: str, role_level: str,
                                 num: int = 10) -> tuple[List[Dict], Dict]:
        """Mode C: one call returning all `num` distinct questions from CV + JD."""
        plan = {"Technical Skills": 3, "Domain Understanding": 3, "Problem Solving": 2, "Communication Clarity": 2}
        plan_str = ", ".join(f"{n} x {s}" for s, n in plan.items())
        level = "fresher / entry level" if role_level == "Easy" else "senior level"
        difficulty = "Easy" if role_level == "Easy" else "Medium"

        prompt = f"""Create exactly {num} interview questions for a {level} candidate.

Job description:
{safe_block(job_description[:2000], 'job_description')}

Candidate CV:
{safe_block(cv[:2500], 'candidate_cv')}

Distribution: {plan_str}.
Rules: every question is specific to the job requirements, references something from the CV where relevant,
is open-ended, and covers a different topic from all the others (no duplicates or near-duplicates).
Return JSON only: {{"questions": [{{"skill_area": "<one of the skill areas above>", "question": "..."}}]}}"""

        total = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        for _ in range(self.MAX_RETRIES + 1):
            data, usage = self.llm.call_json(
                prompt=prompt,
                temperature=LLM_TEMPERATURES["question_generator_mode_c"],
                max_tokens=1500,
                system_prompt=self.SYSTEM_PROMPT,
            )
            for k in total:
                total[k] += usage.get(k, 0)

            seen, questions = set(), []
            for item in data.get("questions", []):
                text = str(item.get("question", "")).strip()
                skill = item.get("skill_area")
                if not text or text.lower() in seen:
                    continue
                seen.add(text.lower())
                questions.append({
                    "id": str(len(questions) + 1),
                    "question_text": text,
                    "skill_area": skill if skill in plan else "Technical Skills",
                    "difficulty": difficulty,
                    "source": "LLM-Generated-CV-JD",
                })
            if len(questions) >= num:
                return questions[:num], total
        raise ValueError(f"Could not generate {num} distinct questions after {self.MAX_RETRIES + 1} attempts")
