import json
from typing import Any, Dict

def question_answer_prompt(role, experience, topics_to_focus, number_of_questions):
    return f"""
You are an AI trained to generate technical interview questions and answers.

CRITICAL JSON RULES (MUST FOLLOW):
- Output MUST be valid JSON that can be parsed by `json.loads`
- Do NOT include markdown fences like ```json or ```
- Do NOT include comments
- Do NOT include trailing commas
- Use ONLY double quotes for strings
- Escape all newlines as \\n
- Escape all quotes inside strings as \\"
- Do NOT add any text before or after the JSON
- Validate the JSON before responding

Task:
- Role: {role}
- Candidate Experience: {experience} years
- Focus Topics: {topics_to_focus}
- Write {number_of_questions} interview questions.
- For each question, generate a detailed answer tailored to a candidate with {experience} years of experience.
- Adjust depth, terminology, and examples according to the experience level.
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

def concept_explain_prompt(question, experience):
    return f"""
You are an AI trained to generate explanations for interview questions.

CRITICAL JSON RULES (MUST FOLLOW):
- Output MUST be valid JSON
- No markdown fences
- No comments
- No trailing commas
- Use only double quotes
- Escape newlines as \\n
- Escape quotes as \\"
- Do NOT add any text outside the JSON
- Validate JSON before responding

Task:
- Explain the following interview question in depth for a candidate with {experience} years of experience.
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
def followup_chat_prompt(context, question):
    # Different responses each time
    dynamic_responses = [
        "I need to stay within the explanation provided, which doesn't cover that topic.",
        "That concept isn't included in the explanation above.",
        "The explanation doesn't address that particular point.",
        "For this session, I'm limited to discussing what's in the explanation.",
        "That's outside what's covered in the explanation provided."
    ]
    
    # Simple selection based on question
    response_index = len(question) % len(dynamic_responses)
    dynamic_response = dynamic_responses[response_index]
    
    return f"""
You are an AI tutor.

CRITICAL JSON RULES (MUST FOLLOW):
- Output MUST be valid JSON
- No markdown fences
- No trailing commas
- No comments
- Escape newlines as \\n
- Escape quotes as \\"
- Return ONLY JSON

Answer the user's question ONLY using the explanation below.
Do NOT introduce unrelated concepts or external knowledge.

**CONTEXT MATCHING RULE:**
- If 70% or more of the question relates to the explanation → Answer from context
- If less than 70% relates to the explanation → Use the dynamic response below
- If the question mixes related/unrelated parts → Answer ONLY the related parts

**DYNAMIC RESPONSE (use when less than 70% match):**
"{dynamic_response}"

--- Explanation Context ---
{context}

--- User Question ---
{question}

**EXAMPLES:**
1. Question is 80% about "inheritance" and context covers OOP → Answer from context
2. Question is 50% about "React hooks" but context is about basics → Use dynamic response
3. Question has both related and unrelated parts → Answer only the related 70%+ parts

Return a valid JSON object like:
{{
  "answer": "Your response here."
}}

Important: Do NOT add anything outside JSON.
When using dynamic response, use it EXACTLY as shown.
"""
# def followup_chat_prompt(context, question):
#     return f"""
# You are an AI tutor.

# Answer the user's question ONLY using the explanation below.
# Do NOT introduce unrelated concepts.
# If the answer is not present in the explanation, reply:

# "I’m sorry — this concept is not covered in the explanation above."

# --- Explanation Context ---
# {context}

# --- User Question ---
# {question}

# Return a valid JSON object like:
# {{
#   "answer": "Short clear answer here."
# }}

# Important: Do NOT add anything outside JSON.
# """

def grammar_fix_prompt(text):
    return f"""
You are an AI assistant tasked with transforming informal, broken, or unclear user inputs into polished, 
grammatically correct, and well-structured questions or prompts. Your response should:

Rules:
- Preserve the original intent and meaning of the input without adding or inventing information.
- Correct grammar, spelling, punctuation, and tense issues.
- Improve clarity and sentence structure, converting fragments into complete, natural sentences.
- Return only the corrected, polished prompt — do not answer, explain, or add any new content.
- Format your output as a single, well-formed sentence or prompt.

Important:
When processing user input, analyze for ambiguities or incomplete sentences and ensure the output is clear and coherent. 
Maintain a neutral tone and avoid making assumptions beyond the original intent.

User input:
{text}
"""

def study_materials_search_queries_prompt(question: str, role: str, experience: str) -> str:
    """Prompt for generating search queries for study materials"""
    return f"""
CRITICAL INSTRUCTIONS:
1. You MUST return ONLY a valid JSON array
2. NO markdown code fences (no ```json or ```)
3. NO additional text before or after the JSON
4. NO explanations, comments, or notes
5. The response must be parseable by json.loads()

Task:
Given this interview question: "{question}"
For a {role} role with {experience} years experience.

Generate 3-5 specific search queries to find the best learning resources online.
Focus on:
1. YouTube tutorial videos
2. Technical articles/blogs
3. Official documentation
4. Practice platforms (LeetCode, etc.)
5. Recommended books/courses

Return EXACTLY this format (no other text):
["query1", "query2", "query3", "query4", "query5"]

Example (for demonstration only):
["JavaScript closures tutorial", "React useEffect documentation", "System design interview preparation"]
"""

def study_materials_selection_prompt(question: str, role: str, experience: str, categorized_results: Dict[str, Any]) -> str:
    """Prompt for selecting the best study materials from search results"""
    return f"""
Interview Question: "{question}"
Role: {role} ({experience} years)

Here are found resources categorized:
{json.dumps(categorized_results, indent=2)}

IMPORTANT: For YouTube videos, preserve ALL metadata including:
- duration (already provided)
- channel (channel name)
- published_date (if available)
- views (formatted views count)

Select the BEST 2-3 resources from EACH category that are most relevant.
Remove duplicates and low-quality links.
Ensure all URLs are valid and accessible.

Return JSON with this structure - PRESERVE ALL METADATA FIELDS:
{{
    "youtube_links": [
        {{
            "title": "...",
            "url": "...",
            "duration": "...",
            "channel": "...",
            "published_date": "...",
            "views": "...",
        }}
    ],
    "articles": [{{"title": "...", "url": "...", "source": "..."}}],
    "documentation": [{{"title": "...", "url": "...", "framework": "..."}}],
    "practice_links": [{{"title": "...", "url": "...", "platform": "..."}}],
    "books": [{{"title": "...", "author": "...", "link": "..."}}],
    "courses": [{{"title": "...", "url": "...", "platform": "..."}}],
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "search_query": "main search query used"
}}

CRITICAL: Return ALL fields for YouTube videos, not just title, url, and duration.
IMPORTANT: Return ONLY valid JSON. No additional text.
"""