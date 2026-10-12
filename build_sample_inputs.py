"""Generate the sample inputs: job description files, question bank (JSON + CSV) and the 3 PDF sample CVs.

Run once after setup:  python build_sample_inputs.py
Also syncs the job descriptions in the database with the JD files.
"""
import csv
import json
import shutil
import sqlite3
import uuid
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from config.settings import DATABASE_PATH, DATA_DIR
from data.role_questions import ROLE_QUESTIONS

JD_DIR = DATA_DIR / "job_descriptions"
QB_DIR = DATA_DIR / "question_bank"
CV_DIR = DATA_DIR / "sample_cvs"

# title: (level, summary, responsibilities, requirements, nice_to_have)
JOBS = {
    "Java Developer (Fresher)": ("Fresher", "Join the backend team as a junior Java developer building and maintaining REST services under mentorship.",
        ["Implement features in Java and Spring Boot services", "Write SQL queries and JDBC/Hibernate data access code", "Write unit tests and fix defects found in code review", "Follow team coding standards and use Git daily"],
        ["B.Tech/BE in Computer Science or related field", "Strong Java fundamentals: OOP, collections, exceptions", "Basic SQL and relational databases", "Understanding of data structures and algorithms"],
        ["Spring Boot or Hibernate project experience", "Familiarity with Maven and JUnit"]),
    "Frontend Developer (Fresher)": ("Fresher", "Build responsive, accessible user interfaces with React as part of the web product team.",
        ["Build UI components in React and JavaScript", "Turn designs into responsive layouts with HTML and CSS", "Consume REST APIs and handle loading and error states", "Debug browser issues using DevTools"],
        ["Solid JavaScript (ES6+), HTML5, CSS3", "Working knowledge of React: props, state, hooks", "Understanding of responsive design and accessibility basics", "Version control with Git"],
        ["TypeScript exposure", "Experience with a component library or testing with Jest"]),
    "Data Analyst (Fresher)": ("Fresher", "Support business teams by cleaning data, running analyses and building dashboards.",
        ["Query and join data using SQL", "Clean and analyse datasets with Python (Pandas) or Excel", "Build dashboards and charts that communicate trends", "Present findings to non-technical stakeholders"],
        ["Strong SQL: joins, aggregations, subqueries", "Python with Pandas or equivalent", "Basic statistics: distributions, correlation, hypothesis testing", "Clear written and verbal communication"],
        ["Tableau or Power BI project", "Exposure to A/B testing"]),
    "QA Engineer (Fresher)": ("Fresher", "Ensure release quality through manual and automated testing of web applications.",
        ["Design and execute test cases from requirements", "Report defects with clear steps to reproduce", "Automate regression tests with Selenium", "Take part in release testing and triage"],
        ["Understanding of the testing life cycle and test design techniques", "Knowledge of defect life cycle, severity and priority", "Basic Selenium or similar automation", "Attention to detail and clear communication"],
        ["API testing with Postman", "Basic SQL for data validation"]),
    "Agentic AI Developer (Fresher)": ("Fresher", "Build LLM-powered agents and retrieval pipelines that use tools to complete tasks reliably.",
        ["Build prompts and tool-calling flows with LLM APIs", "Implement retrieval-augmented generation (RAG) pipelines", "Evaluate agent behaviour and reduce hallucinations", "Log and monitor token usage and cost"],
        ["Python programming", "Understanding of LLMs, prompting and structured outputs", "Awareness of embeddings and vector search", "Interest in AI safety, including prompt injection"],
        ["A personal agent or RAG project", "Familiarity with LangChain or similar frameworks"]),
    "Senior Backend Engineer": ("Senior", "Own the design and scaling of high-traffic backend services and mentor the team.",
        ["Design, version and secure REST/gRPC APIs", "Optimise database queries, indexing and caching", "Lead reliability work: observability, alerting, incident response", "Mentor engineers and review designs and code"],
        ["5+ years building production backend systems", "Deep knowledge of SQL and NoSQL data stores", "Experience with microservices, messaging and distributed consistency", "Strong debugging of latency and scaling problems"],
        ["Experience with Kafka or RabbitMQ", "Cloud experience on AWS, GCP or Azure"]),
    "Senior Full Stack Engineer": ("Senior", "Deliver end-to-end features across a React front end and Node/Python back end.",
        ["Architect front-end state management and data fetching", "Design API contracts between front end and back end", "Improve performance, accessibility and Core Web Vitals", "Collaborate with design and product on scope and trade-offs"],
        ["5+ years of full stack development", "Expert React and TypeScript; Node.js or Python on the server", "Relational database design and migrations", "Authentication, authorization and web security (XSS, CSRF)"],
        ["Server-side rendering experience", "CI/CD and cloud deployment experience"]),
    "AI/ML Engineer (Senior)": ("Senior", "Take machine-learning and LLM systems from notebook to reliable production services.",
        ["Build and deploy ML and LLM pipelines to production", "Evaluate models and monitor drift, quality and cost", "Choose between fine-tuning, RAG and prompt engineering", "Partner with product on realistic expectations and limits"],
        ["5+ years in applied ML", "Strong Python with PyTorch or TensorFlow", "Experience with MLOps: versioning, CI/CD, monitoring", "Experience evaluating LLM-based systems"],
        ["Experience with vector databases", "Cost and latency optimisation for inference"]),
    "Tech Lead / Architect": ("Senior", "Set technical direction for several teams and drive large-scale system design.",
        ["Design systems for high availability and scale", "Define architecture standards and review major designs", "Plan migrations (for example monolith to services) with no downtime", "Coach engineers and communicate trade-offs to executives"],
        ["8+ years in software engineering, 2+ in a lead or architect role", "Deep experience with distributed systems and data architecture", "Strong observability and reliability practices", "Proven ability to align stakeholders"],
        ["Experience managing technical debt across teams", "Cloud cost management"]),
    "DevOps Engineer (Senior)": ("Senior", "Build and run the delivery platform: CI/CD, Kubernetes and infrastructure as code.",
        ["Design CI/CD pipelines for containerised services", "Operate Kubernetes clusters, scaling and self-healing workloads", "Manage infrastructure as code with Terraform", "Define SLOs, alerting and incident reviews"],
        ["5+ years in DevOps or SRE", "Strong Kubernetes and Docker experience", "Terraform or equivalent IaC", "Security practices: secrets management, least privilege"],
        ["GitOps tooling such as ArgoCD", "FinOps / cloud cost optimisation"]),
}

