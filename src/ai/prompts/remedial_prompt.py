REMEDIAL_PROMPT = """
Generate a remedial learning plan.

Topic: {topic}
Student weaknesses: {weaknesses}
Session count: {session_count}

Context:
{context}

Output rules:
- Return ONLY valid JSON.
- Plan must include measurable steps.

{format_instructions}
"""
