# HireMind - AI Interview Agent

HireMind conducts a structured first-round technical interview, scores the candidate on a fixed rubric, and
produces an evidence-backed hiring recommendation. **The AI only advises: the human interviewer confirms or
overrides every recommendation, and the final decision is always theirs.**

## Interview modes

The interviewer picks one mode before each interview.

| Mode | Question source | CV |
|---|---|---|
| **A - Question bank** | The 10 fixed questions prepared for the role. Identical for every candidate, so results compare fairly. No AI is used to pick questions. | Optional |
| **B - Hybrid** | The same fixed bank, plus AI follow-ups that check claims made in the CV. | Required |
| **C - CV-driven** | One AI call writes all 10 questions from the CV and job description (3 Technical, 3 Domain, 2 Problem Solving, 2 Communication), checked for duplicates, up to 2 retries. For roles with no question bank. | Required |

## How an interview runs

1. **New interview** - choose role and mode, enter candidate details, upload the CV (PDF or DOCX), accept the consent notice.
   The CV text is extracted and scanned for hidden instructions.
2. **Questions** - answered by **text, voice or video**.
   - Voice is recorded in the browser and transcribed with OpenAI speech-to-text.
   - Video is recorded in the browser (camera + microphone). If the camera is not enabled, or the picture is too dark,
     blurry, or shows no face, the app says so clearly and **does not accept the answer** until the video is clear.
3. **Adaptive follow-ups** - after an answer the AI decides whether a follow-up is truly needed (vague, incomplete, wrong, or
   contradicting the CV). One follow-up at a time, built on the previous reply. At most 2 per question, and at most 2 questions per
   interview get follow-ups. The interviewer can skip any follow-up. (Both limits are constants at the top of the interview section in `app.py`.)
4. **Results** - four dimensions scored 1-5, each with a written justification and a quote from the transcript:
   Technical Skills, Domain Understanding, Problem Solving, Communication Clarity. Quotes are verified against the real answers;
   an unverifiable quote is replaced by the closest real sentence. Also produced: strengths, gaps, and focus areas for the next round.
5. **Recommendation** - Strong Hire / Hire / Hold / No Hire, with confidence (High / Medium / Low) and a short reason.
6. **Human review** - the interviewer sees the full transcript (and video), scores, evidence and recommendation, then accepts or overrides.
   A **reason is mandatory when overriding**. Each review is stored with interviewer ID and timestamp (UTC).
7. **Report** - exportable as **PDF or Markdown**: per-dimension scores and evidence, strengths, gaps, next-round focus,
   the human decision, security flags, and the transcript.
8. **Usage Analytics** - tokens, cost and latency by agent, mode and interview.

**Resuming after a disconnect.** Every answer is saved as soon as it is submitted, and the interview's 10 questions are saved when it starts.
If the candidate loses connection or refreshes, the Home page lists unfinished interviews under *Resume an unfinished interview*.
Resuming restores the same questions and continues at the first unanswered question. A follow-up that was still open when the connection
dropped is not restored; the interview moves on to the next question. Starting again with the same email reuses the existing candidate record.
Mode C interviews started before this feature have no saved question list, so their questions are regenerated on resume.

## Security: prompt injection

CVs and answers are untrusted. Defences, all active in the normal flow:
- A phrase-level detector (`utils/injection_detector.py`) scans every CV and every saved answer (text, voice transcript, video transcript, follow-up).
  It is tuned to avoid flagging normal technical talk such as "method override" or "bypass the cache".
- Detected phrases are **removed before any text reaches the AI**, and all candidate text is fenced in tags that the prompts declare to be data, never instructions.
- Every attempt is **flagged**: a warning on the results screen and a "Security Flags" section in the PDF and Markdown report.

## Consent and data handling

A consent notice is shown before every interview. It states that data is stored locally and unencrypted, the retention periods, that CV text, answers and recordings are sent to OpenAI for processing, and that AI calls and interviewer decisions are logged. Data is stored locally:

| Data | Location | Kept for |
|---|---|---|
| Transcripts, scores, reviews, usage logs | SQLite database `data/interviews.db` | 90 days (`TRANSCRIPT_RETENTION_DAYS`) |
| Video recordings | `data/videos/` | 7 days (`VIDEO_RETENTION_DAYS`) |
| Uploaded CVs | `data/cvs/` | Until deleted by the operator |
| Reports | `data/reports/` | Until deleted by the operator |

