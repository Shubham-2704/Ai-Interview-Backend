import os
import re
import json
from utils.helper import *
from utils.gemini_service import *
from models.user_model import *
from google import genai
from fastapi import HTTPException
from utils.encryption import encrypt, mask_key, decrypt
from config.database import database
from fastapi import Request, Depends
from middlewares.auth_middlewares import protect
from utils.prompt import *


users = database["users"]

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
async def generate_questions_service(body: dict, user_id: str):
    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user or "geminiApiKey" not in user:
        raise HTTPException(400, "Gemini API key not configured")

    api_key = decrypt(user["geminiApiKey"])

    prompt = question_answer_prompt(
        body["role"],
        body["experience"],
        body["topicsToFocus"],
        body["numberOfQuestions"]
    )

    text = GeminiService.generate(api_key, prompt)
    return clean_ai_json(text)

# ---------- Generate Explanation ----------
async def generate_explanation_service(body: dict, user_id: str):
    question = body.get("question")
    experience = body.get("experience")
    
    if not question:
        raise HTTPException(400, "Missing question")

    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user or "geminiApiKey" not in user:
        raise HTTPException(400, "Gemini API key not configured")

    api_key = decrypt(user["geminiApiKey"])
    prompt = concept_explain_prompt(question, experience)

    text = GeminiService.generate(api_key, prompt)
    return clean_ai_json(text)

async def save_key(payload: UpdateGeminiKey, request: Request, user_data = Depends(protect)):
    user_id = request.state.user["id"]

    # validate key with a basic call
    try:
        client = genai.Client(api_key=payload.apiKey)
        list(client.models.list())
    except Exception:
        return error_response(400, "Invalid or unauthorized Gemini API key")

    encrypted = encrypt(payload.apiKey)

    await users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"geminiApiKey": encrypted}}
    )

    return {
            "message": "API key saved successfully",
            "geminiKeyMasked": mask_key(payload.apiKey),
            "hasGeminiKey": True,
            }

async def delete_key(request: Request, user_data = Depends(protect)):
    user_id = request.state.user["id"]

    await users.update_one(
        {"_id": ObjectId(user_id)},
        {"$unset": {"geminiApiKey": ""}}
    )

    return {"message": "API key removed successfully"}

async def followup_chat_service(body: dict, user_id: str):
    context = body.get("context")
    question = body.get("question")

    if not context or not question:
        raise HTTPException(400, "Missing context or question")

    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user or "geminiApiKey" not in user:
        raise HTTPException(400, "Gemini API key not configured")

    api_key = decrypt(user["geminiApiKey"])

    prompt = followup_chat_prompt(context, question)

    text = GeminiService.generate(api_key, prompt)

    return clean_ai_json(text)
