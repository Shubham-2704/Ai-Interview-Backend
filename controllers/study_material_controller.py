from fastapi import HTTPException, Request, Depends
from datetime import datetime, timedelta
from bson import ObjectId
from typing import List, Dict, Any
import os
import json
import requests
from utils.helper import serialize_doc, serialize_cursor
from utils.encryption import decrypt
from utils.prompt import *
from config.database import database
from models.study_material_model import *
from models.user_model import *
from middlewares.auth_middlewares import protect
from utils.gemini_service import *

# Collections
study_materials = database["study_materials"]
users = database["users"]
sessions = database["sessions"]
questions = database["questions"]

# Tavily Search API (Free tier available)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") 
TAVILY_API_URL = os.getenv("TAVILY_API_URL")

async def search_with_tavily(query: str, max_results: int = 5) -> List[Dict]:
    """Search using Tavily API (free tier available)"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TAVILY_API_KEY}"
    }
    
    payload = {
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": True,
        "include_raw_content": False,
        "include_images": True
    }
    
    try:
        response = requests.post(TAVILY_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("results", []):
            result = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0),
                "published_date": item.get("published_date"),
                "author": item.get("author", ""),
                "site_name": item.get("site_name", ""),
                "type": _determine_content_type(item.get("url", ""))
            }
            results.append(result)
        
        return results
    except Exception as e:
        print(f"Tavily search error: {e}")
        return []

def _determine_content_type(url: str) -> str:
    """Determine content type from URL"""
    url_lower = url.lower()
    
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "medium.com" in url_lower or "dev.to" in url_lower or "blog" in url_lower:
        return "article"
    elif "docs" in url_lower or "readthedocs" in url_lower or "developer" in url_lower:
        return "documentation"
    elif "leetcode" in url_lower or "hackerrank" in url_lower or "codewars" in url_lower:
        return "practice"
    elif "udemy" in url_lower or "coursera" in url_lower or "edx" in url_lower:
        return "course"
    elif "amazon" in url_lower or "goodreads" in url_lower:
        return "book"
    else:
        return "article"

async def _categorize_materials(search_results: List[Dict]) -> Dict[str, List]:
    """Categorize search results into different types"""
    categorized = {
        "youtube_links": [],
        "articles": [],
        "documentation": [],
        "practice_links": [],
        "books": [],
        "courses": []
    }
    
    for result in search_results:
        material = {
            "title": result["title"],
            "url": result["url"],
            "source": result.get("site_name", ""),
            "content": result.get("content", ""),
            "score": result.get("score", 0.0)
        }
        
        # Add duration for videos
        if result["type"] == "youtube":
            material["duration"] = "15-30 min"  # Default estimate
        
        # Add difficulty for practice links
        elif result["type"] == "practice":
            material["difficulty"] = "medium"  # Default
        
        # Add to appropriate category
        if result["type"] == "youtube":
            categorized["youtube_links"].append(material)
        elif result["type"] == "article":
            categorized["articles"].append(material)
        elif result["type"] == "documentation":
            categorized["documentation"].append(material)
        elif result["type"] == "practice":
            categorized["practice_links"].append(material)
        elif result["type"] == "book":
            categorized["books"].append(material)
        elif result["type"] == "course":
            categorized["courses"].append(material)
        else:
            categorized["articles"].append(material)
    
    return categorized

async def generate_study_materials_with_ai(
    question: str, 
    role: str, 
    experience: str,
    user_gemini_key: str
) -> Dict[str, Any]:
    """Use Gemini AI to generate search queries and analyze results"""
    
    try:
        print(f"🔍 Step 1: Generating search queries for: {question}")
        # Step 1: Generate search queries from the question        
        search_prompt = study_materials_search_queries_prompt(question, role, experience)
        # Use GeminiService instead of direct genai calls
        query_response = GeminiService.generate(user_gemini_key, search_prompt)
        print(f"🤖 Raw Gemini response: {query_response}")
        
        # Parse with markdown handling
        search_queries = parse_gemini_json_response(query_response, fix_newlines=False)
        print(f"✅ Parsed {len(search_queries)} search queries: {search_queries}")
        
        # Step 2: Search for each query
        all_results = []
        for query in search_queries[:3]:
            print(f"🔎 Searching for: {query}")
            results = await search_with_tavily(f"{query} {role} interview preparation", max_results=3)
            all_results.extend(results)
        
        print(f"📊 Found {len(all_results)} search results")
        
        # Step 3: Categorize and deduplicate
        categorized = await _categorize_materials(all_results)
        
        # Step 4: Let AI select best resources
        print("🤖 Step 4: AI selecting best resources...")
        selection_prompt = study_materials_selection_prompt(question, role, experience, categorized)
        
        selection_response = GeminiService.generate(user_gemini_key, selection_prompt)
        
        # Parse selection response
        selected_materials = parse_gemini_json_response(selection_response,  fix_newlines=True)
        
        # Count total sources
        material_categories = ["youtube_links", "articles", "documentation", 
                              "practice_links", "books", "courses"]
        total_sources = sum(len(selected_materials.get(cat, [])) 
                           for cat in material_categories)
        
        print(f"🎉 Generated {total_sources} total resources")
        
        return {
            **selected_materials,
            "total_sources": total_sources,
            "ai_model_used": "gemini-2.5-flash"
        }
        
    except Exception as e:
        print(f"❌ AI generation error: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to basic search
        results = await search_with_tavily(f"{question} {role} interview tutorial", max_results=10)
        categorized = await _categorize_materials(results)
        
        material_categories = ["youtube_links", "articles", "documentation", 
                              "practice_links", "books", "courses"]
        total_sources = sum(len(categorized.get(cat, [])) 
                           for cat in material_categories)
        
        return {
            **categorized,
            "keywords": question.lower().split()[:5],
            "search_query": f"{question} {role} interview",
            "total_sources": total_sources,
            "ai_model_used": "tavily_search_fallback"
        }

async def get_or_create_study_materials(
    request: Request,
    question_id: str,
    data: StudyMaterialRequest,
    user = Depends(protect)
):
    """Get study materials for a question (with caching)"""
    user_id = request.state.user["id"]
    
    # Get question and session details
    question = await questions.find_one({"_id": ObjectId(question_id)})
    if not question:
        raise HTTPException(404, "Question not found")
    
    session = await sessions.find_one({"_id": question["session"]})
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Check if materials already exist and not forcing refresh
    if not data.force_refresh:
        existing = await study_materials.find_one({
            "question_id": question_id,
            "user_id": user_id
        })
        
        if existing:
            # Check if cache is fresh (less than 7 days old)
            updated_at = existing.get("updated_at", datetime.utcnow())
            if datetime.utcnow() - updated_at < timedelta(days=7):
                return serialize_doc(existing)
    
    # Get user's Gemini API key
    user_doc = await users.find_one({"_id": ObjectId(user_id)})
    if not user_doc or not user_doc.get("geminiApiKey"):
        raise HTTPException(400, "Gemini API key is required for generating study materials")
    
    gemini_key = decrypt(user_doc["geminiApiKey"])
    
    # Generate new materials
    try:
        materials_data = await generate_study_materials_with_ai(
            question=data.question or question["question"],
            role=session["role"],
            experience=session["experience"],
            user_gemini_key=gemini_key
        )
        
        # Prepare study material document
        study_material_doc = {
            "session_id": str(session["_id"]),
            "question_id": question_id,
            "question_text": question["question"],
            "role": session["role"],
            "experience_level": session["experience"],
            "user_id": user_id,
            **materials_data,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Save to database
        if data.force_refresh:
            # Update existing
            await study_materials.update_one(
                {"question_id": question_id, "user_id": user_id},
                {"$set": study_material_doc},
                upsert=True
            )
        else:
            # Insert new
            await study_materials.insert_one(study_material_doc)
        
        return serialize_doc(study_material_doc)
        
    except Exception as e:
        print(f"Error generating study materials: {e}")
        raise HTTPException(500, f"Failed to generate study materials: {str(e)}")

async def get_study_materials_by_question(
    request: Request,
    question_id: str,
    user = Depends(protect)
):
    """Get study materials for a specific question"""
    user_id = request.state.user["id"]
    
    material = await study_materials.find_one({
        "question_id": question_id,
        "user_id": user_id
    })
    
    if not material:
        raise HTTPException(404, "No study materials found for this question")
    
    return serialize_doc(material)

async def get_study_materials_by_session(
    request: Request,
    session_id: str,
    user = Depends(protect)
):
    """Get all study materials for a session"""
    user_id = request.state.user["id"]
    
    cursor = study_materials.find({
        "session_id": session_id,
        "user_id": user_id
    }).sort("created_at", -1)
    
    materials = await serialize_cursor(cursor)
    
    # Group by question
    grouped = {}
    for material in materials:
        question_id = material["question_id"]
        if question_id not in grouped:
            grouped[question_id] = {
                "question": material["question_text"],
                "materials": []
            }
        grouped[question_id]["materials"].append(material)
    
    return {"success": True, "data": grouped}

async def refresh_study_materials(
    request: Request,
    material_id: str,
    user = Depends(protect)
):
    """Force refresh study materials"""
    user_id = request.state.user["id"]
    
    material = await study_materials.find_one({
        "_id": ObjectId(material_id),
        "user_id": user_id
    })
    
    if not material:
        raise HTTPException(404, "Study material not found")
    
    # Get user's Gemini key
    user_doc = await users.find_one({"_id": ObjectId(user_id)})
    if not user_doc or not user_doc.get("geminiApiKey"):
        raise HTTPException(400, "Gemini API key is required")
    
    gemini_key = decrypt(user_doc["geminiApiKey"])
    
    # Regenerate materials
    new_materials = await generate_study_materials_with_ai(
        question=material["question_text"],
        role=material["role"],
        experience=material["experience_level"],
        user_gemini_key=gemini_key
    )
    
    # Update in database
    await study_materials.update_one(
        {"_id": ObjectId(material_id)},
        {"$set": {
            **new_materials,
            "updated_at": datetime.utcnow()
        }}
    )
    
    updated = await study_materials.find_one({"_id": ObjectId(material_id)})
    return serialize_doc(updated)

async def delete_study_materials(
    request: Request,
    material_id: str,
    user = Depends(protect)
):
    """Delete study materials"""
    user_id = request.state.user["id"]
    
    result = await study_materials.delete_one({
        "_id": ObjectId(material_id),
        "user_id": user_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(404, "Study material not found")
    
    return {"success": True, "message": "Study materials deleted"}
