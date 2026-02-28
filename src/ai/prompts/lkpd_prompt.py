LKPD_PROMPT = """
Generate LKPD (worksheet) content.

Topic: {topic}
Learning objective: {learning_objective}
Activity count: {activity_count}

Context:
{context}

Output rules:
- Return ONLY valid JSON.
- Activities should be actionable and measurable.

{format_instructions}
"""
