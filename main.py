"""
MEXT Scholarship Interview Practice Bot - Part 1
A simple, beginner-friendly command-line bot built with Python.
"""

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

def main():
    """
    Main function to run the interactive interview flow.
    """
    # 1. Ask the user to choose a level
    level = choose_level()
    print(f"\nYou selected: {level.capitalize()} Level\n")

    # 2. Display the MEXT interview question
    question = get_question(level)
    print("=" * 60)
    print("YOUR INTERVIEW QUESTION:")
    print(question)
    print("=" * 60)

    # 3. Take the user's typed answer
    print("\nType your answer below (take your time, then press Enter):")
    answer = input("\nYour Answer: ").strip()

    if not answer:
        print("\nNo answer was entered. Please run the script again and type an answer.")
        return

    # 4. Confirmation
    print("\n" + "=" * 60)
    print("Answer recorded successfully!")
    print("=" * 60)
    print(f"\n[Preview of Recorded Answer]:\n\"{answer}\"")
    print("\nNext Step (Step 2): We will connect this to the Gemini AI API")
    print("to analyze your answer for grammar, clarity, strengths, and improvements!")

if __name__ == "__main__":
    main()
