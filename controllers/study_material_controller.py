from fastapi import HTTPException, Request, Depends
from datetime import datetime, timedelta
from bson import ObjectId
from typing import List, Dict, Any
import os
import re
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
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY") 
YOUTUBE_API_URL = os.getenv("YOUTUBE_API_URL")

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

def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL"""
    if not url:
        return None
    
    url = url.strip()
    
    # Handle different YouTube URL formats
    patterns = [
        # Regular watch URL: https://www.youtube.com/watch?v=VIDEO_ID
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
        # Short URL: https://youtu.be/VIDEO_ID
        r'youtu\.be\/([a-zA-Z0-9_-]{11})',
        # Embed URL: https://www.youtube.com/embed/VIDEO_ID
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def _format_youtube_views(views: str) -> str:
    """Format YouTube views in k/M format"""
    if not views:
        return "0"
    
    try:
        # Remove commas if present
        views = views.replace(',', '')
        views_int = int(views)
        
        if views_int >= 1_000_000:
            return f"{views_int / 1_000_000:.1f}M".replace('.0', '')
        elif views_int >= 1_000:
            return f"{views_int / 1_000:.1f}K".replace('.0', '')
        else:
            return str(views_int)
    except (ValueError, TypeError):
        return views


def _parse_youtube_duration(duration_iso: str) -> str:
    """Convert ISO 8601 duration to readable format"""
    if not duration_iso:
        return "N/A"
    
    try:
        # Parse ISO 8601 duration format (PT1H30M15S)
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_iso)
        
        if not match:
            return "N/A"
        
        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        seconds = int(match.group(3)) if match.group(3) else 0
        
        # Format duration nicely
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        elif seconds > 0:
            return f"{seconds}s"
        else:
            return "0s"
    
    except Exception as e:
        print(f"⚠️ Error parsing duration {duration_iso}: {e}")
        return "N/A"


async def _fetch_youtube_metadata(video_id: str) -> Optional[Dict[str, str]]:
    """Fetch YouTube video metadata using YouTube Data API"""
    if not YOUTUBE_API_KEY:
        print("⚠️ YouTube API key not configured in environment variables")
        return None
    
    try:
        print(f"📺 Fetching YouTube metadata for video: {video_id}")
        
        # YouTube Data API v3 endpoint
        api_url = f"{YOUTUBE_API_URL}/videos"
        
        params = {
            "part": "snippet,contentDetails,statistics",
            "id": video_id,
            "key": YOUTUBE_API_KEY
        }
        
        response = requests.get(api_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("items") and len(data["items"]) > 0:
                item = data["items"][0]
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                statistics = item.get("statistics", {})
                
                # Parse duration
                duration_iso = content_details.get("duration", "")
                duration_readable = _parse_youtube_duration(duration_iso)
                
                # Format published date
                published_date = snippet.get("publishedAt", "")
                if published_date:
                    try:
                        # Convert ISO format to readable date
                        published_date = published_date.replace('Z', '+00:00')
                        published_date = datetime.fromisoformat(published_date)
                        published_date = published_date.strftime("%b %d, %Y")
                    except Exception as e:
                        print(f"⚠️ Error parsing date {published_date}: {e}")
                        published_date = published_date[:10]  # Just get YYYY-MM-DD
                
                # Format views in k/M format
                raw_views = statistics.get("viewCount", "0")
                formatted_views = _format_youtube_views(raw_views)
                
                print(f"✅ Fetched YouTube metadata: {duration_readable} by {snippet.get('channelTitle')}, {formatted_views} views")
                
                return {
                    "duration": duration_readable,
                    "channel": snippet.get("channelTitle", "Unknown"),
                    "published_date": published_date,
                    "views": formatted_views,
                    "raw_views": raw_views,  # Keep original for sorting if needed
                    "likes": statistics.get("likeCount", "0"),
                    "comments": statistics.get("commentCount", "0")
                }
            else:
                print(f"⚠️ No video found with ID: {video_id}")
        else:
            print(f"❌ YouTube API error {response.status_code}: {response.text[:200]}")
        
        return None
        
    except requests.exceptions.Timeout:
        print(f"⏰ YouTube API timeout for video: {video_id}")
        return None
    except Exception as e:
        print(f"❌ Error fetching YouTube metadata: {e}")
        return None


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
        
        if result["type"] == "youtube":
            # Extract video ID
            video_id = _extract_youtube_id(result["url"])
            if video_id:
                # Fetch real YouTube metadata
                video_metadata = await _fetch_youtube_metadata(video_id)
                if video_metadata:
                    material["duration"] = video_metadata.get("duration", "N/A")
                    material["channel"] = video_metadata.get("channel", "Unknown")
                    material["published_date"] = video_metadata.get("published_date")
                    material["views"] = video_metadata.get("views")
                else:
                    # Fallback to default values
                    material["duration"] = "N/A"
                    material["channel"] = result.get("author", "Unknown")
            else:
                material["duration"] = "N/A"
                material["channel"] = result.get("author", "Unknown")
            
            categorized["youtube_links"].append(material)
        
        elif result["type"] == "practice":
            material["difficulty"] = "medium"
            categorized["practice_links"].append(material)
        
        elif result["type"] == "article":
            categorized["articles"].append(material)
        
        elif result["type"] == "documentation":
            categorized["documentation"].append(material)
        
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
        search_prompt = study_materials_search_queries_prompt(question, role, experience)
        query_response = GeminiService.generate(user_gemini_key, search_prompt)
        print(f"🤖 Raw Gemini response: {query_response}")
        
        search_queries = parse_gemini_json_response(query_response, fix_newlines=False)
        print(f"✅ Parsed {len(search_queries)} search queries: {search_queries}")
        
        # Step 2: Search for each query
        all_results = []
        for query in search_queries[:3]:
            print(f"🔎 Searching for: {query}")
            results = await search_with_tavily(f"{query} {role} interview preparation", max_results=3)
            all_results.extend(results)
        
        print(f"📊 Found {len(all_results)} search results")
        
        # Step 3: Categorize and fetch YouTube metadata
        categorized = await _categorize_materials(all_results)
        
        # Store YouTube metadata separately BEFORE Gemini selection
        youtube_metadata = {}
        for video in categorized.get("youtube_links", []):
            video_id = _extract_youtube_id(video.get("url"))
            if video_id:
                youtube_metadata[video_id] = {
                    "channel": video.get("channel"),
                    "views": video.get("views"),
                    "published_date": video.get("published_date"),
                    "duration": video.get("duration")
                }
        
        # Step 4: Let AI select best resources
        print("🤖 Step 4: AI selecting best resources...")
        selection_prompt = study_materials_selection_prompt(question, role, experience, categorized)
        selection_response = GeminiService.generate(user_gemini_key, selection_prompt)
        selected_materials = parse_gemini_json_response(selection_response, fix_newlines=True)
        
        # Step 5: Merge YouTube metadata back into selected materials
        print("🔄 Merging YouTube metadata...")
        for video in selected_materials.get("youtube_links", []):
            video_id = _extract_youtube_id(video.get("url"))
            if video_id and video_id in youtube_metadata:
                # Merge metadata
                video.update(youtube_metadata[video_id])
                print(f"✅ Merged metadata for: {video.get('title')[:50]}...")
        
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