# name, filename role label, title, summary, skills, experience bullets, education
PDF_CVS = [
    ("Ritu Verma", "Senior Full Stack Engineer", "ritu.verma@email.com", "+91-9876543221",
     "Full stack engineer with 7 years of experience shipping React and Node.js products at scale.",
     ["React, TypeScript, Redux, Next.js", "Node.js, Express, GraphQL, REST", "PostgreSQL, Redis, MongoDB", "AWS (ECS, S3, CloudFront), Docker, GitHub Actions"],
     ["Lead Full Stack Engineer, ShopLoop (2022-present): led a team of 4; migrated the REST API to GraphQL and cut average page load time by 40%.",
      "Senior Engineer, FinEdge (2019-2022): built a payments dashboard used by 20,000 merchants; introduced server-side rendering that raised Lighthouse performance from 54 to 91.",
      "Software Engineer, Webcraft (2017-2019): developed internal tools in React and Node.js."],
     "B.E. Computer Science, 2017"),
    ("Karan Mehta", "AI ML Engineer", "karan.mehta@email.com", "+91-9876543222",
     "Applied ML engineer with 6 years of experience in NLP, recommender systems and production LLM applications.",
     ["Python, PyTorch, scikit-learn, Hugging Face", "MLOps: MLflow, Docker, Kubernetes, SageMaker", "LLMs: RAG pipelines, fine-tuning, evaluation harnesses", "SQL, Spark, Airflow"],
     ["Senior ML Engineer, Insightly (2021-present): built a RAG assistant for support teams that deflects 30% of tickets; reduced inference cost by 35% through caching and model routing.",
      "ML Engineer, RetailAI (2018-2021): improved the F1 score of a product-classification model from 0.71 to 0.84 and deployed it with drift monitoring.",
      "Data Scientist, Analytica (2017-2018): churn and demand forecasting models."],
     "M.Tech Data Science, 2017"),
    ("Meera Iyer", "DevOps Engineer", "meera.iyer@email.com", "+91-9876543223",
     "DevOps and SRE engineer with 8 years of experience running Kubernetes platforms and automated delivery pipelines.",
     ["Kubernetes, Helm, ArgoCD, Docker", "Terraform, AWS (EKS, VPC, IAM), Ansible", "Prometheus, Grafana, Loki, PagerDuty", "Jenkins, GitHub Actions, Python, Bash"],
     ["Staff DevOps Engineer, CloudNest (2021-present): rebuilt CI/CD on GitHub Actions and ArgoCD, cutting deploy time from 45 to 8 minutes; maintained 99.95% uptime for 60 services.",
      "DevOps Engineer, Paysure (2018-2021): moved 25 services to EKS with Terraform and reduced monthly cloud spend by 28%.",
      "Systems Engineer, NetOps (2016-2018): Linux administration and monitoring."],
     "B.Tech Information Technology, 2016"),
]


