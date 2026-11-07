"""
MEXT Scholarship Interview Practice Bot - Streamlit Web App
Features:
- Question Bank from questions.py (10 random questions without repeats)
- Interactive interview flow with session state & question counter
- Clean AI feedback (no internal notes/preamble)
- Score cards (Grammar, Clarity, Content) using st.columns and st.metric
- Expandable feedback sections using st.expander
- Dual-source API key (st.secrets & .env) with active Gemini models
- Optimized low-latency evaluation with performance tracking (perf_counter)
"""

import json
import os
import random
import time
import warnings
import streamlit as st
from dotenv import load_dotenv

# Suppress deprecation warnings for a clean user interface
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from google.generativeai.types import RequestOptions

# Import question bank from separate questions.py file
from questions import get_questions_for_level

# Load environment variables from local .env file (if running locally)
load_dotenv()

# Track configured API key to avoid redundant genai.configure() calls
_CONFIGURED_API_KEY = None


def get_api_key():
    """
    Retrieve the Gemini API key safely.
    Checks:
      1. Streamlit Secrets (st.secrets) - used when deploying on Streamlit Community Cloud.
      2. Environment variables (.env file via load_dotenv) - used for local development.
    Returns:
        str or None: The API key if found, otherwise None.
    """
    try:
        if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    env_key = os.getenv("GEMINI_API_KEY")
    if env_key and env_key != "your_gemini_api_key_here":
        return env_key

    return None


def clean_text_content(text: str) -> str:
    """
    Removes any internal AI reasoning/notes (Role, Target, Constraint, Section plan)
    from the feedback text to ensure clean, student-facing output.
    """
    if not text:
        return ""

    unwanted_prefixes = (
        "role:", "target:", "constraint:", "constraints:",
        "section plan:", "plan:", "internal note:", "notes:",
        "### role", "### target", "### constraint", "### plan"
    )

    cleaned_lines = []
    for line in str(text).strip().splitlines():
        line_lower = line.strip().lower()
        if any(line_lower.startswith(prefix) for prefix in unwanted_prefixes):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def get_safe_error_category(exception: Exception) -> str:
    """
    Categorizes exceptions into safe, standardized error descriptions
    without exposing raw exception text or sensitive server details.
    """
    exc_type = type(exception).__name__
    exc_msg = str(exception).lower()

    if "deadline" in exc_msg or "timeout" in exc_msg or "timed out" in exc_msg:
        return "Request Timeout (45s limit reached)"
    elif "404" in exc_msg or "not found" in exc_msg:
        return "Model Unavailable / Not Found"
    elif "403" in exc_msg or "permission" in exc_msg or "api_key" in exc_msg or "unauthenticated" in exc_msg:
        return "Authentication / API Key Error"
    elif "429" in exc_msg or "quota" in exc_msg or "resource_exhausted" in exc_msg:
        return "API Quota / Rate Limit Exceeded"
    elif "connection" in exc_msg or "dns" in exc_msg or "network" in exc_msg:
        return "Network / Connection Error"
    elif "max_tokens" in exc_msg or "finish_reason" in exc_msg:
        return "Token Limit Exceeded"
    elif "parse" in exc_msg or "json" in exc_msg or "valueerror" in exc_msg:
        return "Response Parsing Error"
    else:
        return f"{exc_type} (Service Error)"


def extract_response_text(response) -> str:
    """
    Safely extracts text content from GenerateContentResponse,
    bypassing property errors caused by finish-reason flags or multiple parts.
    """
    if not response:
        return ""

    # 1. Inspect candidate parts directly
    if hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
            collected = []
            for part in candidate.content.parts:
                part_text = getattr(part, "text", "")
                if part_text:
                    collected.append(part_text)
            if collected:
                return "\n".join(collected).strip()

    # 2. Try the quick accessor property
    try:
        if hasattr(response, "text") and response.text:
            return response.text.strip()
    except Exception:
        pass

    return ""


