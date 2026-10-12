from datetime import datetime
from typing import Dict, List
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config.settings import DATA_DIR


def _safe_name(data: Dict) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in data.get("candidate_name", "Candidate"))


def _bullets(items: List[str]) -> List[str]:
    return [str(i).strip() for i in (items or []) if str(i).strip()]


class ReportGeneratorAgent:
    """Generates PDF and Markdown interview reports."""

    def __init__(self):
        self.report_dir = DATA_DIR / "reports"
        self.report_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------ PDF
    def generate_pdf_report(self, interview_data: Dict, output_path: str = None) -> str:
        if output_path is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.report_dir / f"interview_{_safe_name(interview_data)}_{stamp}.pdf")

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("T", parent=styles["Heading1"], fontSize=22, textColor=colors.HexColor("#1E1B4B"), spaceAfter=10)
        cell = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8.5, leading=11)
        cell_bold = ParagraphStyle("CellB", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
        normal = styles["Normal"]

        def para(text, style=normal):
            return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

        story = [Paragraph(f"Interview Report: {escape(interview_data.get('candidate_name', 'Candidate'))}", title_style)]

        summary = Table([
            ["Candidate", interview_data.get("candidate_name", "N/A")],
            ["Position", interview_data.get("job_title", "N/A")],
            ["Date", interview_data.get("interview_date", datetime.now().strftime("%Y-%m-%d"))],
            ["Mode", interview_data.get("mode", "N/A")],
        ], colWidths=[1.6 * inch, 4.9 * inch])
        summary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2FF")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story += [summary, Spacer(1, 14)]

        # Recommendation
        rec = interview_data.get("recommendation") or {}
        story.append(Paragraph("AI Recommendation (advisory)", styles["Heading2"]))
        story.append(para(f"{rec.get('recommendation', 'Not generated')}  |  Confidence: {rec.get('confidence', 'N/A')}",
                          ParagraphStyle("R", parent=normal, fontName="Helvetica-Bold")))
        story.append(para(rec.get("reason_summary", "")))
        story.append(Spacer(1, 10))

        # Human decision
        review = interview_data.get("human_review")
        story.append(Paragraph("Human Review", styles["Heading2"]))
        if review:
            story.append(para(f"Final decision: {review.get('final_recommendation')} "
                              f"(AI recommended: {review.get('original_recommendation')})"))
            story.append(para(f"Interviewer: {review.get('interviewer_id')}  |  {review.get('override_timestamp')} UTC"))
            if review.get("override_reason"):
                story.append(para(f"Override reason: {review['override_reason']}"))
            if review.get("notes"):
                story.append(para(f"Notes: {review['notes']}"))
        else:
            story.append(para("Pending - no interviewer decision recorded yet."))
        story.append(Spacer(1, 10))

        # Scores
        story.append(Paragraph("Per-Dimension Scores", styles["Heading2"]))
        rows = [[Paragraph(h, cell_bold) for h in ("Dimension", "Score", "Justification", "Evidence (quote)")]]
        for s in interview_data.get("scores", []):
            rows.append([para(s.get("dimension", ""), cell), para(f"{s.get('score', 0)}/5", cell),
                         para(s.get("justification", ""), cell), para(f"\"{s.get('evidence_quote', '')}\"", cell)])
        table = Table(rows, colWidths=[1.2 * inch, 0.5 * inch, 2.5 * inch, 2.3 * inch], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ]))
        story += [table, Spacer(1, 12)]

        # Feedback
        fb = interview_data.get("feedback") or {}
        for heading, key in (("Strengths", "strengths"), ("Gaps", "gaps"), ("Suggested Focus for Next Round", "next_round_focus")):
            story.append(Paragraph(heading, styles["Heading2"]))
            items = _bullets(fb.get(key))
            if items:
                for item in items:
                    story.append(Paragraph("&bull; " + escape(item), normal))
            else:
                story.append(para("Not available."))
            story.append(Spacer(1, 6))

        if rec.get("detailed_reasoning"):
            story.append(Paragraph("Detailed Reasoning", styles["Heading3"]))
            story.append(para(rec["detailed_reasoning"]))

        # Security flags
        story.append(Paragraph("Security Flags", styles["Heading2"]))
        flags = interview_data.get("injection_flags") or []
        if flags:
            story.append(Paragraph(f"<b>{len(flags)} possible prompt-injection attempt(s) detected.</b> "
                                   "The text was removed before scoring.", normal))
            for f in flags:
                story.append(Paragraph(f"&bull; <b>{escape(f.get('type', ''))}</b> in {escape(f.get('source', ''))}: "
                                       f"\"{escape(f.get('excerpt', ''))}\"", normal))
        else:
            story.append(para("No prompt-injection attempts detected."))

        # Transcript
        story += [PageBreak(), Paragraph("Interview Transcript", styles["Heading2"])]
        for block in str(interview_data.get("transcript", "No transcript available")).split("\n\n"):
            story += [para(block.strip()), Spacer(1, 6)]

        SimpleDocTemplate(output_path, pagesize=letter).build(story)
        return output_path

    # ------------------------------------------------------------- Markdown
    def generate_markdown_report(self, interview_data: Dict, output_path: str = None) -> str:
        if output_path is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.report_dir / f"interview_{_safe_name(interview_data)}_{stamp}.md")

        rec = interview_data.get("recommendation") or {}
        fb = interview_data.get("feedback") or {}
        review = interview_data.get("human_review")
        flags = interview_data.get("injection_flags") or []

        def cell(text):
            return str(text or "").replace("|", "\\|").replace("\n", " ")

        def section(title, items):
            items = _bullets(items)
            return f"## {title}\n\n" + ("\n".join(f"- {i}" for i in items) if items else "Not available.") + "\n\n"

        md = f"# Interview Report: {interview_data.get('candidate_name', 'Candidate')}\n\n"
        md += "## Summary\n"
        md += f"- **Position:** {interview_data.get('job_title', 'N/A')}\n"
        md += f"- **Date:** {interview_data.get('interview_date', datetime.now().strftime('%Y-%m-%d'))}\n"
        md += f"- **Mode:** {interview_data.get('mode', 'N/A')}\n\n"

        md += "## AI Recommendation (advisory)\n\n"
        md += f"**{rec.get('recommendation', 'Not generated')}** - Confidence: {rec.get('confidence', 'N/A')}\n\n"
        md += f"{rec.get('reason_summary', '')}\n\n"

        md += "## Human Review\n\n"
        if review:
            md += (f"**Final decision:** {review.get('final_recommendation')} "
                   f"(AI recommended: {review.get('original_recommendation')})\n\n"
                   f"- Interviewer: {review.get('interviewer_id')}\n- Time: {review.get('override_timestamp')} UTC\n")
            if review.get("override_reason"):
                md += f"- Override reason: {review['override_reason']}\n"
            if review.get("notes"):
                md += f"- Notes: {review['notes']}\n"
            md += "\n"
        else:
            md += "Pending - no interviewer decision recorded yet.\n\n"

        md += "## Per-Dimension Scores\n\n| Dimension | Score | Justification | Evidence (quote) |\n|---|---|---|---|\n"
        for s in interview_data.get("scores", []):
            md += (f"| {cell(s.get('dimension'))} | {s.get('score', 0)}/5 | {cell(s.get('justification'))} "
                   f"| \"{cell(s.get('evidence_quote'))}\" |\n")
        md += "\n"

        md += section("Strengths", fb.get("strengths"))
        md += section("Gaps", fb.get("gaps"))
        md += section("Suggested Focus for Next Round", fb.get("next_round_focus"))

        if rec.get("detailed_reasoning"):
            md += f"## Detailed Reasoning\n\n{rec['detailed_reasoning']}\n\n"

        md += "## Security Flags\n\n"
        if flags:
            md += f"**{len(flags)} possible prompt-injection attempt(s) detected.** The text was removed before scoring.\n\n"
            md += "\n".join(f"- **{f.get('type', '')}** in {f.get('source', '')}: `{f.get('excerpt', '')}`" for f in flags) + "\n\n"
        else:
            md += "No prompt-injection attempts detected.\n\n"

        md += f"## Interview Transcript\n\n{interview_data.get('transcript', 'No transcript available')}\n\n---\n\n"
        md += f"*Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)
        return output_path

    def generate_reports(self, interview_data: Dict, pdf: bool = True, md: bool = True) -> Dict[str, str]:
        paths = {}
        if pdf:
            paths["pdf"] = self.generate_pdf_report(interview_data)
        if md:
            paths["markdown"] = self.generate_markdown_report(interview_data)
        return paths