def write_jds():
    JD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    for title, (level, summary, resp, req, nice) in JOBS.items():
        md = (f"# {title}\n\n**Level:** {level}\n\n## About the role\n{summary}\n\n## Responsibilities\n"
              + "".join(f"- {r}\n" for r in resp) + "\n## Requirements\n" + "".join(f"- {r}\n" for r in req)
              + "\n## Nice to have\n" + "".join(f"- {r}\n" for r in nice))
        fname = JD_DIR / (title.replace(" / ", "-").replace("/", "-").replace(" ", "_").replace("(", "").replace(")", "") + ".md")
        fname.write_text(md, encoding="utf-8")
        description = f"{summary}\nResponsibilities: " + "; ".join(resp) + ".\nRequirements: " + "; ".join(req) + "."
        cur = conn.execute("UPDATE jobs SET description = ?, required_skills = ? WHERE title = ?", (description, "; ".join(req), title))
        if cur.rowcount == 0:
            conn.execute("INSERT INTO jobs (id, title, description, required_skills) VALUES (?, ?, ?, ?)",
                         (str(uuid.uuid4()), title, description, "; ".join(req)))
    conn.commit()
    conn.close()
    print(f"{len(JOBS)} job description files written to {JD_DIR} and synced to the database")


def write_question_bank():
    QB_DIR.mkdir(parents=True, exist_ok=True)
    rows = [{"role": role, "skill_area": skill, "difficulty": difficulty, "question": text}
            for role, (difficulty, items) in ROLE_QUESTIONS.items() for skill, text in items]
    (QB_DIR / "question_bank.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(QB_DIR / "question_bank.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["role", "skill_area", "difficulty", "question"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} questions written to question_bank.json and question_bank.csv")


def write_cvs():
    CV_DIR.mkdir(parents=True, exist_ok=True)
    src = Path.home() / "Downloads" / "AI_Interview_Agent_CVs"
    if src.exists():
        for f in src.glob("*.docx"):
            shutil.copy(f, CV_DIR / f.name)
    styles = getSampleStyleSheet()
    for name, role, email, phone, summary, skills, exp, edu in PDF_CVS:
        story = [Paragraph(name.upper(), styles["Title"]),
                 Paragraph(f"{role} | {email} | {phone}", styles["Normal"]), Spacer(1, 10),
                 Paragraph("SUMMARY", styles["Heading3"]), Paragraph(summary, styles["Normal"]),
                 Paragraph("SKILLS", styles["Heading3"])]
        story += [Paragraph("&bull; " + s, styles["Normal"]) for s in skills]
        story.append(Paragraph("EXPERIENCE", styles["Heading3"]))
        story += [Paragraph("&bull; " + e, styles["Normal"]) for e in exp]
        story += [Paragraph("EDUCATION", styles["Heading3"]), Paragraph(edu, styles["Normal"])]
        SimpleDocTemplate(str(CV_DIR / f"{name} - {role}.pdf"), pagesize=letter).build(story)
    print("sample CVs in", CV_DIR, ":", len(list(CV_DIR.glob('*.*'))), "files")


if __name__ == "__main__":
    write_jds()
    write_question_bank()
    write_cvs()
