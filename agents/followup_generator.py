"""Generate follow-up questions based on candidate answers."""

import re
from typing import List, Dict
from database.db_manager import DBManager


class FollowUpGenerator:
    """Generate contextual follow-up questions."""

    # Follow-up templates (stored in memory, can be moved to DB)
    FOLLOWUP_TEMPLATES = {
        "Technical Skills": [
            "You mentioned {skill}. Can you describe the most complex {skill} project you worked on?",
            "What were the biggest challenges you faced with {skill} and how did you solve them?",
            "If you were to redesign a {skill} system today, what would you do differently?"
        ],
        "Domain Understanding": [
            "You mentioned {skill}. How does that apply to your current industry?",
            "Can you elaborate on your experience with {skill} in real-world scenarios?",
            "What best practices have you learned about {skill} over the years?"
        ],
        "Problem Solving": [
            "You mentioned solving a {skill} problem. Walk us through your approach.",
            "What was the most critical issue you debugged related to {skill}?",
            "How would you handle a similar {skill} problem with different constraints?"
        ],
        "Communication Clarity": [
            "Can you explain {skill} to a non-technical person in your organization?",
            "How do you communicate {skill} concepts to your team?",
            "Describe a time you had to explain a {skill} decision to stakeholders."
        ]
    }

    def __init__(self):
        self.db = DBManager()

    def extract_keywords(self, text: str) -> List[str]:
        """
        Extract technical keywords from candidate answer.

        Args:
            text: Candidate's answer text

        Returns:
            List of extracted keywords
        """
        text_lower = text.lower()

        # Common technical keywords to look for
        keywords_list = [
            'python', 'java', 'go', 'rust', 'javascript', 'typescript',
            'sql', 'nosql', 'mongodb', 'postgresql', 'redis',
            'api', 'rest', 'graphql', 'grpc',
            'docker', 'kubernetes', 'microservice', 'serverless',
            'aws', 'gcp', 'azure', 'cloud',
            'git', 'ci/cd', 'devops', 'jenkins',
            'machine learning', 'ai', 'deep learning', 'nlp',
            'testing', 'unittest', 'pytest', 'integration test',
            'performance', 'optimization', 'scalability', 'distributed',
            'leadership', 'team', 'mentoring', 'communication'
        ]

        found_keywords = []
        for kw in keywords_list:
            if kw in text_lower:
                # Capitalize for display
                found_keywords.append(kw.title())

        return found_keywords

    def generate_followups(
        self,
        question_id: str,
        candidate_answer: str,
        skill_area: str,
        num_followups: int = 3
    ) -> List[Dict]:
        """
        Generate follow-up questions based on candidate's answer.

        Args:
            question_id: ID of the main question
            candidate_answer: Candidate's response text
            skill_area: Skill area of the main question
            num_followups: Number of follow-ups to generate (1-3)

        Returns:
            List of follow-up question dicts
        """

        # Extract keywords from answer
        keywords = self.extract_keywords(candidate_answer)

        if not keywords:
            # Fallback: use first word that looks like a technical term
            words = candidate_answer.split()
            keywords = [w for w in words if len(w) > 4][:3]

        # Get templates for this skill area
        templates = self.FOLLOWUP_TEMPLATES.get(skill_area, [])

        if not templates:
            # Fallback templates
            templates = [
                "You mentioned {skill}. Can you elaborate?",
                "What challenges did you face with {skill}?",
                "How would you approach this differently with {skill}?"
            ]

        # Generate follow-ups
        followups = []
        for i in range(min(num_followups, len(templates))):
            template = templates[i]

            # Get keyword for this follow-up
            keyword = keywords[i % len(keywords)] if keywords else "this technology"

            # Fill template
            followup_text = template.format(skill=keyword)

            followups.append({
                'sequence': i + 1,
                'question_text': followup_text,
                'skill_area': skill_area,
                'difficulty': self._increase_difficulty(['Easy', 'Medium', 'Hard'][i // 2 % 3], i),
                'source': 'FollowUp',
                'parent_question_id': question_id
            })

        return followups

    def _increase_difficulty(self, base_difficulty: str, sequence: int) -> str:
        """Increase difficulty for each follow-up."""
        difficulty_levels = ['Easy', 'Medium', 'Hard']
        base_idx = difficulty_levels.index(base_difficulty)
        new_idx = min(base_idx + sequence // 2, 2)
        return difficulty_levels[new_idx]