def parse_feedback_response(response_text: str) -> dict:
    """
    Parses the Gemini output into structured scores and 5 feedback sections.
    Guarantees valid scores (out of 10) and clean text for all feedback sections.
    Raises ValueError only if response text contains no extractable feedback.
    """
    import re

    cleaned = response_text.strip()

    # Strip code block fences if returned by model
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Attempt 1: Parse standard JSON with strict=False
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        try:
            data = json.loads(cleaned[start : end + 1], strict=False)
            grammar_score = min(10, max(1, int(data.get("grammar_score", 5))))
            clarity_score = min(10, max(1, int(data.get("clarity_score", 5))))
            content_score = min(10, max(1, int(data.get("content_score", 5))))

            return {
                "grammar_score": grammar_score,
                "clarity_score": clarity_score,
                "content_score": content_score,
                "grammar_feedback": clean_text_content(data.get("grammar_feedback", "")),
                "clarity_feedback": clean_text_content(data.get("clarity_feedback", "")),
                "relevance_feedback": clean_text_content(data.get("relevance_feedback", "")),
                "strengths": clean_text_content(data.get("strengths", "")),
                "improvements": clean_text_content(data.get("improvements", "")),
            }
        except Exception:
            pass

    # Attempt 2: Flexible regex extraction handling escaped quotes and multi-line values
    def extract_field(field_name: str, text: str) -> str:
        pattern = rf'"{field_name}"\s*:\s*"((?:\\.|[^"\\])*)"'
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if m:
            val = m.group(1).replace(r"\"", '"').replace(r"\n", "\n")
            return val.strip()
        return ""

    def extract_score(field_name: str, text: str, default: int = 5) -> int:
        m = re.search(rf'"{field_name}"\s*:\s*(\d+)', text, re.IGNORECASE)
        if m:
            try:
                return min(10, max(1, int(m.group(1))))
            except Exception:
                pass
        return default

    grammar_fb = extract_field("grammar_feedback", cleaned)
    clarity_fb = extract_field("clarity_feedback", cleaned)
    relevance_fb = extract_field("relevance_feedback", cleaned)
    strengths_fb = extract_field("strengths", cleaned)
    improvements_fb = extract_field("improvements", cleaned)

    if grammar_fb or relevance_fb or strengths_fb or improvements_fb:
        return {
            "grammar_score": extract_score("grammar_score", cleaned, default=6),
            "clarity_score": extract_score("clarity_score", cleaned, default=6),
            "content_score": extract_score("content_score", cleaned, default=5),
            "grammar_feedback": clean_text_content(grammar_fb) if grammar_fb else "Grammar evaluated.",
            "clarity_feedback": clean_text_content(clarity_fb) if clarity_fb else "Clarity evaluated.",
            "relevance_feedback": clean_text_content(relevance_fb) if relevance_fb else "Relevance evaluated.",
            "strengths": clean_text_content(strengths_fb) if strengths_fb else "No relevant strengths were demonstrated in this response.",
            "improvements": clean_text_content(improvements_fb) if improvements_fb else "Please review question requirements.",
        }

    # If completely unparseable, do NOT invent fake positive praise
    raise ValueError("Model response could not be parsed into structured interview feedback.")


