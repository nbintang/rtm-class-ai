QUIZ_PROMPT = """
Generate a quiz from the provided context.

Topic: {topic}
Grade level: {grade_level}
Requested number of questions: {num_questions}

Context:
{context}

Output rules:
- Return ONLY valid JSON.
- Each question must have unique options.
- correct_answer must match one option exactly.
- explanation must be non-empty.

{format_instructions}
"""
