import streamlit as st
import PyPDF2
import io
import os
import re
import hashlib
from openai import OpenAI
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from io import BytesIO
from docx import Document

# -------------------- API KEY (WORKS FOR GITHUB + LOCAL) --------------------
OPENAI_API_KEY = os.getenv("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")

if not OPENAI_API_KEY:
    st.error("❌ API key missing. Add it in Streamlit Secrets or environment variables.")
    st.stop()

client = OpenAI(
    api_key="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",
    base_url="https://openrouter.ai/api/v1"
)

# -------------------- UI --------------------
st.set_page_config(page_title="AI Resume Critiquer", page_icon="📄", layout="centered")
st.title("📄 AI Resume Critiquer")
st.write("Analyze, improve, and download your resume using AI.")

uploaded_file = st.file_uploader("Upload Resume (PDF or TXT)", ["pdf", "txt"])
job_role = st.text_input("Target Job Role (optional)")

analyze_btn = st.button("Analyze Resume")
improve_btn = st.button("Generate Improved Resume")
compare_btn = st.button("Compare Resumes")

# -------------------- SESSION STATE --------------------
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "analysis_text" not in st.session_state:
    st.session_state.analysis_text = ""
if "improved_resume" not in st.session_state:
    st.session_state.improved_resume = ""
if "analysis_cache" not in st.session_state:
    st.session_state.analysis_cache = {}

# -------------------- FUNCTIONS --------------------
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + "\n"
    return text

def extract_text(file):
    if file.type == "application/pdf":
        return extract_text_from_pdf(io.BytesIO(file.read()))
    return file.read().decode("utf-8", errors="ignore")

def extract_ats(text):
    match = re.search(r"ATS_SCORE\s*:\s*(\d+)", text)
    return int(match.group(1)) if match else 0

def get_hash(text):
    return hashlib.md5(text.encode()).hexdigest()

def generate_pdf(text):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(line, styles["Normal"]) for line in text.split("\n")]
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_docx(text):
    document = Document()
    for line in text.split("\n"):
        if line.isupper():
            document.add_heading(line, level=2)
        else:
            document.add_paragraph(line)
    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer

# -------------------- STEP 1: ANALYZE --------------------
if analyze_btn and uploaded_file:
    resume_text = extract_text(uploaded_file)[:800]
    st.session_state.resume_text = resume_text
    resume_hash = get_hash(resume_text + job_role)

    if resume_hash in st.session_state.analysis_cache:
        analysis_text = st.session_state.analysis_cache[resume_hash]
    else:
        with st.spinner("Analyzing resume..."):
            prompt = f"""
ATS score this resume for {job_role if job_role else "general role"}.

Return format:
ATS_SCORE: number

Strengths:
- points

Weaknesses:
- points

Skill Gaps:
- points

Resume:
{resume_text}
"""
            response = client.responses.create(
                model="openrouter/auto",
                input=prompt,
                temperature=0,
                max_output_tokens=400
            )
            analysis_text = response.output_text
            st.session_state.analysis_cache[resume_hash] = analysis_text

    st.session_state.analysis_text = analysis_text
    st.subheader("📊 Resume Analysis")
    st.write(analysis_text)

# -------------------- STEP 2: IMPROVE --------------------
if improve_btn and st.session_state.resume_text:
    with st.spinner("Improving resume..."):
        prompt = f"""
Rewrite resume with:
- ATS format
- action verbs
- quantified achievements
- clear sections

Do not add fake experience.

Resume:
{st.session_state.resume_text}

Suggestions:
{st.session_state.analysis_text}
"""
        response = client.responses.create(
            model="openrouter/auto",
            input=prompt,
            temperature=0,
            max_output_tokens=400
        )
        st.session_state.improved_resume = response.output_text

    st.subheader("✨ Improved Resume")
    st.write(st.session_state.improved_resume)

# -------------------- STEP 3: COMPARE --------------------
if compare_btn:
    if st.session_state.analysis_text and st.session_state.improved_resume:
        old_ats = extract_ats(st.session_state.analysis_text)

        with st.spinner("Evaluating improved resume..."):
            prompt = f"""
Compare ATS scores.

Original:
{st.session_state.resume_text}

Improved:
{st.session_state.improved_resume}

Return:
ATS_SCORE: number
"""
            response = client.responses.create(
                model="openrouter/auto",
                input=prompt,
                temperature=0,
                max_output_tokens=200
            )

        new_ats = extract_ats(response.output_text)
        improvement = new_ats - old_ats

        st.subheader("🔍 ATS Comparison")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Original ATS Score", f"{old_ats}/100")
        with col2:
            st.metric("Improved ATS Score", f"{new_ats}/100", delta=improvement)

        st.subheader("📈 ATS Visualization")
        st.write("Original Resume")
        st.progress(old_ats / 100)
        st.write("Improved Resume")
        st.progress(new_ats / 100)
    else:
        st.info("Please analyze and improve the resume first.")

# -------------------- DOWNLOAD --------------------
st.subheader("📥 Download Improved Resume")
if st.session_state.improved_resume:
    pdf_file = generate_pdf(st.session_state.improved_resume)
    docx_file = generate_docx(st.session_state.improved_resume)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Download PDF", data=pdf_file,
                           file_name="Improved_Resume.pdf", mime="application/pdf")
    with col2:
        st.download_button("Download DOCX", data=docx_file,
                           file_name="Improved_Resume.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
else:
    st.info("Generate improved resume first.")