def evaluate_interview_answer(api_key: str, question: str, answer: str) -> dict:
    """
    Calls Gemini API with performance instrumentation using time.perf_counter().
    Evaluates candidate's actual latest answer strictly against the interview question.
    Returns:
        dict: Parsed evaluation containing scores, clean 5 feedback sections, and timings.
    """
    global _CONFIGURED_API_KEY
    t_start = time.perf_counter()

    prompt = f"""
You are an expert, objective MEXT scholarship interview evaluator.
Evaluate the candidate's actual submitted answer strictly against the specific interview question asked.

Interview Question:
"{question}"

Candidate's Submitted Answer:
"{answer}"

STRICT EVALUATION INSTRUCTIONS:
1. SPECIFICITY: Base your evaluation solely on the candidate's actual submitted answer. Do not assume or invent facts not present in their response.
2. RELEVANCE & CONTENT:
   - Critically evaluate whether the answer directly addresses the specific question asked.
   - Detect if the answer is irrelevant, off-topic, incomplete, weak, dismissive, hostile, or shows a lack of interest in the scholarship/topic.
   - If the answer is off-topic, inappropriate, or shows a lack of motivation/interest, assign a low Content score (1-4/10) and explicitly explain why in "relevance_feedback".
3. OBJECTIVE STRENGTHS (NO FAKE OR GENERIC PRAISE):
   - Highlight genuine strengths ONLY when they are actually present in the candidate's response.
   - If the answer is weak, inappropriate, dismissive, or irrelevant, state clearly: "No relevant strengths were demonstrated in this response."
   - Never generate generic positive praise (such as claiming passion for AI or Japan) if the candidate did not actually express it.
4. INDEPENDENT GRAMMAR EVALUATION:
   - Evaluate English grammar independently from content or attitude.
   - If an answer is grammatically well-formed but inappropriate or off-topic, assign a high Grammar score (8-10/10) and do NOT invent grammar mistakes.
   - If there are grammatical/vocabulary errors, point them out specifically with corrected phrasing.
5. ACTIONABLE IMPROVEMENT:
   - Provide concrete, question-specific advice explaining how a strong MEXT candidate should structure an answer to THIS specific question.
6. FORMAT & CONCISENESS:
   - Output ONLY valid JSON matching the exact schema below. Keep each section focused and concise (1-2 sentences).

REQUIRED JSON FORMAT:
{{
  "grammar_score": <integer 1-10>,
  "clarity_score": <integer 1-10>,
  "content_score": <integer 1-10>,
  "grammar_feedback": "Accurate assessment of grammar, syntax, and vocabulary. Do not invent errors if grammar is correct.",
  "clarity_feedback": "Assessment of sentence clarity, organization, and directness.",
  "relevance_feedback": "Direct evaluation of whether and how well the answer addresses this specific question. Call out off-topic or inappropriate responses.",
  "strengths": "Genuine strengths observed, or 'No relevant strengths were demonstrated in this response.' if weak or inappropriate.",
  "improvements": "Specific, actionable tips tailored directly to answering this question effectively."
}}
"""

    try:
        # Strip accidental whitespace or quotes from API key safely
        clean_api_key = api_key.strip().strip('"').strip("'")

        # Configure SDK with REST transport to prevent gRPC proxy hangs on cloud containers
        if _CONFIGURED_API_KEY != clean_api_key:
            genai.configure(api_key=clean_api_key, transport="rest")
            _CONFIGURED_API_KEY = clean_api_key

        # Optimized generation parameters with adequate headroom for reasoning & 5-section JSON output
        generation_config = {
            "temperature": 0.3,
            "max_output_tokens": 2048,
            "response_mime_type": "application/json",
        }

        # Explicit RequestOptions with 45s timeout and retry=None to prevent indefinite cloud container hangs
        # while giving reasoning models sufficient headroom for multi-criteria evaluation
        request_options = RequestOptions(timeout=45.0, retry=None)

        # Candidate models ordered by latency: latest active stable Flash models
        # Prioritize gemini-3.8-flash (primary stable), fallback to gemini-3.5-flash
        candidate_models = ["gemini-3.8-flash", "gemini-3.5-flash"]
        cached_model = st.session_state.get("working_gemini_model")
        if cached_model and cached_model in candidate_models:
            candidate_models.remove(cached_model)
            candidate_models.insert(0, cached_model)

        t_prep_end = time.perf_counter()
        prep_time_ms = (t_prep_end - t_start) * 1000

        last_error_category = None
        attempt_log = []

        for model_name in candidate_models:
            t_api_start = time.perf_counter()
            try:
                print(f"[Gemini API] Querying model={model_name} | transport=rest | timeout=45s")
                model = genai.GenerativeModel(model_name, generation_config=generation_config)
                response = model.generate_content(prompt, request_options=request_options)
                t_api_end = time.perf_counter()
                api_time_s = t_api_end - t_api_start
                print(f"[Gemini API] Success: model={model_name} | duration={api_time_s:.2f}s")

                raw_text = extract_response_text(response)
                if raw_text:
                    t_parse_start = time.perf_counter()
                    parsed = parse_feedback_response(raw_text)
                    t_parse_end = time.perf_counter()

                    parse_time_ms = (t_parse_end - t_parse_start) * 1000
                    total_time_s = t_parse_end - t_start

                    # Cache the working model for subsequent calls
                    st.session_state.working_gemini_model = model_name

                    # Store performance metrics
                    parsed["timings"] = {
                        "prep_ms": prep_time_ms,
                        "api_s": api_time_s,
                        "parse_ms": parse_time_ms,
                        "total_s": total_time_s,
                        "model": model_name,
                    }
                    return parsed

            except Exception as e:
                t_err = time.perf_counter()
                attempt_duration = t_err - t_api_start
                safe_category = get_safe_error_category(e)
                print(f"[Gemini API] Failed: model={model_name} | category={safe_category} | duration={attempt_duration:.2f}s")
                last_error_category = safe_category
                attempt_log.append(f"Model: {model_name} | Status: {safe_category} | Duration: {attempt_duration:.2f}s")
                continue

        if last_error_category:
            st.error(f"Error calling Gemini API: {last_error_category}")
            with st.expander("🔍 Diagnostic Details"):
                for entry in attempt_log:
                    st.write(f"- {entry}")
            return None

    except Exception as error:
        safe_init_category = get_safe_error_category(error)
        print(f"[Gemini API] Initialization failed | category={safe_init_category}")
        st.error(f"Error initializing Gemini: {safe_init_category}")
        return None


