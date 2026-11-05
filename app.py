"""
MEXT Scholarship Interview Practice Bot - Streamlit Web App
A beginner-friendly web application built with Streamlit and Google Gemini.
"""

import os
import warnings
import streamlit as st
from dotenv import load_dotenv

# Suppress deprecation warnings for a clean interface
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai

# Load local environment variables from .env file
load_dotenv()


def get_api_key():
    """
    Retrieve the Gemini API key.
    Checks:
      1. Streamlit Secrets (st.secrets) - used when deploying on Streamlit Community Cloud.
      2. Environment variables (.env file via load_dotenv) - used for local development.
    Returns:
        str or None: The API key if found, otherwise None.
    """
    # 1. Check Streamlit secrets (useful for Cloud deployment)
    try:
        if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    # 2. Check local environment variables (.env file)
    env_key = os.getenv("GEMINI_API_KEY")
    if env_key and env_key != "your_gemini_api_key_here":
        return env_key

    return None


def get_question(level):
    """
    Return a MEXT scholarship interview question based on the selected level.
    """
    if level == "Beginner":
        return "Why do you want to study AI in Japan instead of your home country?"
    else:
        return (
            "How will your proposed research in AI in Japan contribute to society, "
            "and what are your long-term career goals after graduation?"
        )


def evaluate_interview_answer(api_key, question, answer):
    """
    Send question and answer to Gemini AI and return formatted feedback.
    """
    prompt = f"""
You are an expert, encouraging MEXT scholarship interview coach.
A student is practicing for their scholarship interview.

Interview Question:
"{question}"

Student's Answer:
"{answer}"

Please provide constructive, clear, and beginner-friendly feedback divided strictly into the following 4 sections:

### 1. English Grammar & Vocabulary
- Point out any grammatical mistakes and show the corrected sentence.
- Suggest better vocabulary or phrasing if appropriate.

### 2. Clarity of Answer
- Was the answer easy to understand and directly addressing the question?
- Did it stay on topic?

### 3. What was Good (Strengths)
- Highlight specific ideas, motivation, or passion demonstrated in the student's answer.

### 4. What Can Improve
- Provide 1-2 actionable tips to make this answer stronger and more convincing for scholarship evaluators.

Keep your tone positive, encouraging, and concise. Avoid overly complex jargon.
"""

    try:
        # Strip any accidental whitespace from the API key
        clean_api_key = api_key.strip().strip('"').strip("'")
        genai.configure(api_key=clean_api_key)

        # 1. Discover models directly from Google for this specific API key
        discovered_models = []
        try:
            for m in genai.list_models():
                if "generateContent" in getattr(m, "supported_generation_methods", []):
                    name = m.name.replace("models/", "")
                    discovered_models.append(name)
        except Exception:
            pass

        # Preferred models in priority order
        preferred_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]

        # Place preferred models that exist at the front of the list
        ordered_models = [m for m in preferred_models if m in discovered_models]
        # Append any remaining discovered models
        for m in discovered_models:
            if m not in ordered_models:
                ordered_models.append(m)

        # Fallback to standard list if discovery was not permitted
        if not ordered_models:
            ordered_models = preferred_models

        last_error = None
        attempt_log = []

        for model_name in ordered_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response and hasattr(response, "text") and response.text:
                    return response.text
            except Exception as e:
                last_error = e
                attempt_log.append(f"{model_name}: {str(e)}")
                continue

        if last_error:
            st.error(f"Error calling Gemini API: {last_error}")
            with st.expander("🔍 Diagnostic Details"):
                st.write("**Models attempted:**")
                for log_entry in attempt_log:
                    st.code(log_entry)
                st.info(
                    "💡 **Quick fixes:**\n"
                    "1. Double check your API key in **Streamlit App Settings -> Secrets**.\n"
                    "   Make sure it looks like `GEMINI_API_KEY = \"AIzaSy...\"`.\n"
                    "2. If needed, create a fresh free key at [Google AI Studio](https://aistudio.google.com/)."
                )
            return None

    except Exception as error:
        st.error(f"Error initializing Gemini: {error}")
        return None


def main():
    # Page setup
    st.set_page_config(
        page_title="MEXT Interview Practice Bot",
        page_icon="🎓",
        layout="centered",
    )

    st.title("🎓 MEXT Scholarship Interview Practice Bot")
    st.write(
        "Practice answering MEXT scholarship interview questions and receive instant AI feedback "
        "on grammar, clarity, strengths, and areas to improve."
    )

    st.divider()

    # Step 1: Difficulty level selection using st.radio
    st.subheader("Step 1: Choose Your Level")
    level = st.radio(
        "Select your interview difficulty level:",
        options=["Beginner", "Experienced"],
        horizontal=True,
        help="Beginner gives a direct question; Experienced gives an in-depth research/career question.",
    )

    # Step 2: Show question based on selected level
    st.subheader("Step 2: Your Interview Question")
    question = get_question(level)
    st.info(f"**Question:** {question}")

    # Step 3: Text area for user's answer
    st.subheader("Step 3: Type Your Answer")
    answer = st.text_area(
        label="Type your response below (take your time and express your thoughts):",
        placeholder="For example: I want to study AI in Japan because of their world-class robotics research...",
        height=180,
    )

    # Step 4: Button to trigger AI evaluation
    st.subheader("Step 4: Get Feedback")
    api_key = get_api_key()

    # Inform user if API key is missing
    if not api_key:
        st.warning(
            "⚠️ **Gemini API Key not detected!**\n\n"
            "- **Local run:** Add `GEMINI_API_KEY=your_key` in a `.env` file.\n"
            "- **Streamlit Cloud:** Add `GEMINI_API_KEY` in Streamlit App Settings -> Secrets."
        )

    if st.button("🚀 Get AI Feedback", type="primary", use_container_width=True):
        if not answer.strip():
            st.warning("Please type your answer before clicking 'Get AI Feedback'.")
        elif not api_key:
            st.error("Cannot generate feedback without an API key. Please configure GEMINI_API_KEY.")
        else:
            with st.spinner("Connecting to Gemini AI and analyzing your answer..."):
                feedback = evaluate_interview_answer(api_key, question, answer)
                if feedback:
                    st.success("Analysis complete!")
                    st.markdown("### 📋 Evaluation Report")
                    st.markdown(feedback)

    st.divider()
    st.caption("🚀 Build: Dynamic Model Resolver v1.2 | MEXT Interview Practice Bot")


if __name__ == "__main__":
    main()
