SUMMARY_PROMPT = """
Generate a concise learning summary.

Topic: {topic}
Max words: {max_words}

Context:
{context}

Output rules:
- Return ONLY valid JSON.
- Keep it concise and student-friendly.
- key_points should be practical and specific.

{format_instructions}
"""
