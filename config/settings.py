import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "videos").mkdir(exist_ok=True)
(DATA_DIR / "job_descriptions").mkdir(exist_ok=True)
(DATA_DIR / "question_bank").mkdir(exist_ok=True)
(DATA_DIR / "cvs").mkdir(exist_ok=True)

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "interviews.db"))

# Interview Configuration
INTERVIEW_MODES = ["A", "B", "C"]
MAX_FOLLOWUPS_PER_QUESTION = int(os.getenv("MAX_FOLLOWUPS_PER_QUESTION", 3))
SKILL_AREAS = [
    "Technical Skills",
    "Domain Understanding",
    "Problem Solving",
    "Communication Clarity",
]
DIFFICULTY_LEVELS = ["Easy", "Medium", "Hard"]

# Video Quality
VIDEO_QUALITY_THRESHOLD = float(os.getenv("VIDEO_QUALITY_THRESHOLD", 0.7))
MIN_BRIGHTNESS = float(os.getenv("MIN_BRIGHTNESS", 50))
MAX_BRIGHTNESS = float(os.getenv("MAX_BRIGHTNESS", 1000))

# Data Retention
TRANSCRIPT_RETENTION_DAYS = int(os.getenv("TRANSCRIPT_RETENTION_DAYS", 90))
VIDEO_RETENTION_DAYS = int(os.getenv("VIDEO_RETENTION_DAYS", 7))

# LLM Temperature Settings
LLM_TEMPERATURES = {
    "question_generator_mode_a": 0.3,
    "question_generator_mode_b": 0.5,
    "question_generator_mode_c": 0.7,
    "follow_up_adapter": 0.6,
    "scorer": 0.3,
    "recommender": 0.2,
    "injection_detector": 0.0,
}

# Scoring Rubric
SCORING_RUBRIC = {
    "Technical Skills": {
        1: "No understanding of technical concepts; cannot explain basics",
        2: "Limited technical knowledge; struggles with core concepts",
        3: "Adequate technical knowledge; understands fundamentals",
        4: "Strong technical expertise; explains concepts clearly",
        5: "Expert-level knowledge; deep understanding demonstrated",
    },
    "Domain Understanding": {
        1: "No domain knowledge; unfamiliar with industry",
        2: "Limited domain knowledge; surface-level understanding",
        3: "Good domain knowledge; understands key concepts",
        4: "Strong domain expertise; draws on experience",
        5: "Deep domain expertise; understands nuances",
    },
    "Problem Solving": {
        1: "Cannot approach problems; no logical thinking",
        2: "Weak problem-solving; incomplete approach",
        3: "Adequate problem-solving; logical approach",
        4: "Strong problem-solving; considers multiple solutions",
        5: "Excellent problem-solving; creative and thorough",
    },
    "Communication Clarity": {
        1: "Incoherent; difficult to follow",
        2: "Unclear; many rambling explanations",
        3: "Clear enough; minor clarity issues",
        4: "Very clear; well-structured explanations",
        5: "Excellent; articulate and precise",
    },
}

# Recommendation Thresholds
RECOMMENDATION_THRESHOLDS = {
    "Strong Hire": (4.3, 5.0),
    "Hire": (3.8, 4.3),
    "Hold": (2.8, 3.8),
    "No Hire": (0.0, 2.8),
}

# Bias Testing Names
BIAS_TEST_NAMES = [
    ("John Smith", "Aisha Patel"),
    ("James Wilson", "Maria Garcia"),
    ("David Chen", "Sarah Johnson"),
    ("Michael Brown", "Priya Singh"),
    ("Chris Lee", "Fatima Hassan"),
]

# Feature Flags
ENABLE_VIDEO_QUALITY_CHECK = os.getenv("ENABLE_VIDEO_QUALITY_CHECK", "true").lower() == "true"
ENABLE_INJECTION_DETECTION = os.getenv("ENABLE_INJECTION_DETECTION", "true").lower() == "true"
ENABLE_BIAS_TESTING = os.getenv("ENABLE_BIAS_TESTING", "false").lower() == "true"
ENABLE_COST_TRACKING = os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"

# Pricing (OpenAI)
OPENAI_PRICING = {
    "gpt-4-turbo": {
        "input": 0.00001,
        "output": 0.00003,
    },
    "gpt-4o": {
        "input": 0.000005,
        "output": 0.000015,
    },
    "gpt-4o-mini": {
        "input": 0.00000015,
        "output": 0.0000006,
    },
    # Approximate per-token rates for audio transcription (audio-in / text-out); verify against current OpenAI pricing
    "gpt-4o-mini-transcribe": {
        "input": 0.000003,
        "output": 0.000005,
    },
    "gpt-3.5-turbo": {
        "input": 0.0000005,
        "output": 0.0000015,
    },
}
