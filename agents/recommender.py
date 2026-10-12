import json
import numpy as np
from typing import Dict
from services.openai_service import OpenAIService
from utils.injection_detector import safe_block, UNTRUSTED_NOTICE
from config.settings import RECOMMENDATION_THRESHOLDS, LLM_TEMPERATURES


class RecommenderAgent:
    """Generates hire/hold/no-hire recommendation."""

    RECOMMENDATIONS = ["Strong Hire", "Hire", "Hold", "No Hire"]

    SYSTEM_PROMPT = """You are a senior hiring manager making final recommendations.
Your role is to synthesize interview scores into a hiring recommendation.

Be objective, fair, and consider:
1. Score levels and consistency
2. Critical skills for the role
3. Growth potential
4. Communication ability

ALWAYS respond with valid JSON only.""" + "\n\n" + UNTRUSTED_NOTICE

    def __init__(self):
        self.llm = OpenAIService(agent_name="RecommenderAgent")

    def generate_recommendation(self, scores: Dict[str, float], context: Dict) -> Dict:
        """
        Generate hiring recommendation.

        Args:
            scores: {
                'Technical Skills': float,
                'Domain Understanding': float,
                'Problem Solving': float,
                'Communication Clarity': float,
            }
            context: {
                'job_title': str,
                'requirements': str,
                'cv': str,
            }

        Returns:
            {
                'recommendation': str,
                'confidence': str,
                'reason_summary': str,
                'scores_summary': Dict,
            }
        """
        overall_score = (
            sum(scores.values()) / len(scores) if scores else 0.0
        )

        prompt = f"""Generate a hiring recommendation based on:

Job: {context.get('job_title', 'Unknown Position')}

Candidate Scores (out of 5):
- Technical Skills: {scores.get('Technical Skills', 0):.2f}
- Domain Understanding: {scores.get('Domain Understanding', 0):.2f}
- Problem Solving: {scores.get('Problem Solving', 0):.2f}
- Communication Clarity: {scores.get('Communication Clarity', 0):.2f}
- Overall: {overall_score:.2f}

Job Requirements:
{context.get('requirements', '')[:300]}

Candidate Background (excerpt):
{safe_block((context.get('cv') or '')[:300], 'candidate_cv')}

Score Thresholds:
- Strong Hire: 4.3+ (High confidence)
- Hire: 3.8-4.2 (High confidence)
- Hold: 2.8-3.7 (Medium confidence - gaps exist)
- No Hire: <2.8 (High confidence)

Make a recommendation considering:
1. Alignment with job requirements
2. Score consistency
3. Communication ability
4. Technical depth

Respond with ONLY valid JSON:
{{
    "recommendation": "<Strong Hire|Hire|Hold|No Hire>",
    "confidence": "<High|Medium|Low>",
    "reason_summary": "<1-2 sentence reason>",
    "detailed_reasoning": "<explanation>"
}}"""

        temperature = LLM_TEMPERATURES["recommender"]

        try:
            response_json, usage = self.llm.call_json(
                prompt=prompt,
                temperature=temperature,
                max_tokens=500,
                system_prompt=self.SYSTEM_PROMPT,
            )
        except Exception as e:
            # Fallback to rule-based recommendation if API fails
            recommendation = self._map_to_recommendation(overall_score)
            return {
                "recommendation": recommendation,
                "confidence": "Medium",
                "reason_summary": f"Assessment based on interview scores (API error: {str(e)[:50]})",
                "detailed_reasoning": "",
                "overall_score": overall_score,
                "scores": scores,
                "usage": {"error": str(e)},
            }

        # Validate recommendation
        recommendation = response_json.get("recommendation", "Hold") if response_json else "Hold"
        if recommendation not in self.RECOMMENDATIONS:
            recommendation = self._map_to_recommendation(overall_score)

        result = {
            "recommendation": recommendation,
            "confidence": response_json.get("confidence", "Medium") if response_json else "Medium",
            "reason_summary": response_json.get(
                "reason_summary", "Assessment based on interview scores"
            ) if response_json else "Assessment based on interview scores",
            "detailed_reasoning": response_json.get("detailed_reasoning", "") if response_json else "",
            "overall_score": overall_score,
            "scores": scores,
            "usage": usage if 'usage' in locals() else {},
        }

        return result

    def _map_to_recommendation(self, overall_score: float) -> str:
        """Map score to recommendation."""
        for recommendation, (min_score, max_score) in RECOMMENDATION_THRESHOLDS.items():
            if min_score <= overall_score <= max_score:
                return recommendation
        return "No Hire"
