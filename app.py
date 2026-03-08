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

# =====================================
# API KEY
# =====================================

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

# =====================================
# UI
# =====================================

st.set_page_config(page_title="AI Resume Critiquer", page_icon="📃")

st.title("📃 AI Resume Critiquer")
st.caption("Analyze • Improve • Compare • Download")

uploaded_file = st.file_uploader("Upload Resume (PDF/TXT)", ["pdf", "txt"])
job_role = st.text_input("Target Job Role (optional)")

c1, c2, c3 = st.columns(3)

analyze_btn = c1.button("Analyze")
improve_btn = c2.button("Improve")
compare_btn = c3.button("Compare")

# =====================================
# FUNCTIONS
# =====================================

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


# =====================================
# SESSION STATE
# =====================================

for key in ["resume_text", "analysis", "improved", "ats_old", "ats_new"]:
    if key not in st.session_state:
        st.session_state[key] = ""


# =====================================
# ANALYZE RESUME
# =====================================

if analyze_btn:

    if not uploaded_file:
        st.warning("Upload resume first")

    else:

        resume_text = extract_text(uploaded_file)
        st.session_state.resume_text = resume_text

        prompt = f"""
You are an ATS resume evaluator.

IMPORTANT:
- Respond ONLY in English
- Analyze the resume professionally

Return in this format:

ATS Score: <number>

Strengths:
- point
- point

Weak Areas:
- point
- point

Skill Gaps:
- missing skills

Improvement Suggestions:
- action
- action

Resume:
{resume_text}
"""

        response = client.chat.completions.create(
            model="openrouter/auto",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=900
        )

        result = response.choices[0].message.content

        st.session_state.analysis = result
        st.session_state.ats_old = get_score(str(result))

        st.subheader("📊 Resume Analysis")
        st.write(result)


# =====================================
# IMPROVE RESUME
# =====================================

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
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200
        )

        improved = response.choices[0].message.content

        st.session_state.improved = improved

        score_prompt = f"Give ATS score only number for this resume:\n{improved}"

        score_res = client.chat.completions.create(
            model="openrouter/auto",
            messages=[
                {"role": "user", "content": score_prompt}
            ],
            max_tokens=10
        )

        score_text = score_res.choices[0].message.content
        st.session_state.ats_new = get_score(score_text)

        st.subheader("✨ Improved Resume")
        st.write(improved)


# =====================================
# DOWNLOAD
# =====================================

if st.session_state.improved:

    st.subheader("📥 Download Improved Resume")

    pdf_file = generate_pdf(st.session_state.improved)
    docx_file = generate_docx(st.session_state.improved)

    a, b = st.columns(2)

    a.download_button("Download PDF", pdf_file, "Improved_Resume.pdf")
    b.download_button("Download DOCX", docx_file, "Improved_Resume.docx")


# =====================================
# COMPARISON
# =====================================

if compare_btn:

    if not st.session_state.improved:
        st.warning("Improve resume first")

    else:

        ats_old = st.session_state.ats_old
        ats_new = st.session_state.ats_new

        improvement = ats_new - ats_old

        st.subheader("📊 Resume Comparison Dashboard")

        df = pd.DataFrame({
            "Metric": ["ATS Score"],
            "Old Resume": [ats_old],
            "Improved Resume": [ats_new]
        })

        st.dataframe(df, hide_index=True, use_container_width=True)

        st.metric("ATS Improvement", ats_new, improvement)
