# 🎓 MEXT Scholarship Interview Practice Bot

A simple, text-based Generative AI practice bot written in Python to help students prepare for MEXT scholarship interviews.

---

## 📌 Project Overview
Preparing for a scholarship interview can be challenging. This tool helps you:
1. Select your difficulty level (**Beginner** or **Experienced**).
2. Receive a realistic MEXT scholarship interview question.
3. Type and submit your answer directly in the terminal.
4. Receive AI-powered feedback from Google Gemini on:
   - **English Grammar & Vocabulary**
   - **Clarity of Thought**
   - **What was Good (Strengths)**
   - **What Can Improve (Actionable Advice)**

---

## 🚀 How to Run

### 1. Prerequisites
- Python 3.9+ installed on your computer.

### 2. Install Required Libraries
```bash
pip install -r requirements.txt
```

### 3. Set Up Your API Key
1. Create a file named `.env` in the root folder of this project.
2. Open `.env` and add your Google Gemini API key:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   ```
   *(You can get a free API key at [Google AI Studio](https://aistudio.google.com/)).*

### 4. Run the Bot
```bash
python main.py
```

---

## 🔒 Security Best Practices
- **API Keys are private**: Never hardcode API keys directly into Python files.
- We keep secrets in a `.env` file, which is listed in `.gitignore` so Git never uploads it to GitHub.
- A template `.env.example` is provided for reference.

---

## 📁 Project Structure
```
interview-practice-bot/
├── .env               # Your private API key (ignored by Git)
├── .env.example       # Template for API keys
├── .gitignore          # Tells Git to ignore sensitive files (.env)
├── requirements.txt    # Required Python libraries (google-generativeai, python-dotenv)
├── main.py             # Main Python script for interview practice and AI evaluation
└── README.md           # Project documentation
```

---

## 💡 How to Explain this in an Interview / Viva
1. **Separation of Secrets**: Explain how `.env` and `python-dotenv` keep credentials secure and prevent credential leaks on GitHub.
2. **Modular Functions**:
   - `choose_level()`: Handles user menu input and validation.
   - `get_question()`: Maps difficulty level to tailored questions.
   - `evaluate_interview_answer()`: Constructs a prompt with the question + answer and queries Google's Gemini LLM.
3. **Structured Prompting**: Explain how prompt engineering was used to ask the LLM for specific sections (Grammar, Clarity, Strengths, Improvements) rather than a generic text response.
