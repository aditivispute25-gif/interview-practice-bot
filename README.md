# 🎓 MEXT Scholarship Interview Practice Bot

A simple, text-based Generative AI practice bot written in Python to help students prepare for MEXT scholarship interviews.

---

## 📌 Project Overview
Preparing for a scholarship interview can be challenging. This tool helps you:
1. Select your difficulty level (**Beginner** or **Experienced**).
2. Receive a realistic MEXT scholarship interview question.
3. Type and submit your answer directly in the terminal.
4. Receive AI-powered feedback on:
   - **English Grammar & Vocabulary**
   - **Clarity of Thought**
   - **What was Good (Strengths)**
   - **What Can Improve (Actionable Advice)**

---

## 🚀 How to Run (Step 1)

### 1. Prerequisites
- Python 3.9+ installed on your computer.

### 2. Install Required Libraries
```bash
pip install -r requirements.txt
```

### 3. Run the Bot
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
├── .env.example       # Template for API keys
├── .gitignore          # Tells Git to ignore sensitive files (.env)
├── requirements.txt    # Required Python libraries
├── main.py             # Main Python script for interview practice
└── README.md           # Project documentation
```
