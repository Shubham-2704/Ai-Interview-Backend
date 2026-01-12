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
from google.genai.errors import ServerError, ClientError
from google.api_core.exceptions import ResourceExhausted, PermissionDenied, TooManyRequests

users = database["users"]

# def clean_ai_json(raw_text: str):
#     """
#     Removes ```json and ``` fences and safely parses JSON
#     """
#     if not raw_text:
#         raise ValueError("Empty AI response")

#     # Clean the text
#     cleaned = raw_text.strip()
    
#     # Remove JSON code fences
#     if cleaned.startswith("```json"):
#         cleaned = cleaned[7:]
#     elif cleaned.startswith("```"):
#         cleaned = cleaned[3:]
    
#     if cleaned.endswith("```"):
#         cleaned = cleaned[:-3]
    
#     cleaned = cleaned.strip()
    
#     try:
#         # Parse JSON
#         parsed = json.loads(cleaned)
        
#         # Fix code blocks in answers (replace escaped \n with actual newlines)
#         if isinstance(parsed, list):
#             for item in parsed:
#                 if "answer" in item:
#                     # This helps preserve code block formatting
#                     item["answer"] = item["answer"].replace('\\n', '\n')
#         elif isinstance(parsed, dict):
#             if "explanation" in parsed:
#                 parsed["explanation"] = parsed["explanation"].replace('\\n', '\n')
        
#         return parsed
#     except json.JSONDecodeError as e:
#         # Try one more time with aggressive cleaning
#         cleaned = re.sub(r'^[^{[]*', '', cleaned)  # Remove anything before {
#         cleaned = re.sub(r'[^}\]]*$', '', cleaned)  # Remove anything after }
        
#         try:
#             return json.loads(cleaned)
#         except:
#             raise ValueError(f"Could not parse JSON from AI response: {e}")

# ---------- Generate Questions ----------
async def generate_questions_service(body: dict, user_id: str):
    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user or "geminiApiKey" not in user:
        raise HTTPException(400, "Gemini API key not configured")

    api_key = decrypt(user["geminiApiKey"])
    print("Decrypted API key",api_key)

    prompt = question_answer_prompt(
        body["role"],
        body["experience"],
        body["topicsToFocus"],
        body["numberOfQuestions"]
    )

    try:
        text = GeminiService.generate(api_key, prompt)

    except ResourceExhausted:
        return JSONResponse(status_code=403, content={"message": "Free-tier quota exceeded. Please try again later."})
    except PermissionDenied:
        return JSONResponse(status_code=403, content={"message": "Invalid Gemini API key"})  
    except ServerError:
        return JSONResponse(status_code=500, content={"message": "The model is overloaded. Please try again later."})
    except TooManyRequests:
        return JSONResponse(status_code=429, content={"message": "Too many requests. Please slow down and try again."})
    except ClientError as e:
        if "RESOURCE_EXHAUSTED" in str(e):
            return JSONResponse(
                status_code=403,
                content={"message": "Free-tier quota exceeded. Please try again later."}
            )
    
    return parse_gemini_json_response(text)

# ---------- Generate Explanation ----------
async def generate_explanation_service(body: dict, user_id: str):
    user = await users.find_one({"_id": ObjectId(user_id)})
    question = body.get("question")
    experience = body.get("experience")
    
    if not question:
        return JSONResponse(status_code=400, content={"message": "Missing question"})
    if not user or "geminiApiKey" not in user:
        return JSONResponse(status_code=400, content={"message": "Gemini API key not configured"})

    api_key = decrypt(user["geminiApiKey"])
    prompt = concept_explain_prompt(question, experience)

    try:
        text = GeminiService.generate(api_key, prompt)
    except ResourceExhausted:
        return JSONResponse(status_code=403, content={"message": "Gemini API quota limit exceeded"})
    except PermissionDenied:
        return JSONResponse(status_code=403, content={"message": "Invalid Gemini API key"})  
    except ServerError:
        return JSONResponse(status_code=500, content={"message": "The model is overloaded. Please try again later."})
    except TooManyRequests:
        return JSONResponse(status_code=429, content={"message": "Too many requests. Please slow down and try again."})
    except ClientError as e:
        if "RESOURCE_EXHAUSTED" in str(e):
            return JSONResponse(
                status_code=403,
                content={"message": "Free-tier quota exceeded. Please try again later."}
            )

    return parse_gemini_json_response(text)

async def save_key(payload: UpdateGeminiKey, request: Request, user_data = Depends(protect)):
    user_id = request.state.user["id"]
    
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
            "message": "API key saved successfully!",
            "geminiKeyMasked": mask_key(payload.apiKey),
            "hasGeminiKey": True,
            }

async def delete_key(request: Request, user_data = Depends(protect)):
    user_id = request.state.user["id"]

    await users.update_one(
        {"_id": ObjectId(user_id)},
        {"$unset": {"geminiApiKey": ""}}
    )
    return {"message": "API key removed successfully!"}

async def followup_chat_service(body: dict, user_id: str):
    user = await users.find_one({"_id": ObjectId(user_id)})
    context = body.get("context")
    question = body.get("question")

    if not context or not question:
        raise HTTPException(400, "Missing context or question")
    if not user or "geminiApiKey" not in user:
        return JSONResponse(status_code=400, content={"message": "Gemini API key not configured"})

    api_key = decrypt(user["geminiApiKey"])
    prompt = followup_chat_prompt(context, question)

    try:
        text = GeminiService.generate(api_key, prompt)
    except ResourceExhausted:
        return JSONResponse(status_code=403, content={"message": "Gemini API quota limit exceeded"})
    except PermissionDenied:
        return JSONResponse(status_code=403, content={"message": "Invalid Gemini API key"})
    except ServerError:
        return JSONResponse(status_code=500, content={"message": "The model is overloaded. Please try again later."})
    except TooManyRequests:
        return JSONResponse(status_code=429, content={"message": "Too many requests. Please slow down and try again."})
    except ClientError as e:
        if "RESOURCE_EXHAUSTED" in str(e):
            return JSONResponse(
                status_code=403,
                content={"message": "Free-tier quota exceeded. Please try again later."}
            )

    return parse_gemini_json_response(text)

async def ai_grammar_correct_service(text: str, user_id: str):
    user = await users.find_one({"_id": ObjectId(user_id)})

    if not user or "geminiApiKey" not in user:
        return JSONResponse(status_code=400, content={"message": "Gemini key not configured"})

    api_key = decrypt(user["geminiApiKey"])
    prompt = grammar_fix_prompt(text)

    try:
        response = GeminiService.generate(api_key, prompt)
    except ResourceExhausted:
        return JSONResponse(status_code=403, content={"message": "Gemini API quota limit exceeded"})
    except PermissionDenied:
        return JSONResponse(status_code=403, content={"message": "Invalid Gemini API key"})
    except ServerError:
        return JSONResponse(status_code=500, content={"message": "The model is overloaded. Please try again later."})
    except TooManyRequests:
        return JSONResponse(status_code=429, content={"message": "Too many requests. Please slow down and try again."})
    except ClientError as e:
        if "RESOURCE_EXHAUSTED" in str(e):
            return JSONResponse(
                status_code=403,
                content={"message": "Free-tier quota exceeded. Please try again later."}
            )
    
    return {"correctedText": response}
    
