"""
MEXT Scholarship Interview Practice Bot - Part 1
A simple, beginner-friendly command-line bot built with Python.

This script:
1. Asks the user to choose their difficulty level (Beginner / Experienced).
2. Presents a relevant MEXT scholarship interview question.
3. Takes the user's typed response.
4. Uses Google's Gemini API to analyze:
   - English grammar & vocabulary
   - Clarity of the answer
   - What was good (strengths)
   - What can improve (actionable advice)
"""

import os
import warnings

# Suppress library deprecation warnings for a clean user console
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from the local .env file
load_dotenv()


def choose_level():
    """
    Step 1: Ask the user to choose their interview difficulty level.
    Returns:
        str: 'beginner' or 'experienced'
    """
    print("=" * 60)
    print(" Welcome to MEXT Scholarship Interview Practice Bot! ")
    print("=" * 60)
    print("\nPlease choose your interview level:")
    print("  [1] Beginner    (Simple, direct question)")
    print("  [2] Experienced (In-depth question requiring detailed explanation)")

    while True:
        choice = input("\nEnter your choice (1 or 2): ").strip()
        if choice == "1":
            return "beginner"
        elif choice == "2":
            return "experienced"
        else:
            print("Invalid choice. Please enter 1 for Beginner or 2 for Experienced.")


def get_question(level):
    """
    Step 2: Return a MEXT scholarship interview question based on the selected level.
    Args:
        level (str): 'beginner' or 'experienced'
    Returns:
        str: Interview question
    """
    if level == "beginner":
        return "Why do you want to study AI in Japan instead of your home country?"
    else:
        return "How will your proposed research in AI in Japan contribute to society, and what are your long-term career goals after graduation?"


def evaluate_interview_answer(question, answer):
    """
    Step 4: Send the question + answer to Gemini AI and print structured feedback.
    Args:
        question (str): The interview question asked
        answer (str): The student's typed response
    """
    # Read the secret API key from environment variables
    api_key = os.getenv("GEMINI_API_KEY")

    # Safety check: ensure user created the .env file with a valid key
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n" + "=" * 60)
        print("NOTICE: GEMINI_API_KEY is not configured yet!")
        print("=" * 60)
        print("To enable AI feedback:")
        print("1. Create a file named '.env' in this folder.")
        print("2. Add this line inside it:")
        print("   GEMINI_API_KEY=your_actual_api_key")
        print("3. You can get a free key from Google AI Studio: https://aistudio.google.com/")
        print("=" * 60)
        return

    # Prepare the prompt for the AI model
    prompt = f"""
You are an expert, encouraging MEXT scholarship interview coach.
A student is practicing for their scholarship interview.

Interview Question:
"{question}"

Student's Answer:
"{answer}"

Please provide constructive, clear, and beginner-friendly feedback divided strictly into the following 4 sections:

1. English Grammar & Vocabulary:
- Point out any grammatical mistakes and show the corrected sentence.
- Suggest better vocabulary or phrasing if appropriate.

2. Clarity of Answer:
- Was the answer easy to understand and directly addressing the question?
- Did it stay on topic?

3. What was Good (Strengths):
- Highlight specific ideas, motivation, or passion demonstrated in the student's answer.

4. What Can Improve:
- Provide 1-2 actionable tips to make this answer stronger and more convincing for scholarship evaluators.

Keep your tone positive, encouraging, and concise. Avoid overly complex jargon.
"""

    print("\n" + "=" * 60)
    print("Connecting to AI model and analyzing your answer...")
    print("=" * 60)

    try:
        # Configure Gemini with the user's API key
        genai.configure(api_key=api_key)

        # Initialize the model (gemini-1.5-flash is fast and cost-effective)
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
        except Exception:
            # Fallback to gemini-2.5-flash if gemini-1.5-flash isn't available
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)

        # Display the AI feedback
        print("\n" + "=" * 60)
        print("AI INTERVIEW FEEDBACK:")
        print("=" * 60)
        print(response.text)
        print("=" * 60)

    except Exception as error:
        print("\n" + "=" * 60)
        print("Error connecting to Gemini API:")
        print(f"{error}")
        print("=" * 60)
        print("Troubleshooting tips:")
        print("- Verify that your GEMINI_API_KEY in .env is correct.")
        print("- Ensure your computer is connected to the internet.")


def main():
    """
    Main function to run the interactive interview flow.
    """
    # 1. Ask user to choose a difficulty level
    level = choose_level()
    print(f"\nYou selected: {level.capitalize()} Level\n")

    # 2. Retrieve and display the MEXT interview question
    question = get_question(level)
    print("=" * 60)
    print("YOUR INTERVIEW QUESTION:")
    print(question)
    print("=" * 60)

    # 3. Take user's typed response
    print("\nType your answer below (take your time, then press Enter):")
    answer = input("\nYour Answer: ").strip()

    if not answer:
        print("\nNo answer was entered. Please run the script again and type an answer.")
        return

    print("\n" + "=" * 60)
    print("Answer recorded successfully!")
    print("=" * 60)

    # 4. Send question + answer to AI model for feedback
    evaluate_interview_answer(question, answer)


if __name__ == "__main__":
    main()
