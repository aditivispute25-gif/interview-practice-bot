# 🎓 MEXT Scholarship Interview Practice Bot

A Generative AI practice web app and CLI tool written in Python to help students prepare for MEXT scholarship interviews.

---

## 🌐 Live Demo
Try the live web application on Streamlit Community Cloud:
👉 **[Launch Live Demo](https://interview-practice-botgit-jywabghjc6uutkqdvt375u.streamlit.app/)**

---

## 📌 Project Overview
Preparing for a scholarship interview can be challenging. This tool helps you:
1. Select your difficulty level (**Beginner** or **Experienced**).
2. Practice a **10-question interview simulation**, picked randomly without repeats from a dedicated question bank (`questions.py`).
3. Track your progress with a dynamic question counter (e.g., **"Question 3 of 10"**).
4. Type and submit your answer directly in the text area for each question.
5. Receive **Score Cards** (scores out of 10 for Grammar, Clarity, and Content) using `st.columns` and `st.metric`.
6. Review clean, structured feedback organized in collapsible expanders (`st.expander`):
   - **English Grammar & Vocabulary**
   - **Clarity of Thought**
   - **What was Good (Strengths)**
   - **What Can Improve (Actionable Advice)**
7. Progress seamlessly through the 10 questions using the **"Next Question"** flow.

---

## 🚀 How to Run the Streamlit Web App

### 1. Prerequisites
- Python 3.9+ installed on your computer.

### 2. Install Required Libraries
```bash
pip install -r requirements.txt
```

### 3. Configure Your Gemini API Key
You can configure your API key in either of two ways:

#### Option A: Local Development (via `.env`)
Create a file named `.env` in the root folder of this project:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```
*(Get a free API key at [Google AI Studio](https://aistudio.google.com/)).*

#### Option B: Streamlit Cloud Deployment (via `st.secrets`)
If deploying to [Streamlit Community Cloud](https://share.streamlit.io):
1. Go to your App Settings -> **Secrets**.
2. Add:
   ```toml
   GEMINI_API_KEY = "your_actual_gemini_api_key_here"
   ```

### 4. Launch the Web App
Run the following command in your terminal:
```bash
streamlit run app.py
```
This will open the web app automatically in your default browser at `http://localhost:8501`.

---

## 🖥️ Terminal Version (CLI)
You can still run the original command-line version anytime:
```bash
python main.py
```

---

## 🔒 Security Best Practices
- **API Keys are private**: Never hardcode API keys directly into Python files.
- We keep secrets in `.env` (or Streamlit Secrets), which is listed in `.gitignore` so Git never uploads it to GitHub.
- A template `.env.example` is provided for reference.

---

## 📁 Project Structure
```
interview-practice-bot/
├── .env.example       # Template for API keys
├── .gitignore          # Tells Git to ignore sensitive files (.env)
├── requirements.txt    # Required Python libraries (streamlit, google-generativeai, python-dotenv)
├── questions.py        # Question bank (10+ Beginner and 10+ Experienced MEXT questions)
├── app.py              # Streamlit Web Application (10-question flow, score cards, clean feedback)
├── main.py             # Streamlit Cloud entry point
└── README.md           # Project documentation
```

---

## 💡 How to Explain this in an Interview / Viva
1. **Separation of Concerns**:
   - `questions.py`: Decouples the question data from UI logic, making it easy to add or edit questions without touching application code.
2. **State Management (`st.session_state`)**:
   - Persists the 10 selected questions, user answers, and generated feedback across Streamlit reruns.
3. **Structured Prompting & Score Cards**:
   - Instructs Google Gemini to return structured scores and evaluations.
   - `st.columns` and `st.metric` display the score cards cleanly at a glance.
   - `st.expander` organizes the detailed feedback sections so the page is easy to read.
4. **Clean Output Filtering**:
   - Filters out any internal AI reasoning/preambles (Role, Target, Constraint, Plan) before rendering to the user.
