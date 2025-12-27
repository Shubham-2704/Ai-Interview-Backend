import os
import re
import json
import google.generativeai as genai
from fastapi import HTTPException

from utils.prompt import (
    question_answer_prompt,
    concept_explain_prompt,
)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")


def clean_ai_json(raw_text: str):
    """
    Removes ```json and ``` fences and safely parses JSON
    """
    if not raw_text:
        raise ValueError("Empty AI response")

    # Clean the text
    cleaned = raw_text.strip()
    
    # Remove JSON code fences
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    
    cleaned = cleaned.strip()
    
    try:
        # Parse JSON
        parsed = json.loads(cleaned)
        
        # Fix code blocks in answers (replace escaped \n with actual newlines)
        if isinstance(parsed, list):
            for item in parsed:
                if "answer" in item:
                    # This helps preserve code block formatting
                    item["answer"] = item["answer"].replace('\\n', '\n')
        elif isinstance(parsed, dict):
            if "explanation" in parsed:
                parsed["explanation"] = parsed["explanation"].replace('\\n', '\n')
        
        return parsed
    except json.JSONDecodeError as e:
        # Try one more time with aggressive cleaning
        cleaned = re.sub(r'^[^{[]*', '', cleaned)  # Remove anything before {
        cleaned = re.sub(r'[^}\]]*$', '', cleaned)  # Remove anything after }
        
        try:
            return json.loads(cleaned)
        except:
            raise ValueError(f"Could not parse JSON from AI response: {e}")


# ---------- Generate Questions ----------
async def generate_questions_service(body: dict):
    role = body.get("role")
    experience = body.get("experience")
    topics = body.get("topicsToFocus")
    count = body.get("numberOfQuestions")

    if not all([role, experience, topics, count]):
        raise HTTPException(400, "Missing required fields")

    prompt = question_answer_prompt(role, experience, topics, count)

    try:
        response = model.generate_content(prompt)
        return clean_ai_json(response.text)
    except Exception as e:
        raise HTTPException(500, f"Failed to generate questions: {e}")


# ---------- Generate Explanation ----------
async def generate_explanation_service(body: dict):
    question = body.get("question")

    if not question:
        raise HTTPException(400, "Missing required fields")

    prompt = concept_explain_prompt(question)

    try:
        response = model.generate_content(prompt)
        return clean_ai_json(response.text)
    except Exception as e:
        raise HTTPException(500, f"Failed to generate explanation: {e}")
