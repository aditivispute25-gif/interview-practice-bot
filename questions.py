"""
MEXT Scholarship Interview Question Bank
Contains categorized interview questions for Beginner and Experienced levels.
"""

# At least 10 MEXT-style interview questions for Beginner
BEGINNER_QUESTIONS = [
    "Why do you want to study in Japan instead of your home country or other English-speaking nations?",
    "What sparked your passion for Artificial Intelligence, and why is Japan the right place to study it?",
    "What specific field or topic within AI do you wish to focus on during your undergraduate/scholarship studies?",
    "Which Japanese university or professor's research are you most interested in, and why?",
    "What are your short-term academic goals during your first year under the MEXT scholarship?",
    "How will your studies in Japan help you achieve your future career goals?",
    "Living and studying in Japan requires adapting to a new culture. How do you plan to handle culture shock and language barriers?",
    "Tell us about a challenging academic or personal project you worked on and how you solved it.",
    "Why did you choose the MEXT scholarship over scholarships from other countries?",
    "How will you contribute to building friendly relations between Japan and your home country?",
    "Japan envisions a smart, human-centered society called 'Society 5.0'. How can your AI knowledge contribute to this vision?",
    "MEXT scholarship students must study independently. How do you stay motivated when facing difficult learning curves?",
]

# At least 10 MEXT-style interview questions for Experienced
EXPERIENCED_QUESTIONS = [
    "How will your proposed research in AI in Japan contribute to society, and what are your long-term career goals after graduation?",
    "Explain your specific research methodology in AI and why Japanese university laboratories provide the ideal infrastructure for it.",
    "How does your proposed AI research address ethical considerations such as bias, transparency, data privacy, and accountability?",
    "If your experimental results contradict your primary research hypothesis, what systematic process will you follow to pivot?",
    "Japan faces urgent societal challenges like an aging demographic and disaster risks. How can your AI research address these issues?",
    "Which recent research publications or Japanese laboratory papers have most significantly influenced your proposed thesis topic?",
    "How will your research bridge the gap between theoretical machine learning models and real-world deployment in industry or public infrastructure?",
    "As a MEXT scholar, how will you act as a cultural and scientific ambassador between Japan and your home country after your studies?",
    "Describe a complex technical project where you led or collaborated with a team. How did you navigate architectural disagreements?",
    "Where do you envision your professional and research contributions five years after completing your MEXT scholarship?",
    "Artificial Intelligence often intersects with robotics, healthcare, or agriculture. How does your research leverage cross-disciplinary insights?",
    "Graduate research under scholarship conditions can be demanding. What strategies and mental models do you use to maintain consistent research productivity?",
]


def get_questions_for_level(level: str):
    """
    Returns the list of MEXT interview questions based on the difficulty level.
    Args:
        level (str): 'Beginner' or 'Experienced'
    Returns:
        list: 12 authentic MEXT interview questions
    """
    if level == "Experienced":
        return EXPERIENCED_QUESTIONS
    return BEGINNER_QUESTIONS
