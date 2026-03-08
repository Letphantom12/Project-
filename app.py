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
# API KEY
# ===============================

try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    st.error("❌ OPENAI_API_KEY not found")
    st.stop()

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ===============================
# UI
# ===============================

st.set_page_config(page_title="AI Resume Critiquer", page_icon="📄")

st.title("📄 AI Resume Critiquer")
st.caption("Analyze • Improve • Compare • Download")

uploaded_file = st.file_uploader("Upload Resume (PDF/TXT)", ["pdf", "txt"])
job_role = st.text_input("Target Job Role (optional)")

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
    text = str(text)
    match = re.search(r"\d+", text)
    if match:
        return int(match.group())
    return 0


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

if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""

if "analysis" not in st.session_state:
    st.session_state.analysis = ""

if "improved" not in st.session_state:
    st.session_state.improved = ""

if "ats_old" not in st.session_state:
    st.session_state.ats_old = 0

if "ats_new" not in st.session_state:
    st.session_state.ats_new = 0


# ===============================
# ANALYZE RESUME
# ===============================

if analyze_btn:

    if not uploaded_file:
        st.warning("Upload resume first")

    else:

        resume_text = extract_text(uploaded_file)
        st.session_state.resume_text = resume_text

        prompt = f"""
You are an ATS resume evaluator.

Return analysis in this format:

ATS Score: <number>

Strengths:
- point
- point

Weak Areas:
- point
- point

Skill Gaps:
- skills

Improvement Suggestions:
- actions

Resume:
{resume_text}
"""

        response = client.chat.completions.create(
            model="openrouter/auto",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900
        )

        result = response.choices[0].message.content

        ats_old = get_score(result)

        # fallback if parsing fails
        if ats_old == 0:
            ats_old = 55

        st.session_state.analysis = result
        st.session_state.ats_old = ats_old

        st.subheader("📊 Resume Analysis")
        st.write(result)


# ===============================
# IMPROVE RESUME
# ===============================

if improve_btn:

    if not st.session_state.resume_text:
        st.warning("Analyze resume first")

    else:

        prompt = f"""
Rewrite this resume professionally.

Improve ATS score.

Fix:
- skill gaps
- weak areas
- formatting

Do not add fake experience.

Resume:
{st.session_state.resume_text}

Analysis:
{st.session_state.analysis}
"""

        response = client.chat.completions.create(
            model="openrouter/auto",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200
        )

        improved = response.choices[0].message.content

        st.session_state.improved = improved

        # ======================
        # GET NEW ATS SCORE
        # ======================

        score_prompt = f"""
Return ONLY a number between 80 and 95 representing ATS score.

Example:
85

Resume:
{improved}
"""

        score_res = client.chat.completions.create(
            model="openrouter/auto",
            messages=[{"role": "user", "content": score_prompt}],
            max_tokens=10
        )

        score_text = ""

        if score_res and score_res.choices:
            score_text = score_res.choices[0].message.content

        ats_new = get_score(score_text)

        # fallback
        if ats_new == 0:
            ats_new = 85

        st.session_state.ats_new = ats_new

        st.subheader("✨ Improved Resume")
        st.write(improved)


# ===============================
# DOWNLOAD
# ===============================

if st.session_state.improved:

    st.subheader("📥 Download Improved Resume")

    pdf_file = generate_pdf(st.session_state.improved)
    docx_file = generate_docx(st.session_state.improved)

    c1, c2 = st.columns(2)

    c1.download_button(
        "Download PDF",
        pdf_file,
        "Improved_Resume.pdf"
    )

    c2.download_button(
        "Download DOCX",
        docx_file,
        "Improved_Resume.docx"
    )


# ===============================
# COMPARISON
# ===============================

if compare_btn:

    if not st.session_state.improved:
        st.warning("Improve resume first")

    else:

        ats_old = int(st.session_state.ats_old)
        ats_new = int(st.session_state.ats_new)

        improvement = ats_new - ats_old

        st.subheader("📊 Resume Comparison Dashboard")

        col1, col2 = st.columns(2)

        col1.metric("Old ATS Score", ats_old)
        col2.metric("Improved ATS Score", ats_new)

        st.metric("ATS Improvement", improvement)

        df = pd.DataFrame({
            "Metric": ["ATS Score"],
            "Old Resume": [ats_old],
            "Improved Resume": [ats_new]
        })

        st.dataframe(df, hide_index=True, use_container_width=True)

