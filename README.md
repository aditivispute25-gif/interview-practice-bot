# 🎓 MEXT Scholarship Interview Practice Bot

A Generative AI practice web app and CLI tool written in Python to help students prepare for MEXT scholarship interviews.

---

## 🌐 Live Demo
Try the live web application on Streamlit Community Cloud:
👉 **[Launch Live Demo](https://interview-practice-botgit-jywabghjc6uutkqdvt375u.streamlit.app/)**

---

## 📌 Project Overview
Preparing for a scholarship interview can be challenging. This tool helps you:
1. Select your difficulty level (**Beginner** or **Experienced**) using an interactive radio selector.
2. Receive a realistic MEXT scholarship interview question.
3. Type and submit your answer directly in a text area.
4. Receive AI-powered feedback from Google Gemini on:
   - **English Grammar & Vocabulary**
   - **Clarity of Thought**
   - **What was Good (Strengths)**
   - **What Can Improve (Actionable Advice)**

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
├── app.py              # Streamlit Web Application
├── main.py             # Terminal / CLI version
└── README.md           # Project documentation
```

---

## 💡 How to Explain this in an Interview / Viva
1. **Frontend with Streamlit**:
   - `st.radio`: Multi-choice toggle for interview difficulty levels.
   - `st.text_area`: Multi-line text input for user answers.
   - `st.button`: Triggers the analysis and displays progress with `st.spinner`.
2. **Dual-Source Secret Management**:
   - `get_api_key()` checks `st.secrets` first (for cloud hosting), then falls back to `os.getenv` via `python-dotenv` (for local development).
3. **Structured AI Prompting**:
   - Directs Google Gemini (`gemini-1.5-flash`) to return 4 structured sections (Grammar, Clarity, Strengths, Improvements) rather than unstructured text.
