-- Core Tables for AI Interview Agent

CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    cv_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    required_skills TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interviews (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('A', 'B', 'C')),
    status TEXT DEFAULT 'in_progress' CHECK(status IN ('in_progress', 'completed', 'paused')),
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    video_quality_flag INTEGER DEFAULT 0,
    injection_detected INTEGER DEFAULT 0,
    injection_details TEXT,
    feedback_json TEXT,
    planned_questions TEXT,
    FOREIGN KEY(candidate_id) REFERENCES candidates(id),
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL,
    base_question TEXT NOT NULL,
    skill_area TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK(difficulty IN ('Easy', 'Medium', 'Hard')),
    source TEXT NOT NULL CHECK(source IN ('QuestionBank', 'CV-Derived', 'JD-Derived')),
    follow_up_count INTEGER DEFAULT 0,
    question_order INTEGER NOT NULL,
    FOREIGN KEY(interview_id) REFERENCES interviews(id)
);

CREATE TABLE IF NOT EXISTS answers (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    candidate_response TEXT,
    response_type TEXT CHECK(response_type IN ('Voice', 'Video', 'Text')),
    voice_duration_sec INTEGER,
    video_path TEXT,
    transcript TEXT,
    transcription_confidence REAL,
    follow_up_flags INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(question_id) REFERENCES questions(id)
);

CREATE TABLE IF NOT EXISTS follow_ups (
    id TEXT PRIMARY KEY,
    answer_id TEXT NOT NULL,
    follow_up_order INTEGER NOT NULL CHECK(follow_up_order <= 3),
    follow_up_question TEXT NOT NULL,
    follow_up_response TEXT,
    follow_up_transcript TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(answer_id) REFERENCES answers(id)
);

CREATE TABLE IF NOT EXISTS scores (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL,
    skill_area TEXT NOT NULL,
    score INTEGER NOT NULL CHECK(score >= 1 AND score <= 5),
    justification TEXT NOT NULL,
    evidence_quote TEXT NOT NULL,
    evidence_question_id TEXT,
    scorer_agent_name TEXT,
    scoring_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(interview_id) REFERENCES interviews(id),
    FOREIGN KEY(evidence_question_id) REFERENCES questions(id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL UNIQUE,
    ai_recommendation TEXT NOT NULL CHECK(ai_recommendation IN ('Strong Hire', 'Hire', 'Hold', 'No Hire')),
    confidence TEXT NOT NULL CHECK(confidence IN ('High', 'Medium', 'Low')),
    reason_summary TEXT NOT NULL,
    technical_score REAL,
    domain_score REAL,
    problem_solving_score REAL,
    communication_score REAL,
    final_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(interview_id) REFERENCES interviews(id)
);

CREATE TABLE IF NOT EXISTS human_reviews (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL UNIQUE,
    interviewer_id TEXT NOT NULL,
    original_recommendation TEXT NOT NULL,
    final_recommendation TEXT NOT NULL,
    override_reason TEXT,
    override_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY(interview_id) REFERENCES interviews(id)
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,
    interview_id TEXT,
    agent_name TEXT NOT NULL,
    model_used TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    latency_ms INTEGER,
    cost_usd REAL,
    status TEXT CHECK(status IN ('success', 'error')),
    error_message TEXT,
    FOREIGN KEY(interview_id) REFERENCES interviews(id)
);

CREATE TABLE IF NOT EXISTS consent_records (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL UNIQUE,
    candidate_id TEXT NOT NULL,
    consent_given INTEGER DEFAULT 0,
    consent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_retention_days INTEGER DEFAULT 90,
    storage_location TEXT DEFAULT 'SQLite DB + File Storage',
    ip_address TEXT,
    user_agent TEXT,
    FOREIGN KEY(interview_id) REFERENCES interviews(id),
    FOREIGN KEY(candidate_id) REFERENCES candidates(id)
);

CREATE TABLE IF NOT EXISTS question_bank (
    id TEXT PRIMARY KEY,
    skill_area TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK(difficulty IN ('Easy', 'Medium', 'Hard')),
    question_text TEXT NOT NULL,
    category TEXT,
    role TEXT,
    question_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_interviews_candidate ON interviews(candidate_id);
CREATE INDEX IF NOT EXISTS idx_interviews_job ON interviews(job_id);
CREATE INDEX IF NOT EXISTS idx_questions_interview ON questions(interview_id);
CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id);
CREATE INDEX IF NOT EXISTS idx_scores_interview ON scores(interview_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_interview ON recommendations(interview_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_interview ON usage_logs(interview_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_timestamp ON usage_logs(timestamp);
