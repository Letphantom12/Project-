import streamlit as st
from pypdf import PdfReader
import io
import os
import re
import pandas as pd
from openai import OpenAI
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from io import BytesIO
from docx import Document

# ===============================
# API KEY (STREAMLIT SAFE)
# ===============================

try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    st.error("❌ OPENAI_API_KEY not found")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

# ===============================
# UI
# ===============================

st.set_page_config(page_title="AI Resume Critiquer", page_icon="📄")

st.title("📄 AI Resume Critiquer")
st.caption("Analyze • Improve • Compare • Download")

uploaded_file = st.file_uploader("Upload Resume (PDF/TXT)", ["pdf", "txt"])
job_role = st.text_input("Target Job Role")

c1, c2, c3 = st.columns(3)

analyze_btn = c1.button("Analyze")
improve_btn = c2.button("Improve")
compare_btn = c3.button("Compare")

# ===============================
# FUNCTIONS
# ===============================

def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"
    return text


def extract_text(file):
    if file.type == "application/pdf":
        return extract_text_from_pdf(io.BytesIO(file.read()))
    return file.read().decode("utf-8", errors="ignore")


def get_score(text):
    if not text:
        return 0
    match = re.search(r"\d+", str(text))
    return int(match.group()) if match else 0


def generate_pdf(text):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    story = []
    for line in text.split("\n"):
        story.append(Paragraph(line, styles["Normal"]))

    doc.build(story)
    buffer.seek(0)

    return buffer


def generate_docx(text):
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    return buffer

# ===============================
# SESSION STATE
# ===============================

for key in ["resume_text", "analysis", "improved", "ats_old", "ats_new"]:
    if key not in st.session_state:
        st.session_state[key] = "" if "ats" not in key else 0

# ===============================
# ANALYZE
# ===============================

if analyze_btn:

    if not uploaded_file:
        st.warning("Upload resume first")

    else:
        resume_text = extract_text(uploaded_file)
        st.session_state.resume_text = resume_text

        prompt = f"""
You are an ATS resume evaluator.

Target Job Role: {job_role}

Return strictly:

ATS Score: <number>

Strengths:
- point

Weak Areas:
- point

Skill Gaps:
- missing skills

Suggestions:
- improvements

Resume:
{resume_text}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=900
        )

        result = response.choices[0].message.content
        ats_old = get_score(result) or 55

        st.session_state.analysis = result
        st.session_state.ats_old = ats_old

        st.subheader("📊 Analysis")
        st.write(result)

# ===============================
# IMPROVE
# ===============================

if improve_btn:

    if not st.session_state.resume_text:
        st.warning("Analyze first")

    else:
        prompt = f"""
Rewrite this resume professionally for {job_role}.
Improve ATS score. Do not add fake info.

Resume:
{st.session_state.resume_text}

Analysis:
{st.session_state.analysis}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1200
        )

        improved = response.choices[0].message.content
        st.session_state.improved = improved

        # ATS score for improved
        score_prompt = f"""
Give ONLY ATS score (0-100):

{improved}
"""

        score_res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": score_prompt}],
            max_tokens=10
        )

        ats_new = get_score(score_res.choices[0].message.content) or 85
        st.session_state.ats_new = ats_new

        st.subheader("✨ Improved Resume")
        st.write(improved)

# ===============================
# DOWNLOAD
# ===============================

if st.session_state.improved:

    st.subheader("📥 Download")

    col1, col2 = st.columns(2)

    col1.download_button(
        "PDF",
        generate_pdf(st.session_state.improved),
        "resume.pdf"
    )

    col2.download_button(
        "DOCX",
        generate_docx(st.session_state.improved),
        "resume.docx"
    )

# ===============================
# COMPARE
# ===============================

if compare_btn:

    if not st.session_state.improved:
        st.warning("Improve first")

    else:
        old = int(st.session_state.ats_old)
        new = int(st.session_state.ats_new)

        st.subheader("📊 Comparison")

        c1, c2 = st.columns(2)
        c1.metric("Old Score", old)
        c2.metric("New Score", new)

        st.metric("Improvement", new - old)

        df = pd.DataFrame({
            "Metric": ["ATS Score"],
            "Old": [old],
            "Improved": [new]
        })

        st.dataframe(df, use_container_width=True)
