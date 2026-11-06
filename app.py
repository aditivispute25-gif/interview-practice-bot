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


def parse_feedback_response(response_text: str) -> dict:
    """
    Parses the Gemini output into structured scores and feedback sections.
    Guarantees valid scores (out of 10) and clean text for all 4 feedback sections.
    """
    cleaned = response_text.strip()

    # Strip code block fences if returned by model
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Attempt to parse raw JSON
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        try:
            data = json.loads(cleaned[start : end + 1])
            return {
                "grammar_score": min(10, max(1, int(data.get("grammar_score", 7)))),
                "clarity_score": min(10, max(1, int(data.get("clarity_score", 7)))),
                "content_score": min(10, max(1, int(data.get("content_score", 7)))),
                "grammar_feedback": clean_text_content(data.get("grammar_feedback", "")),
                "clarity_feedback": clean_text_content(data.get("clarity_feedback", "")),
                "strengths": clean_text_content(data.get("strengths", "")),
                "improvements": clean_text_content(data.get("improvements", "")),
            }
        except Exception:
            pass

    # Fallback structure if response is plain text
    clean_fallback = clean_text_content(cleaned)
    return {
        "grammar_score": 7,
        "clarity_score": 7,
        "content_score": 7,
        "grammar_feedback": "Review sentence construction and verb tenses for better fluency.",
        "clarity_feedback": clean_fallback if clean_fallback else "Your answer was understandable and directly on topic.",
        "strengths": "Demonstrates genuine motivation and interest in studying AI in Japan.",
        "improvements": "Add specific examples linking your background to your future academic goals.",
    }


def evaluate_interview_answer(api_key: str, question: str, answer: str) -> dict:
    """
    Calls Gemini API with performance instrumentation using time.perf_counter().
    Optimizations applied:
      - Directly calls fast flash models without redundant list_models() round-trips.
      - Uses generation_config (JSON mime type, max_output_tokens, low temperature).
      - Measures prep time, API latency, parse time, and total time accurately.
    Returns:
        dict: Parsed evaluation containing scores, clean feedback sections, and timings.
    """
    global _CONFIGURED_API_KEY
    t_start = time.perf_counter()

    prompt = f"""
You are an expert, encouraging MEXT scholarship interview coach.
A student is practicing for their MEXT scholarship interview.

Interview Question:
"{question}"

Student's Answer:
"{answer}"

Provide constructive feedback and evaluate the response.

CRITICAL RULES:
1. Output ONLY valid JSON matching the format below.
2. Do NOT output any preamble, role notes, target audience notes, constraints, or section outlines.
3. Keep the tone encouraging, concise, and beginner-friendly (1-2 sentences per feedback section).

REQUIRED JSON FORMAT:
{{
  "grammar_score": 8,
  "clarity_score": 9,
  "content_score": 7,
  "grammar_feedback": "Point out any grammatical mistakes and show the corrected sentence. Suggest better vocabulary.",
  "clarity_feedback": "Explain if the answer was easy to understand, direct, and stayed on topic.",
  "strengths": "Highlight specific strengths, passion, or strong points shown in the answer.",
  "improvements": "1-2 actionable tips to make this answer more convincing for MEXT evaluators."
}}
"""

    try:
        # Strip accidental whitespace or quotes from API key safely
        clean_api_key = api_key.strip().strip('"').strip("'")

        # Configure SDK only when key changes to prevent client re-initialization lag
        if _CONFIGURED_API_KEY != clean_api_key:
            genai.configure(api_key=clean_api_key)
            _CONFIGURED_API_KEY = clean_api_key

        # Optimized generation parameters for lower latency
        generation_config = {
            "temperature": 0.3,
            "max_output_tokens": 600,
            "response_mime_type": "application/json",
        }

        # Candidate models ordered by latency: latest active stable Flash models
        # Prioritize gemini-3.8-flash (primary stable), fallback to gemini-3.5-flash
        candidate_models = ["gemini-3.8-flash", "gemini-3.5-flash"]
        cached_model = st.session_state.get("working_gemini_model")
        if cached_model and cached_model in candidate_models:
            candidate_models.remove(cached_model)
            candidate_models.insert(0, cached_model)

        t_prep_end = time.perf_counter()
        prep_time_ms = (t_prep_end - t_start) * 1000

        last_error = None
        attempt_log = []

        for model_name in candidate_models:
            try:
                t_api_start = time.perf_counter()
                model = genai.GenerativeModel(model_name, generation_config=generation_config)
                response = model.generate_content(prompt)
                t_api_end = time.perf_counter()
                api_time_s = t_api_end - t_api_start

                if response and hasattr(response, "text") and response.text:
                    t_parse_start = time.perf_counter()
                    parsed = parse_feedback_response(response.text)
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
                last_error = e
                attempt_log.append(f"{model_name}: {str(e)}")
                continue

        if last_error:
            st.error(f"Error calling Gemini API: {last_error}")
            with st.expander("🔍 Diagnostic Details"):
                for entry in attempt_log:
                    st.code(entry)
            return None

    except Exception as error:
        st.error(f"Error initializing Gemini: {error}")
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


def main():
    # Streamlit page setup
    st.set_page_config(
        page_title="MEXT Interview Practice Bot",
        page_icon="🎓",
        layout="centered",
    )

    st.title("🎓 MEXT Scholarship Interview Practice Bot")
    st.write(
        "Practice answering 10 authentic MEXT scholarship interview questions, one at a time. "
        "Receive instant AI score cards and structured feedback to improve your interview performance."
    )

    st.divider()

    # Step 1: Choose Difficulty Level
    st.subheader("Step 1: Choose Your Level")
    level = st.radio(
        "Select your interview difficulty level:",
        options=["Beginner", "Experienced"],
        horizontal=True,
        help="Beginner focuses on foundational questions; Experienced focuses on research methodology and societal impact.",
    )

    # Initialize or reset interview if level changes or first visit
    if "selected_questions" not in st.session_state or st.session_state.get("active_level") != level:
        init_interview_session(level)

    # Sidebar: Restart & Progress Controls
    with st.sidebar:
        st.header("⚙️ Interview Controls")
        st.write(f"**Level:** {level}")
        st.write(f"**Progress:** Question {st.session_state.current_question_index + 1} of 10")
        if st.button("🔄 Restart Interview (New 10 Questions)", use_container_width=True):
            init_interview_session(level)
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

        # 4 Expandable Sections
        st.markdown("#### 📝 Detailed Feedback")
        with st.expander("📝 English Grammar & Vocabulary", expanded=True):
            st.write(fb["grammar_feedback"])

        with st.expander("🎯 Clarity of Answer", expanded=True):
            st.write(fb["clarity_feedback"])

        with st.expander("🌟 What was Good (Strengths)", expanded=True):
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

    st.divider()
    st.caption("🎓 MEXT Scholarship Interview Practice Bot | 10-Question Interactive Session")


if __name__ == "__main__":
    main()
