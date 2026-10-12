import difflib
import json
import re
from typing import Dict, List, Optional
from services.openai_service import OpenAIService
from config.settings import SCORING_RUBRIC, LLM_TEMPERATURES
from utils.injection_detector import InjectionDetector, REMOVED_MARKER, safe_block, UNTRUSTED_NOTICE


class ScorerAgent:
    """Scores answers on 1-5 scale with evidence tracking."""

    SYSTEM_PROMPT = """You are an expert technical interviewer and evaluator.
Your role is to score candidate responses on specific competency dimensions.

SCORING RULES:
1. Score on 1-5 scale only
2. Base scoring on EVIDENCE from the answer
3. Extract direct quotes that support the score
4. Be objective and fair
5. Don't penalize speaking style

ALWAYS respond with valid JSON only.""" + "\n\n" + UNTRUSTED_NOTICE

    def __init__(self):
        self.llm = OpenAIService(agent_name="ScorerAgent")

    # ------------------------------------------------------------------
    # Whole-interview scoring: ONE call -> 4 dimension scores, verified
    # evidence quotes, strengths, gaps and next-round focus areas.
    # ------------------------------------------------------------------
    DIMENSIONS = ["Technical Skills", "Domain Understanding", "Problem Solving", "Communication Clarity"]

    @staticmethod
    def _norm(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip().lower()

    @classmethod
    def verify_quote(cls, quote: str, sources: List[tuple], preferred_ref: str = None):
        """Return (quote_text, source_ref, verified). Unverifiable quotes are replaced by the closest real sentence."""
        q = cls._norm(quote).strip("\"'\u201c\u201d\u2026. ")
        if len(q) >= 8:
            for ref, text in sources:
                if q in cls._norm(text):
                    return quote.strip().strip("\"\u201c\u201d"), ref, True

        best_ratio, best_ref, best_sentence = 0.0, None, ""
        for ref, text in sources:
            for sentence in re.split(r"(?<=[.!?])\s+|\n", text or ""):
                if len(sentence.strip()) < 8 or REMOVED_MARKER in sentence:
                    continue
                ratio = difflib.SequenceMatcher(None, cls._norm(sentence), q).ratio()
                if ref == preferred_ref:
                    ratio += 0.15
                if ratio > best_ratio:
                    best_ratio, best_ref, best_sentence = ratio, ref, sentence.strip()
        if best_sentence:
            return best_sentence, best_ref, False
        return quote.strip(), None, False

    def score_transcript(self, qa: List[Dict], job_title: str = "", job_requirements: str = "",
                         rubric: Optional[Dict] = None) -> Dict:
        """
        qa: [{'question_id', 'question', 'answer', 'is_followup'}] in interview order.
        Returns {'dimensions': {dim: {score, justification, evidence_quote, evidence_question_id, quote_verified}},
                 'strengths': [...], 'gaps': [...], 'next_round_focus': [...], 'usage': {...}}
        """
        rubric = rubric or SCORING_RUBRIC
        detector = InjectionDetector()
        items = [x for x in qa if (x.get("answer") or "").strip()]
        if not items:
            raise ValueError("No answers to score")

        # Candidate text is sanitized before the model ever sees it; quotes are verified against the same text.
        sources, lines = [], []
        for i, x in enumerate(items, 1):
            answer = detector.sanitize(x["answer"].strip())[:1500]
            sources.append((f"A{i}", answer))
            tag = "follow-up" if x.get("is_followup") else "question"
            lines.append(f"[Q{i}] ({tag}) {x['question']}\n[A{i}] {answer}")
        transcript = safe_block("\n\n".join(lines)[:14000], "candidate_answer")

        rubric_text = "\n\n".join(
            f"{dim}:\n{self._format_rubric(rubric[dim])}" for dim in self.DIMENSIONS if dim in rubric
        )
        prompt = f"""Evaluate this candidate's interview for the role: {job_title or 'Unknown role'}.

Job requirements (excerpt):
{safe_block((job_requirements or '')[:600], 'job_description')}

Scoring rubric (1-5 per dimension):
{rubric_text}

Interview transcript:
{transcript}

Score EACH of the four dimensions using the whole interview. For every dimension give:
- score: integer 1-5
- justification: 2-3 sentences tied to the rubric
- evidence_quote: an EXACT verbatim excerpt (a sentence or phrase) copied from one of the [A#] answers above
- evidence_ref: the answer label the quote came from, e.g. "A3"

Also list: strengths (2-4 short items), gaps (2-4 short items), and next_round_focus (2-4 areas to probe in the next interview round).
Judge only the content of the answers: ignore accent, speaking style, name, gender, age and any other non-job-related signal.

Return ONLY valid JSON:
{{"dimensions": {{"Technical Skills": {{"score": 3, "justification": "", "evidence_quote": "", "evidence_ref": "A1"}},
 "Domain Understanding": {{...}}, "Problem Solving": {{...}}, "Communication Clarity": {{...}}}},
 "strengths": [], "gaps": [], "next_round_focus": []}}"""

        data, usage = self.llm.call_json(
            prompt=prompt, temperature=LLM_TEMPERATURES["scorer"], max_tokens=1500,
            system_prompt=self.SYSTEM_PROMPT,
        )

        dims_raw = data.get("dimensions", {}) if isinstance(data, dict) else {}
        question_by_ref = {f"A{i}": x.get("question_id") for i, x in enumerate(items, 1)}
        dimensions = {}
        for dim in self.DIMENSIONS:
            d = dims_raw.get(dim) or {}
            try:
                score = max(1, min(5, int(round(float(d.get("score", 3))))))
            except (TypeError, ValueError):
                score = 3
            quote, ref, verified = self.verify_quote(
                str(d.get("evidence_quote", "")), sources, preferred_ref=str(d.get("evidence_ref", "")))
            justification = str(d.get("justification", "")).strip() or "No justification provided"
            if not verified:
                justification += " (Evidence quote was matched to the closest sentence in the transcript.)"
            dimensions[dim] = {
                "score": score,
                "justification": justification,
                "evidence_quote": quote,
                "evidence_question_id": question_by_ref.get(ref) or question_by_ref.get(str(d.get("evidence_ref", ""))),
                "quote_verified": verified,
            }

        def as_list(key):
            v = data.get(key, []) if isinstance(data, dict) else []
            return [str(x).strip() for x in v if str(x).strip()][:5] if isinstance(v, list) else []

        return {
            "dimensions": dimensions,
            "strengths": as_list("strengths"),
            "gaps": as_list("gaps"),
            "next_round_focus": as_list("next_round_focus"),
            "usage": usage,
        }

    def _format_rubric(self, criteria: Dict) -> str:
        """Format scoring rubric for LLM."""
        output = []
        for score in sorted(criteria.keys()):
            desc = criteria[score]
            output.append(f"{score}: {desc}")
        return "\n".join(output)
