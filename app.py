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
        return "Request Timeout (API connection timed out)"
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
    Highly tolerant parser for Gemini responses:
      1. Tries standard JSON parsing (with markdown strip & strict=False).
      2. Tries repaired JSON / regex field extraction with alias support.
      3. Tries Markdown heading & bullet extraction.
      4. If all structured parsing fails, cleanly falls back to raw text
         without ever raising an error.
    """
    import re

    raw = str(response_text).strip()
    if not raw:
        return {
            "grammar_score": 5,
            "clarity_score": 5,
            "content_score": 5,
            "grammar_feedback": "Unable to evaluate grammar from empty response.",
            "clarity_feedback": "Unable to evaluate clarity from empty response.",
            "relevance_feedback": "Unable to evaluate relevance from empty response.",
            "strengths": "No relevant strengths demonstrated in this response.",
            "improvements": "Please provide a more detailed interview answer.",
            "raw_text": "",
        }

    # 1. Clean markdown code fences if present
    cleaned = raw
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # 2. Attempt direct JSON parsing
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = cleaned[start : end + 1]
        try:
            data = json.loads(json_str, strict=False)
            if isinstance(data, dict):
                def get_score(keys, default=5):
                    for k in keys:
                        if k in data and data[k] is not None:
                            try:
                                return min(10, max(1, int(data[k])))
                            except Exception:
                                pass
                    return default

                def get_text(keys):
                    for k in keys:
                        if k in data and data[k]:
                            return clean_text_content(str(data[k]))
                    return ""

                g_score = get_score(["grammar_score", "grammar", "grammar_rating", "english_grammar"])
                c_score = get_score(["clarity_score", "clarity", "clarity_rating", "clarity_of_answer"])
                cnt_score = get_score(["content_score", "content", "content_rating", "relevance_score"])

                g_fb = get_text(["grammar_feedback", "grammar", "english_grammar", "grammar_notes"])
                c_fb = get_text(["clarity_feedback", "clarity", "clarity_notes", "organization"])
                r_fb = get_text(["relevance_feedback", "relevance", "relevance_to_question", "question_relevance"])
                s_fb = get_text(["strengths", "what_was_good", "positive", "strengths_feedback"])
                i_fb = get_text(["improvements", "what_can_improve", "areas_for_improvement", "suggestions"])

                if any([g_fb, c_fb, r_fb, s_fb, i_fb]):
                    return {
                        "grammar_score": g_score,
                        "clarity_score": c_score,
                        "content_score": cnt_score,
                        "grammar_feedback": g_fb or "Grammar & vocabulary evaluated.",
                        "clarity_feedback": c_fb or "Sentence clarity evaluated.",
                        "relevance_feedback": r_fb or "Relevance evaluated against question.",
                        "strengths": s_fb or "No relevant strengths demonstrated in this response.",
                        "improvements": i_fb or "Review question requirements and provide specific details.",
                        "raw_text": raw,
                    }
        except Exception as e:
            print(f"[Parser Debug] Direct JSON load failed: {e}")

    # 3. Regex field extraction with aliases (handles unescaped internal quotes and multi-line strings)
    def extract_field_tolerant(key_aliases, text):
        for key in key_aliases:
            pattern = rf'"{key}"\s*:\s*"(.*?)(?=",\s*"\w+"|\s*"\s*:\s*|\s*}}\s*$)'
            m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if m:
                val = m.group(1).replace(r"\"", '"').replace(r"\n", "\n")
                return clean_text_content(val.strip())
        return ""

    def extract_score_tolerant(key_aliases, text, default=5):
        for key in key_aliases:
            m = re.search(rf'"{key}"\s*:\s*(\d+)', text, re.IGNORECASE)
            if m:
                try:
                    return min(10, max(1, int(m.group(1))))
                except Exception:
                    pass
        return default

    g_fb = extract_field_tolerant(["grammar_feedback", "grammar", "english_grammar"], cleaned)
    c_fb = extract_field_tolerant(["clarity_feedback", "clarity", "organization"], cleaned)
    r_fb = extract_field_tolerant(["relevance_feedback", "relevance", "relevance_to_question"], cleaned)
    s_fb = extract_field_tolerant(["strengths", "what_was_good", "positive"], cleaned)
    i_fb = extract_field_tolerant(["improvements", "what_can_improve", "suggestions"], cleaned)

    if any([g_fb, c_fb, r_fb, s_fb, i_fb]):
        return {
            "grammar_score": extract_score_tolerant(["grammar_score", "grammar"], cleaned, default=6),
            "clarity_score": extract_score_tolerant(["clarity_score", "clarity"], cleaned, default=6),
            "content_score": extract_score_tolerant(["content_score", "content"], cleaned, default=5),
            "grammar_feedback": g_fb or "Grammar & vocabulary evaluated.",
            "clarity_feedback": c_fb or "Sentence clarity evaluated.",
            "relevance_feedback": r_fb or "Relevance evaluated against question.",
            "strengths": s_fb or "No relevant strengths demonstrated in this response.",
            "improvements": i_fb or "Review question requirements.",
            "raw_text": raw,
        }

    # 4. Markdown section parsing fallback (e.g. ### Grammar, ### Strengths, etc.)
    def extract_markdown_section(section_headers, text):
        for header in section_headers:
            pattern = rf"(?:###|\*\*|#)\s*{header}[^\n]*\n([\s\S]*?)(?=(?:###|\*\*|#)\s*\w+|$)"
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return clean_text_content(m.group(1).strip())
        return ""

    md_g = extract_markdown_section(["Grammar", "English Grammar", "Grammar & Vocabulary"], raw)
    md_c = extract_markdown_section(["Clarity", "Clarity of Answer"], raw)
    md_r = extract_markdown_section(["Relevance", "Relevance to Question"], raw)
    md_s = extract_markdown_section(["Strengths", "What Was Good", "Good"], raw)
    md_i = extract_markdown_section(["Improvements", "What Can Improve", "Suggestions"], raw)

    def find_score_in_text(category, default=6):
        m = re.search(rf"{category}[^\d]{{1,20}}(\d{{1,2}})(?:\s*(?:/|\s*out of\s*)\s*10)?", raw, re.IGNORECASE)
        if m:
            try:
                return min(10, max(1, int(m.group(1))))
            except Exception:
                pass
        return default

    if any([md_g, md_c, md_r, md_s, md_i]):
        return {
            "grammar_score": find_score_in_text("grammar", 6),
            "clarity_score": find_score_in_text("clarity", 6),
            "content_score": find_score_in_text("content", 5),
            "grammar_feedback": md_g or "Grammar evaluated.",
            "clarity_feedback": md_c or "Clarity evaluated.",
            "relevance_feedback": md_r or "Relevance evaluated.",
            "strengths": md_s or "No relevant strengths demonstrated in this response.",
            "improvements": md_i or "Review recommendations above.",
            "raw_text": raw,
        }

    # 5. SAFE FALLBACK (NEVER THROW ERROR): Show raw feedback text instead of failing
    print("[Parser Fallback] Structured extraction failed, using raw response fallback.")
    return {
        "grammar_score": find_score_in_text("grammar", 6),
        "clarity_score": find_score_in_text("clarity", 6),
        "content_score": find_score_in_text("content", 5),
        "grammar_feedback": "Please refer to the complete AI evaluation below.",
        "clarity_feedback": "Please refer to the complete AI evaluation below.",
        "relevance_feedback": "Please refer to the complete AI evaluation below.",
        "strengths": "See full assessment below.",
        "improvements": "See actionable suggestions below.",
        "raw_fallback_text": clean_text_content(raw),
        "raw_text": raw,
    }


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

        # Explicit RequestOptions with timeout=40.0 and retry=None to prevent indefinite cloud container hangs
        request_options = RequestOptions(timeout=40.0, retry=None)

        # Candidate models ordered by speed and stability:
        # 1. gemini-3.5-flash-lite: Ultra-low-latency model (1-2s response, no heavy thinking delays)
        # 2. gemini-3.8-flash: High-capability reasoning fallback
        candidate_models = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
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
                print(f"[Gemini API] Querying model={model_name} | transport=rest | timeout=40s")
                model = genai.GenerativeModel(model_name, generation_config=generation_config)
                response = model.generate_content(prompt, request_options=request_options)
                t_api_end = time.perf_counter()
                api_time_s = t_api_end - t_api_start
                print(f"[Gemini API] Success: model={model_name} | duration={api_time_s:.2f}s")

                raw_text = extract_response_text(response)
                print(f"[Gemini API Raw Response ({model_name})]:\n{raw_text}\n")

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
                else:
                    print(f"[Gemini API] Model {model_name} returned empty text.")
                    attempt_log.append(f"Model: {model_name} | Status: Empty Response Text | Duration: {api_time_s:.2f}s")
                    continue

            except Exception as e:
                t_err = time.perf_counter()
                attempt_duration = t_err - t_api_start
                safe_category = get_safe_error_category(e)
                print(f"[Gemini API] Failed: model={model_name} | category={safe_category} | duration={attempt_duration:.2f}s | error={e}")
                
                # Invalidate failed model from cache so it doesn't get retried first next time
                if "working_gemini_model" in st.session_state and st.session_state.working_gemini_model == model_name:
                    del st.session_state["working_gemini_model"]

                last_error_category = safe_category
                attempt_log.append(f"Model: {model_name} | Status: {safe_category} | Duration: {attempt_duration:.2f}s | Detail: {str(e)[:120]}")
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


def get_score_color(score: int) -> str:
    """
    Returns design rule color based on score:
      7 to 10 = teal (#14B8A6)
      4 to 6 = amber (#F59E0B)
      1 to 3 = soft red (#EF4444)
    """
    if score >= 7:
        return "#14B8A6"
    elif score >= 4:
        return "#F59E0B"
    else:
        return "#EF4444"


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

    # SECTION 2: INTERVIEW ROOM
    # Progress Indicator: small label "Question X of 10" with progress bar at top
    st.markdown(
        f'<div style="font-size: 0.9rem; font-weight: 600; color: #64748B; margin-bottom: 0.25rem;">Question {current_idx + 1} of {total_q}</div>',
        unsafe_allow_html=True,
    )
    st.progress((current_idx + 1) / total_q)

    # Current Interview Question inside one large, clean card
    current_question = st.session_state.selected_questions[current_idx]
    st.markdown(
        f"""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.5rem; margin-top: 1.25rem; margin-bottom: 1.5rem;">
            <div style="font-size: 1.2rem; font-weight: 600; color: #172554; line-height: 1.5;">{current_question}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Small label "Your answer" above the answer box
    st.markdown(
        '<div style="font-size: 0.95rem; font-weight: 600; color: #172554; margin-bottom: 0.4rem;">Your answer</div>',
        unsafe_allow_html=True,
    )
    text_area_key = f"answer_input_{current_idx}"
    default_text = st.session_state.answers.get(current_idx, "")

    answer = st.text_area(
        label="Your answer",
        value=default_text,
        placeholder="Type your answer here (take your time and express your thoughts)...",
        height=180,
        key=text_area_key,
        label_visibility="collapsed",
    )

    # API key detection check
    api_key = get_api_key()
    if not api_key:
        st.warning(
            "⚠️ **Gemini API Key not detected!**\n\n"
            "- **Local run:** Add `GEMINI_API_KEY=your_key` in `.env` file.\n"
            "- **Streamlit Cloud:** Add `GEMINI_API_KEY` in Streamlit App Settings -> Secrets."
        )

    # Button: Get Feedback (blue, full width)
    if st.button("Get Feedback", type="primary", use_container_width=True):
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

    # SECTION 3: AI SCORE CARDS & EVALUATION
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

        # Above scores: heading "Your Score" (no numbering)
        st.markdown("<h3 style='color: #172554; margin-top: 1.5rem; margin-bottom: 0.75rem;'>Your Score</h3>", unsafe_allow_html=True)

        # Grammar, Clarity and Content as 3 cards in a row (st.columns), colored by score
        col1, col2, col3 = st.columns(3)

        grammar_score = fb["grammar_score"]
        clarity_score = fb["clarity_score"]
        content_score = fb["content_score"]

        with col1:
            st.markdown(
                f"""
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.1rem; text-align: center; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.35rem;">Grammar</div>
                    <div style="font-size: 2.25rem; font-weight: 700; color: {get_score_color(grammar_score)}; line-height: 1;">{grammar_score}<span style="font-size: 1.1rem; font-weight: 500; color: #94A3B8;">/10</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                f"""
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.1rem; text-align: center; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.35rem;">Clarity</div>
                    <div style="font-size: 2.25rem; font-weight: 700; color: {get_score_color(clarity_score)}; line-height: 1;">{clarity_score}<span style="font-size: 1.1rem; font-weight: 500; color: #94A3B8;">/10</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col3:
            st.markdown(
                f"""
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.1rem; text-align: center; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.35rem;">Content</div>
                    <div style="font-size: 2.25rem; font-weight: 700; color: {get_score_color(content_score)}; line-height: 1;">{content_score}<span style="font-size: 1.1rem; font-weight: 500; color: #94A3B8;">/10</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Under the cards: one short "Overall" line with average score and one-sentence summary
        avg_score = round((grammar_score + clarity_score + content_score) / 3.0, 1)
        if avg_score >= 7.0:
            summary_text = "Strong response demonstrating solid interview readiness and clear motivation."
            overall_color = "#14B8A6"
        elif avg_score >= 4.0:
            summary_text = "Fair response with good fundamentals, but needs more depth and specificity."
            overall_color = "#F59E0B"
        else:
            summary_text = "Needs significant improvement in substance and relevance to meet MEXT standards."
            overall_color = "#EF4444"

        st.markdown(
            f"""
            <div style="background-color: #F8FAFC; border-left: 4px solid {overall_color}; border-radius: 4px; padding: 0.75rem 1rem; margin-top: 0.75rem; margin-bottom: 1.5rem;">
                <span style="font-weight: 700; color: #172554;">Overall: {avg_score}/10</span> — <span style="color: #475569;">{summary_text}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Detailed Feedback heading without numbering
        st.markdown("<h3 style='color: #172554; margin-top: 1.5rem; margin-bottom: 0.75rem;'>Detailed Feedback</h3>", unsafe_allow_html=True)
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

        # If parser fallback occurred, display complete evaluator notes
        if "raw_fallback_text" in fb and fb["raw_fallback_text"]:
            with st.expander("📄 Complete Evaluator Output", expanded=False):
                st.write(fb["raw_fallback_text"])

        st.divider()

        # Next Question navigation or Session Completion
        if current_idx < total_q - 1:
            if st.button("Next Question", type="primary", use_container_width=True):
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