def init_interview_session(level: str):
    """
    Initializes or resets the interview session state:
    picks 10 random questions without repeats from questions.py.
    """
    all_questions = get_questions_for_level(level)
    # Pick 10 random questions without replacement
    st.session_state.selected_questions = random.sample(all_questions, min(10, len(all_questions)))
    st.session_state.current_question_index = 0
    st.session_state.answers = {}
    st.session_state.feedbacks = {}
    st.session_state.active_level = level
    st.session_state.interview_started = True


def main():
    # Streamlit page setup
    st.set_page_config(
        page_title="MEXT Interview Practice Bot",
        page_icon="🎓",
        layout="centered",
    )

    # Custom CSS for Design Rules:
    # White background (#FFFFFF), navy headings (#172554), blue primary buttons (#3B82F6),
    # teal for positive feedback (#14B8A6), amber for improvements (#F59E0B), light grey cards (#F8FAFC)
    # No animations, no pink accents, mobile and desktop responsive
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #FFFFFF;
            color: #172554;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #172554 !important;
            font-weight: 700 !important;
        }
        button[kind="primary"], .stButton > button[kind="primary"] {
            background-color: #3B82F6 !important;
            border-color: #3B82F6 !important;
            color: #FFFFFF !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
        }
        button[kind="primary"]:hover {
            background-color: #2563EB !important;
            border-color: #2563EB !important;
        }
        div[data-testid="stExpander"] {
            background-color: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 8px !important;
        }
        * {
            animation: none !important;
            transition: none !important;
        }
        button[kind="primary"] {
            transition: background-color 0.15s ease-in-out !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Initialize interview session flags
    if "interview_started" not in st.session_state:
        st.session_state.interview_started = False
    if "active_level" not in st.session_state:
        st.session_state.active_level = "Beginner"

    # SECTION 1: Welcome / Dashboard Screen
    if not st.session_state.interview_started:
        st.title("🎓 MEXT Scholarship Interview Practice Bot")
        st.markdown(
            """
            Master your MEXT scholarship interview with realistic questions and instant AI feedback.  
            Choose your experience level below and click **Start Interview** to begin your 10-question practice session.
            """
        )

        st.markdown(
            """
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.25rem; margin-top: 1rem; margin-bottom: 1.25rem;">
                <h4 style="color: #172554; margin: 0 0 0.5rem 0;">Choose Difficulty Level</h4>
                <p style="color: #475569; font-size: 0.95rem; margin-bottom: 0.75rem; line-height: 1.5;">
                    • <b>Beginner:</b> Foundational motivation, Japanese culture, university choices, and study planning.<br>
                    • <b>Experienced:</b> In-depth research methodology, academic contribution, challenges, and bilateral diplomacy.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_level = st.radio(
            "Select your interview difficulty level:",
            options=["Beginner", "Experienced"],
            index=0 if st.session_state.active_level == "Beginner" else 1,
            horizontal=True,
        )

        st.write("")
        if st.button("🚀 Start Interview", type="primary", use_container_width=True):
            init_interview_session(selected_level)
            st.rerun()

        with st.sidebar:
            st.header("⚙️ Session Controls")
            st.write("Welcome! Choose your level and start your practice interview.")
            st.caption("10 randomly selected authentic MEXT interview questions.")

        return

    # INTERVIEW IN PROGRESS (Displayed only after clicking Start Interview)
    level = st.session_state.active_level

    # Sidebar: Restart & Navigation Controls
    with st.sidebar:
        st.header("⚙️ Interview Controls")
        st.write(f"**Level:** {level}")
        st.write(f"**Progress:** Question {st.session_state.current_question_index + 1} of 10")
        if st.button("🔄 Restart Interview (New 10 Questions)", use_container_width=True):
            init_interview_session(level)
            st.rerun()
        if st.button("🏠 Exit to Welcome Screen", use_container_width=True):
            st.session_state.interview_started = False
            st.rerun()

    # Check current question
    current_idx = st.session_state.current_question_index
    total_q = len(st.session_state.selected_questions)

    # Progress Indicator
    st.caption(f"📌 **Question {current_idx + 1} of {total_q}**")
    st.progress((current_idx + 1) / total_q)

    # Step 2: Display Current Interview Question
    current_question = st.session_state.selected_questions[current_idx]
    st.subheader("Step 2: Interview Question")
    st.info(f"**Q{current_idx + 1}:** {current_question}")

    # Step 3: User's typed response
    st.subheader("Step 3: Type Your Answer")
    text_area_key = f"answer_input_{current_idx}"
    default_text = st.session_state.answers.get(current_idx, "")

    answer = st.text_area(
        label="Type your response below (take your time and express your thoughts):",
        value=default_text,
        placeholder="For example: I want to study AI in Japan because of their world-class robotics research...",
        height=180,
        key=text_area_key,
    )

    # Step 4: Feedback & Score Card
    st.subheader("Step 4: AI Evaluation & Score Card")
    api_key = get_api_key()

    if not api_key:
        st.warning(
            "⚠️ **Gemini API Key not detected!**\n\n"
            "- **Local run:** Add `GEMINI_API_KEY=your_key` in `.env` file.\n"
            "- **Streamlit Cloud:** Add `GEMINI_API_KEY` in Streamlit App Settings -> Secrets."
        )

    # Button: Get AI Feedback
    if st.button("🚀 Get AI Feedback", type="primary", use_container_width=True):
        if not answer.strip():
            st.warning("Please type your answer before requesting feedback.")
        elif not api_key:
            st.error("Cannot evaluate answer without an API key. Please configure GEMINI_API_KEY.")
        # Optimization: Prevent duplicate API calls if this exact answer was already evaluated
        elif (
            current_idx in st.session_state.feedbacks
            and st.session_state.answers.get(current_idx) == answer.strip()
        ):
            st.info("⚡ Feedback already loaded for this answer.")
        else:
            with st.spinner("⚡ Connecting to Gemini AI and analyzing your answer..."):
                feedback = evaluate_interview_answer(api_key, current_question, answer.strip())
                if feedback:
                    # Save answer and feedback into session state
                    st.session_state.answers[current_idx] = answer.strip()
                    st.session_state.feedbacks[current_idx] = feedback

    # Render Feedback if available for this question
    if current_idx in st.session_state.feedbacks:
        fb = st.session_state.feedbacks[current_idx]

        st.success("✅ Evaluation Complete!")

        # Performance metric caption (if timings are present)
        if "timings" in fb:
            t = fb["timings"]
            st.caption(
                f"⚡ Response time: **{t['total_s']:.2f}s** "
                f"(API: {t['api_s']:.2f}s, Parse: {t['parse_ms']:.1f}ms) "
                f"| Model: `{t['model']}`"
            )

        # 4. Score Card: 3 metric cards at top
        st.markdown("#### 📊 Score Card")
        col1, col2, col3 = st.columns(3)
        col1.metric("Grammar", f"{fb['grammar_score']}/10")
        col2.metric("Clarity", f"{fb['clarity_score']}/10")
        col3.metric("Content", f"{fb['content_score']}/10")

        # 5 Expandable Sections
        st.markdown("#### 📝 Detailed Feedback")
        with st.expander("📝 English Grammar & Vocabulary", expanded=True):
            st.write(fb["grammar_feedback"])

        with st.expander("🎯 Clarity of Answer", expanded=True):
            st.write(fb["clarity_feedback"])

        with st.expander("📌 Relevance to the Question", expanded=True):
            st.write(fb.get("relevance_feedback", "Evaluated based on relevance to the specific interview question."))

        with st.expander("🌟 What Was Good (Strengths)", expanded=True):
            st.write(fb["strengths"])

        with st.expander("🚀 What Can Improve", expanded=True):
            st.write(fb["improvements"])

        st.divider()

        # Step 5: Next Question or Session Completion
        if current_idx < total_q - 1:
            if st.button("➡️ Next Question", type="primary", use_container_width=True):
                st.session_state.current_question_index += 1
                st.rerun()
        else:
            st.balloons()
            st.success("🎉 **Congratulations! You have completed all 10 interview questions!**")
            st.write("You have practiced a full MEXT scholarship interview simulation.")
            if st.button("🔄 Start a New Interview Session", type="primary", use_container_width=True):
                init_interview_session(level)
                st.rerun()
            if st.button("🏠 Exit to Welcome Screen", use_container_width=True):
                st.session_state.interview_started = False
                st.rerun()

    st.divider()
    st.caption("🎓 MEXT Scholarship Interview Practice Bot | 10-Question Interactive Session")


if __name__ == "__main__":
    main()
