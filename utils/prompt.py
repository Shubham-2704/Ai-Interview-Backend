def question_answer_prompt(role, experience, topics_to_focus, number_of_questions):
    return f"""
You are an AI trained to generate technical interview questions and answers.

Task:
- Role: {role}
- Candidate Experience: {experience} years
- Focus Topics: {topics_to_focus}
- Write {number_of_questions} interview questions.
- For each question, generate a detailed but beginner-friendly answer.
- If the answer needs a code example, ALWAYS wrap it in markdown code blocks with language.
- Keep formatting very clean.

Return a pure JSON array like:
[
    {{
        "question": "Question here?",
        "answer": "Answer here.\\n\\n```js\\ncode here\\n```"
    }}
]

Important: Do NOT add any extra text. Only return valid JSON.
"""

def concept_explain_prompt(question):
    return f"""
You are an AI trained to generate explanations for interview questions.

Task:
- Explain the following interview question in depth for a beginner.
- Question: "{question}"
- Provide a short and clear title.
- If the explanation includes a code example, ALWAYS use markdown code blocks with language.

Return a valid JSON object like:
{{
    "title": "Short title here?",
    "explanation": "Explanation here.\\n\\n```js\\ncode here\\n```"
}}

Important: Do NOT add any extra text outside the JSON.
"""