Retention is **enforced**: when the app starts it deletes expired video files and replaces expired transcripts with
"[removed after retention period]". Both periods are configurable in `.env`. Audio and video are sent to OpenAI only for transcription.

## What the design deliberately does not judge

HireMind scores only the **content of what the candidate says**: the transcript text, measured against the rubric and the job requirements.
It does no facial-expression, emotion, or body-language analysis. The only thing computed from the video picture is a technical usability
check (is the camera on, and is the image bright, sharp and does it contain a face), which decides whether the recording can be
transcribed and reviewed, not how the candidate is judged. The scorer is not given the candidate's name, gender, age or CV
(the recommender sees a short CV excerpt for role fit only), and its prompt tells it to ignore accent, speaking style and other
non-job-related signals. The bias evaluation below tests this.

## Usage logging

Every AI call (chat and transcription) is logged to `usage_logs` with timestamp, user ID, agent name, model, input tokens,
output tokens, latency (ms), status (success or error) and estimated cost. **Token counts come from the usage fields in the API
response, not from estimates.** Failed calls are logged with status `error`. Cost is computed from the per-token prices in
`config/settings.py`; the transcription prices there are approximate, so check them against current OpenAI pricing.

## Tech stack

Python, Streamlit (UI and a small custom browser component for video), SQLite, OpenAI `gpt-4o-mini` (scoring, recommendation,
question and follow-up generation) and `gpt-4o-mini-transcribe` (speech to text), python-docx and pypdf (CV parsing), ReportLab (PDF reports).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env            # then set OPENAI_API_KEY
python setup.py                 # creates the database, 10 jobs, 100 questions, and the sample input files
streamlit run app.py
```

Use one Python install consistently. If you have several, run `python -m pip install -r requirements.txt` with the same
interpreter that runs Streamlit. After changing any file other than `app.py`, restart Streamlit.

## Sample inputs

| Input | Location |
|---|---|
| Job descriptions (10 roles, Markdown) | `data/job_descriptions/` |
| Question bank (100 questions, tagged by role, skill area and difficulty) | `data/question_bank/question_bank.json` and `.csv` |
| Synthetic CVs (10: 7 DOCX, 3 PDF) | `data/sample_cvs/` |

`python build_sample_inputs.py` regenerates them. The question bank lives in `data/role_questions.py`.

## Evaluation

```bash
python tests/evaluation/run_evaluations.py          # live, roughly 80 small API calls (about $0.10)
python tests/evaluation/run_evaluations.py --mock   # offline plumbing check only (fake model, meaningless scores)
```

Writes `tests/evaluation/results/evaluation_results.json` and `EVALUATION_REPORT.md`:
1. **Scoring consistency** - the evaluator is run 5 times on the same 3 transcripts; variance is reported per dimension.
2. **Bias check** - identical answers with the name, gender and pronouns changed (4 variants); score differences reported.
3. **Injection resistance** - detector coverage and false positives, plus a full pipeline run on an interview containing injected instructions in the CV and answers, compared with the clean interview (with and without sanitization).
4. **Human agreement** - the agent's scores and recommendation against reference judgements for 5 sample interviews (`tests/evaluation/eval_data.py`). **Review and adjust those reference labels to your own judgement before reporting results**, and explain any disagreements in the report.

Results are produced by running the command above; none are bundled in this repository.

## Project layout

```
app.py                  Streamlit app: all screens and the interview flow
agents/                 question_generator, scorer, recommender, report_generator, followup_generator (template, no AI)
services/               openai_service (all AI calls + logging), cv_parser, question_selector, speech_service,
                        video_processor, video_recorder (browser component wrapper)
components/video_recorder/   browser camera/microphone recorder
database/               schema.sql, db_manager (all reads and writes), usage_logger
utils/injection_detector.py
config/settings.py      environment, rubric, prices, retention, temperatures
data/                   role question bank, job descriptions, sample CVs, reports (generated)
tests/                  unit tests (python -m pytest tests -q) and the evaluation runner
```

## Known limitations

- The video clarity limits (brightness, sharpness) were tested with a simulated camera, not a range of real webcams. They are configurable (`MIN_BRIGHTNESS`, `MIN_SHARPNESS`).
- Face presence is only checked in browsers that support the FaceDetector API; elsewhere the face check is skipped.
- Mode A follow-ups are simple templates, so they are less specific than the AI follow-ups in Modes B and C.
- A single local SQLite database and a single interviewer session at a time; not designed for concurrent multi-user deployment.
