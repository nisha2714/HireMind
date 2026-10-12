import os
import streamlit as st
import sys
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup page configuration
st.set_page_config(
    page_title="HireMind | AI Interview Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
    .block-container { padding-top: 2rem; max-width: 1200px; }
    h1, h2, h3 { color: #1E1B4B; letter-spacing: -0.01em; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #1E1B4B 0%, #312E81 100%); }
    [data-testid="stSidebar"] * { color: #E0E7FF !important; }
    [data-testid="stSidebar"] hr { border-color: rgba(224,231,255,.25); }
    .stButton > button {
        height: 46px; font-size: 15px; font-weight: 600; border-radius: 10px;
        border: 1px solid #C7D2FE; transition: all .15s ease;
    }
    .stButton > button:hover { border-color: #4F46E5; color: #4F46E5; transform: translateY(-1px); }
    .stButton > button[kind="primary"], .stFormSubmitButton > button { background: #4F46E5; color: #fff; border: none; }
    .hero {
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 55%, #0EA5E9 100%);
        border-radius: 18px; padding: 2.4rem 2.2rem; color: #fff; margin-bottom: 1.5rem;
    }
    .hero h1 { color: #fff; font-size: 2.6rem; margin: 0 0 .3rem 0; }
    .hero p { color: #E0E7FF; font-size: 1.1rem; margin: 0; }
    .mode-card {
        background: #fff; border: 1px solid #E2E8F0; border-top: 4px solid #4F46E5;
        border-radius: 14px; padding: 1.2rem 1.3rem; height: 100%;
        box-shadow: 0 1px 3px rgba(15,23,42,.06);
    }
    .mode-card .tag { font-size: .75rem; font-weight: 700; letter-spacing: .08em; color: #4F46E5; }
    .mode-card h3 { margin: .2rem 0 .4rem 0; font-size: 1.15rem; }
    .mode-card p { color: #475569; margin: 0; font-size: .93rem; }
    .feat { background: #EEF2FF; border-radius: 10px; padding: .6rem .9rem; margin-bottom: .5rem;
            color: #312E81; font-size: .93rem; font-weight: 500; }
    </style>
    """, unsafe_allow_html=True)

from database.db_manager import DBManager
from config.settings import DATABASE_PATH
from agents.question_generator import QuestionGeneratorAgent
from agents.scorer import ScorerAgent
from agents.recommender import RecommenderAgent
from agents.report_generator import ReportGeneratorAgent
from agents.followup_generator import FollowUpGenerator
from services.cv_parser import read_cv
from utils.answer_checks import is_non_answer

def init_session_state():
    """Initialize session state."""
    if 'page' not in st.session_state:
        st.session_state.page = 'home'
    if 'interview_id' not in st.session_state:
        st.session_state.interview_id = None
    if 'question_index' not in st.session_state:
        st.session_state.question_index = 0

def resume_interview(db, interview_id):
    """Re-enter an unfinished interview at the first unanswered question."""
    state = db.get_resume_state(interview_id)
    st.session_state.interview_id = interview_id
    st.session_state.question_index = state['question_index']
    st.session_state.followup_q_used = state['followup_q_used']
    st.session_state.generated_questions = None  # reloaded from the saved list on the next screen
    st.session_state.followup_state = None
    st.session_state.role_context = None
    st.session_state.page = 'interview_flow'
    st.rerun()


def show_resume_section():
    """List unfinished interviews so a disconnected candidate can continue where they stopped."""
    try:
        db = DBManager()
        pending = db.list_resumable_interviews()
    except Exception:
        return
    if not pending:
        return

    st.write("")
    st.subheader("Resume an unfinished interview")
    st.caption("Answers already given are saved. Resuming continues at the first unanswered question.")
    for row in pending:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{row['candidate_name']}** - {row['job_title']} (Mode {row['mode']}) - "
                 f"{row['answered']} question(s) answered - started {(row['start_time'] or '')[:16]}")
        if c2.button("Resume", key=f"resume_{row['id']}", use_container_width=True):
            resume_interview(db, row['id'])


def show_home():
    """Home page - Introduction."""
    st.markdown("""
        <div class="hero">
            <h1>🧠 HireMind</h1>
            <p>Structured interviews. Evidence-backed hiring.</p>
        </div>
        """, unsafe_allow_html=True)

    modes = [
        ("MODE A", "Question Bank", "The same prepared questions for every candidate in a role, so results compare fairly."),
        ("MODE B", "Bank + CV Follow-ups", "The standard bank, plus follow-ups that verify claims made in the candidate's CV."),
        ("MODE C", "CV + JD Driven", "Every question generated from the CV and job description, for roles with no bank."),
    ]
    for col, (tag, title, desc) in zip(st.columns(3), modes):
        col.markdown(
            f'<div class="mode-card"><div class="tag">{tag}</div><h3>{title}</h3><p>{desc}</p></div>',
            unsafe_allow_html=True,
        )

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("▶️ Start New Interview", use_container_width=True, key="btn_start", type="primary"):
            st.session_state.page = 'new_interview'
            st.rerun()
    with c2:
        if st.button("📈 Usage & Costs", use_container_width=True, key="btn_usage"):
            st.session_state.page = 'usage_analytics'
            st.rerun()

    show_resume_section()

    st.write("")
    st.subheader("What HireMind does")
    features = [
        "Text, voice and video answers",
        "Adaptive follow-up questions (up to 3)",
        "4-dimension scoring on a 1-5 scale, with evidence quotes",
        "AI hiring recommendation with human review and override",
        "PDF and Markdown reports",
        "Prompt-injection detection",
        "Per-interview token and cost tracking",
        "Fresher and senior role question banks",
    ]
    left, right = st.columns(2)
    for i, f in enumerate(features):
        (left if i % 2 == 0 else right).markdown(f'<div class="feat">{f}</div>', unsafe_allow_html=True)

def show_new_interview():
    """New Interview - Create interview with consent."""
    st.title("Start New Interview")

    if st.button("← Back to Home", key="btn_back_new"):
        st.session_state.page = 'home'
        st.rerun()

    st.markdown("---")

    db = DBManager()
    jobs = db.list_jobs()
    
    if not jobs:
        st.error("❌ No jobs available! Run 'python setup.py'")
        st.stop()
    
    st.success(f"✓ {len(jobs)} jobs available")
    
    mode = st.selectbox(
        "Interview Mode *",
        ["A", "B", "C"],
        format_func=lambda x: {"A": "Mode A - Question bank only", "B": "Mode B - Question bank + CV follow-ups",
                               "C": "Mode C - CV + job description driven"}[x],
        key="new_interview_mode",
    )
    cv_required = mode in ("B", "C")

    with st.form("interview_form"):
        col1, col2 = st.columns(2)
        with col1:
            job_idx = st.selectbox(
                "Job Position *",
                range(len(jobs)),
                format_func=lambda i: jobs[i]['title'],
            )
            job_id = jobs[job_idx]['id']

            candidate_name = st.text_input("Candidate Name *")

        with col2:
            candidate_email = st.text_input("Candidate Email *")
            candidate_phone = st.text_input("Candidate Phone")

        cv_file = st.file_uploader(
            "Upload CV / Resume * (required)" if cv_required else "Upload CV / Resume (optional)",
            type=['pdf', 'docx'],
        )
        
        st.subheader("Consent & Data Handling")
        st.info("""
        **Data storage:** Transcripts, scores and reviews are stored locally in a SQLite database (data/interviews.db), not encrypted.  
        **Retention:** 90 days for transcripts, 7 days for videos; expired data is deleted automatically.  
        **Processing:** Your CV text, answers and any audio/video recording are sent to OpenAI to transcribe, score and generate questions.  
        **Audit trail:** Every AI call and every interviewer decision is logged with a timestamp.
        """)
        
        consent_given = st.checkbox(
            "I consent to data handling as described and agree this interview will be recorded and evaluated"
        )
        
        submitted = st.form_submit_button("▶️ Start Interview", use_container_width=True)
        
        if submitted:
            if not candidate_name or not candidate_email:
                st.error("❌ Name and email required")
                st.stop()
            
            if not consent_given:
                st.error("❌ Consent required to proceed")
                st.stop()

            if cv_required and not cv_file:
                st.error(f"❌ A CV / resume is required for Mode {mode}")
                st.stop()
            
            try:
                with st.spinner("Creating interview..."):
                    # Create candidate
                    cv_path = None
                    if cv_file:
                        cv_dir = Path("data/cvs")
                        cv_dir.mkdir(parents=True, exist_ok=True)
                        cv_path = str(cv_dir / f"{candidate_email}_{cv_file.name}")
                        with open(cv_path, 'wb') as f:
                            f.write(cv_file.getbuffer())
                        if cv_required and not read_cv(cv_path):
                            os.remove(cv_path)
                            st.error("❌ Could not read any text from this CV. Upload a text-based PDF or DOCX (not a scanned image).")
                            st.stop()
                    
                    candidate_id = db.create_candidate(
                        name=candidate_name,
                        email=candidate_email,
                        phone=candidate_phone if candidate_phone else None,
                        cv_path=cv_path,
                    )
                    
                    # Create interview
                    interview_id = db.create_interview(
                        candidate_id=candidate_id,
                        job_id=job_id,
                        mode=mode,
                    )
                    
                    # Save consent
                    db.save_consent(interview_id, candidate_id, True)

                    # Flag prompt-injection attempts hidden in the CV
                    if cv_path:
                        from utils.injection_detector import InjectionDetector
                        db.add_injection_flags(
                            interview_id, InjectionDetector().scan(read_cv(cv_path, max_chars=50000), "CV"))
                
                st.success("✅ Interview created! Starting Q&A...")
                st.session_state.interview_id = interview_id
                st.session_state.current_candidate_id = candidate_id
                st.session_state.page = 'interview_flow'
                st.session_state.question_index = 0
                st.session_state.generated_questions = None  # Reset generated questions
                st.session_state.followup_state = None
                st.session_state.followup_q_used = 0
                st.session_state.role_context = None  # Reset role context
                st.rerun()
            
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

MAX_FOLLOWUPS = 2            # follow-ups per question
MAX_FOLLOWUP_QUESTIONS = 2   # questions per interview that may get follow-ups


def next_followup(mode, question, history, interview, job_description):
    """Return the next single follow-up text, or None if the answer doesn't warrant one."""
    last_answer = history[-1]['a']
    if is_non_answer(last_answer):
        return None  # "I don't know" - nothing to probe; move on (does not use up the follow-up allowance)
    try:
        if mode in ("B", "C"):
            cv_text = read_cv((interview.get('candidate') or {}).get('cv_path'))
            text, _ = QuestionGeneratorAgent(mode=mode).next_followup(
                history, cv=cv_text, job_description=job_description or "", max_followups=MAX_FOLLOWUPS)
            return text
        # Mode A: free template follow-up, only for a short answer and only once
        if len(history) > 1 or len(last_answer.split()) >= 25:
            return None
        items = FollowUpGenerator().generate_followups(
            question_id="", candidate_answer=last_answer,
            skill_area=question['skill_area'], num_followups=1)
        return items[0]['question_text'] if items else None
    except Exception as err:
        st.warning(f"Skipping follow-up: {err}")
        return None


def collect_answer(key, response_type):
    """Render the input for the chosen channel. Returns {'type','text','video_path'} once an answer is ready, else None."""
    if response_type == "Text":
        text = st.text_area("Your Answer", height=150, key=f"text_{key}")
        if st.button("✅ Submit Answer", use_container_width=True, key=f"submit_text_{key}"):
            if not text.strip():
                st.error("❌ Please provide an answer")
                return None
            return {'type': 'Text', 'text': text, 'video_path': None}
        return None

    if response_type == "Voice":
        audio = st.audio_input("Record your voice answer", key=f"voice_{key}")
        if audio and st.button("✅ Transcribe & Submit", use_container_width=True, key=f"submit_voice_{key}"):
            try:
                with st.spinner("🔄 Transcribing..."):
                    from services.speech_service import SpeechService
                    text = SpeechService().transcribe_audio(audio)
            except Exception as err:
                st.error(f"❌ {err}")
                return None
            return {'type': 'Voice', 'text': text, 'video_path': None}
        return None

    # Video
    import base64
    import hashlib
    from services.video_recorder import video_recorder
    from services.video_processor import VideoProcessor

    attempt = st.session_state.get(f"video_attempt_{key}", 0)
    rec_key = f"{key}_{attempt}"
    st.info("📹 **Video answer** - enable your camera and microphone, record, then press *Stop & submit*. "
            "Your face must be visible and well lit. Only what you say is assessed.")
    result = video_recorder(key=f"video_{rec_key}")
    if result is None:
        return None

    def record_again(reason_lines):
        st.error("❌ **Video is not enabled or not clear - this answer cannot be accepted.**\n\n"
                 + "\n".join(f"- {r}" for r in reason_lines))
        if st.button("🔄 Record again", use_container_width=True, key=f"video_retry_{rec_key}"):
            st.session_state[f"video_attempt_{key}"] = attempt + 1
            st.rerun()
        return None

    quality = VideoProcessor().check_quality(result)
    if not quality['clear']:
        return record_again(quality['issues'])

    err_key = f"video_err_{rec_key}"
    if st.session_state.get(err_key):
        return record_again([st.session_state[err_key]])

    try:
        data = base64.b64decode(result['data'])
        ext = "mp4" if "mp4" in (result.get('mime') or "") else "webm"
        with st.spinner("🔄 Extracting audio and transcribing..."):
            from services.speech_service import SpeechService
            text = SpeechService().transcribe_from_video(data, f"answer.{ext}")
        video_dir = Path("data/videos")
        video_dir.mkdir(parents=True, exist_ok=True)
        video_path = str(video_dir / f"{hashlib.sha1(data).hexdigest()}.{ext}")
        with open(video_path, 'wb') as f:
            f.write(data)
    except Exception as err:
        st.session_state[err_key] = str(err)
        return record_again([str(err)])
    return {'type': 'Video', 'text': text, 'video_path': video_path}


def save_answer_and_advance(db, interview, interview_id, mode, q_idx, question, answer, job_description):
    """Save the main answer, then either start a follow-up or move to the next question."""
    question_id = db.create_question(
        interview_id=interview_id,
        question_text=question['question_text'],
        skill_area=question['skill_area'],
        difficulty=question['difficulty'],
        source='CV-Derived' if mode == 'C' else 'QuestionBank',
        question_order=q_idx,
    )
    db.save_answer(question_id=question_id, response_type=answer['type'], transcript=answer['text'],
                   candidate_response=answer['text'], video_path=answer['video_path'])

    history = [{'q': question['question_text'], 'a': answer['text']}]
    nxt = None
    if st.session_state.get('followup_q_used', 0) < MAX_FOLLOWUP_QUESTIONS:
        nxt = next_followup(mode, question, history, interview, job_description)
    if nxt:
        st.session_state.followup_q_used = st.session_state.get('followup_q_used', 0) + 1
        st.session_state.followup_state = {
            'q_idx': q_idx, 'history': history, 'current': nxt, 'rtype': answer['type'],
            'skill_area': question['skill_area'], 'difficulty': question['difficulty'],
        }
    else:
        st.session_state.question_index += 1
    st.rerun()


def show_interview_flow():
    """Interview Flow - Ask questions and collect answers (Text, Voice, Video)."""
    st.title("Interview in Progress")

    interview_id = st.session_state.interview_id
    if not interview_id:
        st.error("No interview selected")
        st.stop()

    db = DBManager()
    interview = db.get_interview(interview_id)

    if not interview:
        st.error("Interview not found")
        st.stop()

    # Header
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Candidate", interview['candidate']['name'])
    with col2:
        st.metric("Position", interview['job']['title'])
    with col3:
        st.metric("Mode", interview['mode'])

    st.markdown("---")

    # Generate questions based on interview mode
    job_title = interview['job']['title']
    job_description = interview['job'].get('description', '')
    job_id = interview['job']['id']
    mode = interview['mode']

    if 'generated_questions' not in st.session_state or not st.session_state.generated_questions:
        with st.spinner(f"📋 Loading interview questions for Mode {mode}..."):
            try:
                from services.question_selector import QuestionSelector

                # A resumed interview reuses the exact question list it started with
                questions = db.get_planned_questions(interview_id)
                resumed = bool(questions)

                if not questions:
                    # Determine role level (Fresher vs Senior)
                    role_level = "Easy" if "fresher" in job_title.lower() or "junior" in job_title.lower() else "Medium"

                    # Get candidate CV
                    cv_text = read_cv((interview.get('candidate') or {}).get('cv_path'))

                    # Select questions based on mode
                    questions = QuestionSelector.select_questions(
                        mode=mode,
                        job_description=job_description or "",
                        candidate_cv=cv_text,
                        role_level=role_level,
                        job_title=job_title
                    )

                if questions:
                    st.session_state.generated_questions = questions[:10]
                    if not resumed:
                        db.save_planned_questions(interview_id, st.session_state.generated_questions)
                    if resumed:
                        st.success("✅ Restored this interview's questions")
                    elif mode == "C":
                        st.success(f"✅ Generated questions from CV+JD (Mode C)")
                    else:
                        st.success(f"✅ Loaded questions from database (Mode {mode})")
                else:
                    st.session_state.generated_questions = []

            except Exception as e:
                st.error(f"❌ Error loading questions: {str(e)}")
                st.session_state.generated_questions = []

    question_bank = st.session_state.generated_questions

    if not question_bank or len(question_bank) == 0:
        st.error(f"❌ No question bank for '{job_title}' (Mode {mode}). Use Mode C for roles without a prepared bank.")
        st.stop()

    q_idx = st.session_state.question_index

    if q_idx >= len(question_bank):
        st.success("✅ All questions answered! Proceeding to scoring...")
        db.update_interview_status(interview_id, 'completed')
        st.session_state.page = 'results'
        st.rerun()

    question = question_bank[q_idx]

    # Progress
    st.subheader(f"Question {q_idx + 1} of {len(question_bank)}")
    st.progress((q_idx + 1) / len(question_bank))

    st.write(f"**Skill:** {question['skill_area']} | **Level:** {question['difficulty']}")

    st.markdown("---")
    st.write(f"## {question['question_text']}")

    st.markdown("---")

    # One follow-up at a time for the question just answered
    fstate = st.session_state.get('followup_state')
    if fstate and fstate['q_idx'] == q_idx:
        n = len(fstate['history'])
        st.subheader(f"🎯 Follow-up {n} of up to {MAX_FOLLOWUPS}")
        st.write(f"**{fstate['current']}**")
        fu = collect_answer(f"fu_{q_idx}_{n}", fstate.get('rtype', 'Text'))
        if st.button("⏭️ Skip to next question", use_container_width=True, key=f"fu_skip_{q_idx}_{n}"):
            st.session_state.followup_state = None
            st.session_state.question_index += 1
            st.rerun()
        if fu:
            fu_qid = db.create_question(
                interview_id=interview_id, question_text=fstate['current'],
                skill_area=fstate['skill_area'], difficulty=fstate['difficulty'],
                source='CV-Derived' if mode in ('B', 'C') else 'QuestionBank', question_order=q_idx,
            )
            db.save_answer(question_id=fu_qid, response_type=fu['type'], transcript=fu['text'],
                           candidate_response=fu['text'], video_path=fu['video_path'])
            history = fstate['history'] + [{'q': fstate['current'], 'a': fu['text']}]
            nxt = next_followup(mode, {'skill_area': fstate['skill_area']}, history, interview, job_description) \
                if len(history) - 1 < MAX_FOLLOWUPS else None
            if nxt:
                fstate.update(history=history, current=nxt)
            else:
                st.session_state.followup_state = None
                st.session_state.question_index += 1
            st.rerun()
        st.stop()

    # Response channel
    response_type = st.radio("Response Type", ["Text", "Voice", "Video"], horizontal=True, key=f"type_{q_idx}")
    answer = collect_answer(f"q{q_idx}", response_type)
    if answer:
        try:
            save_answer_and_advance(db, interview, interview_id, mode, q_idx, question, answer, job_description)
        except Exception as err:
            if type(err).__name__ in ("RerunException", "StopException"):
                raise
            st.error(f"Error: {err}")


def show_results():
    """Results - Scoring, Recommendation, Human Review."""
    st.title("Interview Results & Scoring")
    
    interview_id = st.session_state.interview_id
    if not interview_id:
        st.error("No interview selected")
        st.stop()
    
    db = DBManager()
    interview = db.get_interview(interview_id)
    
    if not interview:
        st.error("Interview not found")
        st.stop()
    
    st.subheader(f"📊 Interview Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Candidate", interview['candidate']['name'])
    with col2:
        st.metric("Position", interview['job']['title'])
    with col3:
        st.metric("Questions", len(interview['questions']))
    
    st.markdown("---")
    
    injection_flags = db.get_injection_flags(interview_id)
    if injection_flags:
        st.error(
            f"🚨 **{len(injection_flags)} possible prompt-injection attempt(s) detected.** "
            "The injected text was removed before scoring and will be flagged in the report."
        )
        with st.expander("View flagged text"):
            for f in injection_flags:
                st.write(f"- **{f['type']}** in *{f['source']}*: `{f['excerpt']}`")

    # Full transcript for the human reviewer
    with st.expander("📝 Full transcript", expanded=False):
        last_order = None
        for q in interview['questions']:
            a = db.get_answer_by_question(q['id']) or {}
            is_followup = q['question_order'] == last_order
            last_order = q['question_order']
            label = "↳ Follow-up" if is_followup else f"Q{q['question_order'] + 1}"
            st.markdown(f"**{label}:** {q['base_question']}")
            st.write(f"*({a.get('response_type') or 'Text'} answer)* {a.get('transcript') or 'No answer recorded'}")
            vp = a.get('video_path')
            if vp and os.path.exists(vp):
                st.video(vp)
            st.markdown("---")

    # ---------------- Scoring ----------------
    st.subheader("📈 Scoring (1-5 Scale)")
    score_err_key = f"score_err_{interview_id}"

    if not interview['scores']:
        if st.session_state.get(score_err_key):
            st.error(f"Scoring failed: {st.session_state[score_err_key]}")
            if st.button("🔄 Retry scoring", key="retry_scoring"):
                st.session_state[score_err_key] = None
                st.rerun()
            st.stop()

        qa, last_order = [], None
        for q in interview['questions']:
            a = db.get_answer_by_question(q['id'])
            if a and (a.get('transcript') or '').strip():
                qa.append({'question_id': q['id'], 'question': q['base_question'], 'answer': a['transcript'],
                           'is_followup': q['question_order'] == last_order})
            last_order = q['question_order']
        if not qa:
            st.warning("No answers were recorded for this interview, so there is nothing to score.")
            st.stop()

        try:
            with st.spinner("🤖 Scoring the interview..."):
                result = ScorerAgent().score_transcript(
                    qa, job_title=interview['job']['title'], job_requirements=interview['job'].get('description') or '')
                for dim, d in result['dimensions'].items():
                    db.save_score(interview_id=interview_id, skill_area=dim, score=d['score'],
                                  justification=d['justification'], evidence_quote=d['evidence_quote'],
                                  question_id=d['evidence_question_id'])
                db.save_feedback(interview_id, {k: result[k] for k in ('strengths', 'gaps', 'next_round_focus')})
        except Exception as e:
            st.session_state[score_err_key] = str(e)
            st.rerun()
        st.rerun()

    scores = db.get_scores(interview_id)
    by_dim = {}
    for sc in scores:
        by_dim.setdefault(sc['skill_area'], []).append(sc)
    scores_by_dim = {d: sum(x['score'] for x in rows) / len(rows) for d, rows in by_dim.items()}

    for col, (dim, avg) in zip(st.columns(max(len(scores_by_dim), 1)), scores_by_dim.items()):
        col.metric(dim, f"{avg:.1f}/5")

    st.subheader("📋 Evidence & Justifications")
    question_text = {q['id']: q['base_question'] for q in interview['questions']}
    for dim, rows in by_dim.items():
        sc = rows[0]
        with st.expander(f"📌 {dim} - {sc['score']}/5", expanded=True):
            st.write(f"**Justification:** {sc['justification']}")
            st.write(f"**Evidence:** \"{sc['evidence_quote']}\"")
            if sc.get('evidence_question_id') in question_text:
                st.caption(f"From the answer to: {question_text[sc['evidence_question_id']]}")

    feedback = db.get_feedback(interview_id)
    if feedback:
        c1, c2, c3 = st.columns(3)
        for col, title, key in ((c1, "💪 Strengths", "strengths"), (c2, "⚠️ Gaps", "gaps"),
                                (c3, "🎯 Focus for next round", "next_round_focus")):
            col.markdown(f"**{title}**")
            for item in feedback.get(key, []):
                col.markdown(f"- {item}")

    st.markdown("---")

    # ---------------- Recommendation ----------------
    st.subheader("🎯 AI Recommendation")
    rec = db.get_recommendation(interview_id)
    if not rec and scores_by_dim:
        try:
            with st.spinner("Generating recommendation..."):
                r = RecommenderAgent().generate_recommendation(
                    scores=scores_by_dim,
                    context={
                        'job_title': interview['job']['title'],
                        'requirements': interview['job']['description'],
                        'cv': read_cv((interview.get('candidate') or {}).get('cv_path'), max_chars=600),
                    }
                )
                db.save_recommendation(
                    interview_id=interview_id,
                    recommendation=r.get('recommendation', 'Hold'),
                    confidence=r.get('confidence', 'Medium'),
                    reason=r.get('reason_summary', 'No summary'),
                    scores=scores_by_dim,
                )
        except Exception as e:
            st.error(f"Recommendation error: {str(e)}")
        else:
            st.rerun()

    if rec:
        c1, c2 = st.columns(2)
        c1.metric("Decision", rec['ai_recommendation'])
        c2.metric("Confidence", rec['confidence'])
        st.write(f"**Reason:** {rec['reason_summary']}")

    st.markdown("---")

    # ---------------- Human review ----------------
    st.subheader("👤 Human Review & Override")
    st.info("**The AI recommendation is advisory only.** You make the final decision.")

    review = interview.get('human_review')
    options = ["Strong Hire", "Hire", "Hold", "No Hire"]
    if review:
        st.success(f"✅ Reviewed by **{review['interviewer_id']}** on {review['override_timestamp']} UTC: "
                   f"**{review['final_recommendation']}** (AI said: {review['original_recommendation']})")
        if review.get('override_reason'):
            st.write(f"**Override reason:** {review['override_reason']}")
        if review.get('notes'):
            st.write(f"**Notes:** {review['notes']}")
    else:
        ai_choice = rec['ai_recommendation'] if rec else None
        with st.form("human_review"):
            interviewer_id = st.text_input("Interviewer ID *")
            final_decision = st.selectbox(
                "Your final decision *", options,
                index=options.index(ai_choice) if ai_choice in options else 0)
            reason = st.text_area("Reason (required if your decision differs from the AI recommendation)", height=100)
            if st.form_submit_button("✅ Submit Review", use_container_width=True):
                is_override = bool(ai_choice) and final_decision != ai_choice
                if not interviewer_id.strip():
                    st.error("❌ Interviewer ID is required")
                elif is_override and not reason.strip():
                    st.error(f"❌ You changed the decision from {ai_choice} to {final_decision}. A reason is required.")
                else:
                    db.save_human_review(
                        interview_id=interview_id,
                        interviewer_id=interviewer_id.strip(),
                        original_rec=ai_choice or 'Not Generated',
                        final_rec=final_decision,
                        override_reason=reason.strip() if is_override else None,
                        notes=reason.strip() if (reason.strip() and not is_override) else None,
                    )
                    st.rerun()

    st.markdown("---")

    # Generate Report
    if st.button("📄 Generate Report (Next Page)", use_container_width=True, key="btn_report"):
        st.session_state.page = 'report'
        st.rerun()

def show_report():
    """Report - Generate PDF & Markdown reports."""
    st.title("Interview Report")
    
    interview_id = st.session_state.interview_id
    if not interview_id:
        st.error("No interview selected")
        st.stop()
    
    if st.button("← Back to Results", key="btn_back_report"):
        st.session_state.page = 'results'
        st.rerun()
    
    st.markdown("---")
    
    db = DBManager()
    interview = db.get_interview(interview_id)
    
    if not interview:
        st.error("Interview not found")
        st.stop()
    
    try:
        with st.spinner("Generating reports..."):
            # Prepare interview data
            scores = db.get_scores(interview_id)
            scores_data = []
            for score in scores:
                scores_data.append({
                    'dimension': score['skill_area'],
                    'score': score['score'],
                    'justification': score['justification'],
                    'evidence_quote': score['evidence_quote'],
                })
            
            transcript_blocks, last_order = [], None
            for q in interview['questions']:
                a = db.get_answer_by_question(q['id']) or {}
                tag = "Follow-up" if q['question_order'] == last_order else f"Q{q['question_order'] + 1}"
                last_order = q['question_order']
                transcript_blocks.append(
                    f"{tag}: {q['base_question']}\nAnswer ({a.get('response_type') or 'Text'}): {a.get('transcript') or 'N/A'}")

            interview_data = {
                'candidate_name': interview['candidate']['name'],
                'job_title': interview['job']['title'],
                'interview_date': interview['start_time'][:10] if interview['start_time'] else '',
                'mode': interview['mode'],
                'scores': scores_data,
                'recommendation': db.get_recommendation(interview_id),
                'injection_flags': db.get_injection_flags(interview_id),
                'feedback': db.get_feedback(interview_id),
                'human_review': interview.get('human_review'),
                'transcript': '\n\n'.join(transcript_blocks),
            }
            
            # Generate reports
            report_gen = ReportGeneratorAgent()
            paths = report_gen.generate_reports(interview_data, pdf=True, md=True)
            
            st.success("✅ Reports generated!")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'pdf' in paths:
                    with open(paths['pdf'], 'rb') as f:
                        st.download_button(
                            "📥 Download PDF Report",
                            f.read(),
                            file_name=f"interview_{interview['candidate']['name']}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
            
            with col2:
                if 'markdown' in paths:
                    with open(paths['markdown'], 'r') as f:
                        markdown_content = f.read()
                        st.download_button(
                            "📥 Download Markdown Report",
                            markdown_content,
                            file_name=f"interview_{interview['candidate']['name']}.md",
                            mime="text/markdown",
                            use_container_width=True,
                        )
            
            st.markdown("---")
            st.subheader("📋 Report Preview")
            st.markdown(markdown_content)
    
    except Exception as e:
        st.error(f"Error generating reports: {str(e)}")
        import traceback
        st.error(traceback.format_exc())

def show_usage_analytics():
    """LLM token usage and cost, by interview, mode and agent."""
    st.title("LLM Usage Analytics & Costs")
    st.caption("Token counts come from the API response, not estimates. Only real AI calls are counted: question-bank selection, template follow-ups and page navigation cost $0.")

    conn = DBManager()._get_connection()
    cur = conn.cursor()

    cur.execute("""SELECT COUNT(*) calls, COALESCE(SUM(input_tokens),0) inp, COALESCE(SUM(output_tokens),0) outp,
                          COALESCE(SUM(cost_usd),0) cost, COALESCE(AVG(latency_ms),0) lat,
                          COALESCE(SUM(status != 'success'),0) errs,
                          COALESCE(SUM(interview_id IS NULL),0) unattributed
                   FROM usage_logs""")
    s = dict(cur.fetchone())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("LLM calls", f"{s['calls']:,}")
    c2.metric("Input / output tokens", f"{s['inp']:,} / {s['outp']:,}")
    c3.metric("Total cost", f"${s['cost']:.4f}")
    c4.metric("Avg latency", f"{s['lat']:.0f} ms")
    if s['unattributed']:
        st.info(f"{s['unattributed']} older call(s) are not linked to an interview (logged before attribution was added or from test scripts).")
    if s['errs']:
        st.warning(f"{s['errs']} call(s) failed.")

    st.subheader("By agent")
    cur.execute("""SELECT agent_name Agent, COUNT(*) Calls, SUM(input_tokens) Input_tokens,
                          SUM(output_tokens) Output_tokens, ROUND(SUM(cost_usd),5) Cost_USD,
                          ROUND(AVG(latency_ms)) Avg_latency_ms, MIN(latency_ms) Min_latency_ms,
                          MAX(latency_ms) Max_latency_ms, SUM(status != 'success') Errors
                   FROM usage_logs GROUP BY agent_name ORDER BY Cost_USD DESC""")
    agent_rows = [dict(r) for r in cur.fetchall()]
    left, right = st.columns([3, 2])
    left.dataframe(agent_rows, use_container_width=True, hide_index=True)
    if agent_rows:
        import pandas as pd
        right.bar_chart(pd.DataFrame(agent_rows).set_index("Agent")[["Cost_USD"]])

    st.subheader("By interview mode")
    cur.execute("""SELECT i.mode Mode, COUNT(DISTINCT i.id) Interviews, COUNT(u.id) Calls,
                          COALESCE(SUM(u.input_tokens),0) Input_tokens, COALESCE(SUM(u.output_tokens),0) Output_tokens,
                          ROUND(COALESCE(SUM(u.cost_usd),0),5) Cost_USD,
                          ROUND(COALESCE(SUM(u.cost_usd),0) * 1.0 / COUNT(DISTINCT i.id),5) Cost_per_interview
                   FROM interviews i LEFT JOIN usage_logs u ON u.interview_id = i.id
                   GROUP BY i.mode ORDER BY i.mode""")
    st.dataframe([dict(r) for r in cur.fetchall()], use_container_width=True, hide_index=True)

    st.subheader("By interview")
    cur.execute("""SELECT c.name Candidate, j.title Role, i.mode Mode, i.status Status,
                          COUNT(u.id) Calls, COALESCE(SUM(u.input_tokens),0) Input_tokens,
                          COALESCE(SUM(u.output_tokens),0) Output_tokens,
                          ROUND(COALESCE(SUM(u.cost_usd),0),5) Cost_USD
                   FROM interviews i
                   JOIN candidates c ON c.id = i.candidate_id
                   JOIN jobs j ON j.id = i.job_id
                   LEFT JOIN usage_logs u ON u.interview_id = i.id
                   GROUP BY i.id ORDER BY i.start_time DESC""")
    st.dataframe([dict(r) for r in cur.fetchall()], use_container_width=True, hide_index=True)

    st.subheader("Recent calls")
    cur.execute("""SELECT substr(timestamp,1,19) Time, agent_name Agent, input_tokens In_tok, output_tokens Out_tok,
                          latency_ms Latency_ms, ROUND(cost_usd,6) Cost_USD, status Status
                   FROM usage_logs ORDER BY timestamp DESC LIMIT 25""")
    st.dataframe([dict(r) for r in cur.fetchall()], use_container_width=True, hide_index=True)
    conn.close()


def main():
    """Main application."""
    
    # Initialize database
    if not Path(DATABASE_PATH).exists():
        with st.spinner("Initializing database..."):
            db = DBManager()
            db.init_db()
            st.success("Database initialized!")
    
    # Enforce data-retention periods once per server process
    if not st.session_state.get('_purged'):
        try:
            from config.settings import TRANSCRIPT_RETENTION_DAYS, VIDEO_RETENTION_DAYS
            DBManager().purge_expired(TRANSCRIPT_RETENTION_DAYS, VIDEO_RETENTION_DAYS)
        except Exception as err:
            print(f"Retention purge failed: {err}")
        st.session_state._purged = True

    # Initialize session state
    init_session_state()
    os.environ["CURRENT_INTERVIEW_ID"] = st.session_state.interview_id or ""
    
    # Sidebar
    with st.sidebar:
        st.title("🧠 HireMind")
        st.caption("AI Interview Agent")
        st.markdown("---")
        
        page_map = {
            "Home": "home",
            "New Interview": "new_interview",
            "Interview Flow": "interview_flow",
            "Results": "results",
            "Report": "report",
            "Usage Analytics": "usage_analytics",
        }
        
        page = st.radio(
            "Navigation",
            list(page_map.keys()),
            index=list(page_map.values()).index(st.session_state.page),
        )
        
        st.session_state.page = page_map[page]
        
        st.markdown("---")
        st.write("**Interview Workflow:**")
        st.write("1. Create new interview")
        st.write("2. Answer questions")
        st.write("3. Review AI scoring")
        st.write("4. Human review & override")
        st.write("5. Generate report")
    
    # Route pages
    if st.session_state.page == "home":
        show_home()
    elif st.session_state.page == "new_interview":
        show_new_interview()
    elif st.session_state.page == "interview_flow":
        show_interview_flow()
    elif st.session_state.page == "results":
        show_results()
    elif st.session_state.page == "report":
        show_report()
    elif st.session_state.page == "usage_analytics":
        show_usage_analytics()

if __name__ == "__main__":
    main()
