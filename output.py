
import os
import re
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Image as RLImage, HRFlowable)

REQUIRED_FIELDS = ["name", "phone", "email", "summary", "education", "skills", "experience", "projects"]

SECTIONS = [
    ("Summary", "summary"),
    ("Education", "education"),
    ("Skills", "skills"),
    ("Experience", "experience"),
    ("Projects", "projects"),
]

BULLET_KEYS = {"education", "experience", "projects"}

STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "this", "that",
    "from", "have", "has", "who", "can", "able", "etc", "all", "any", "about", "into",
    "their", "they", "must", "should", "good", "strong", "knowledge", "ability", "work",
    "working", "role", "team", "using", "use", "such", "also", "than", "more",
}

TEMPLATES = {
    "Classic": {"body": "Times-Roman", "bold": "Times-Bold", "align": TA_CENTER, "name_size": 22, "minimal": False},
    "Modern": {"body": "Helvetica", "bold": "Helvetica-Bold", "align": TA_LEFT, "name_size": 24, "minimal": False},
    "Minimal": {"body": "Helvetica", "bold": "Helvetica-Bold", "align": TA_LEFT, "name_size": 20, "minimal": True},
}


def build_preview_text(data):
    lines = []
    name = (data.get("name") or "").strip() or "Your Name"
    lines.append(name.upper())
    contact = " | ".join(x.strip() for x in [data.get("email") or "", data.get("phone") or ""] if x.strip())
    if contact:
        lines.append(contact)
    for title, key in SECTIONS:
        text = (data.get(key) or "").strip()
        if text:
            lines.append("")
            lines.append(title.upper())
            lines.append(text)
    return "\n".join(lines)


def completeness(data):
    filled = sum(1 for key in REQUIRED_FIELDS if str(data.get(key) or "").strip())
    return round(filled / len(REQUIRED_FIELDS) * 100)


def ats_score(resume_text, job_text):
    words = re.findall(r"[a-zA-Z+#]+", job_text.lower())
    keywords = {w for w in words if len(w) > 2 and w not in STOPWORDS}
    if not keywords:
        return 0, []
    resume_lower = resume_text.lower()
    found = [k for k in keywords if k in resume_lower]
    missing = sorted(k for k in keywords if k not in resume_lower)
    score = round(len(found) / len(keywords) * 100)
    return score, missing


def export_pdf(data, file_name):
    info = TEMPLATES.get(data.get("template"), TEMPLATES["Classic"])
    accent = HexColor(data.get("color") or "#1f4e79")
    minimal = info["minimal"]
    text_color = black if minimal else accent
    align = info["align"]

    name_style = ParagraphStyle("Name", fontName=info["bold"], fontSize=info["name_size"],
                                leading=info["name_size"] + 4, alignment=align,
                                textColor=text_color, spaceAfter=4)
    contact_style = ParagraphStyle("Contact", fontName=info["body"], fontSize=10, leading=13,
                                   alignment=align, spaceAfter=10)
    heading_style = ParagraphStyle("Heading", fontName=info["bold"], fontSize=12.5, leading=16,
                                   textColor=text_color, spaceBefore=10, spaceAfter=4, alignment=TA_LEFT)
    body_style = ParagraphStyle("Body", fontName=info["body"], fontSize=10.5, leading=14, spaceAfter=3)

    story = []
    temp_photo = None
    photo_file = data.get("photo_path") or ""
    if photo_file and os.path.exists(photo_file):
        try:
            img = PILImage.open(photo_file).convert("RGB")
            img.thumbnail((400, 400))
            temp_photo = os.path.join(os.path.dirname(os.path.abspath(file_name)), "_temp_photo.png")
            img.save(temp_photo)
            photo = RLImage(temp_photo, width=1.1 * inch, height=1.1 * inch)
            photo.hAlign = "CENTER" if align == TA_CENTER else "LEFT"
            story.append(photo)
            story.append(Spacer(1, 8))
        except Exception:
            temp_photo = None

    story.append(Paragraph(escape((data.get("name") or "").strip()), name_style))
    contact = " | ".join(x.strip() for x in [data.get("email") or "", data.get("phone") or ""] if x.strip())
    story.append(Paragraph(escape(contact), contact_style))

    for title, key in SECTIONS:
        text = (data.get(key) or "").strip()
        if not text:
            continue
        story.append(Paragraph(title.upper(), heading_style))
        if not minimal:
            story.append(HRFlowable(width="100%", thickness=0.8, color=accent, spaceBefore=0, spaceAfter=4))
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            prefix = "• " if key in BULLET_KEYS else ""
            story.append(Paragraph(escape(prefix + line), body_style))

    doc = SimpleDocTemplate(file_name, pagesize=A4, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    try:
        doc.build(story)
    finally:
        if temp_photo and os.path.exists(temp_photo):
            os.remove(temp_photo)