from fastapi import HTTPException
from datetime import datetime, timezone
from config.database import database
import requests
import json
import os

settings_collection = database["system_settings"]
TAVILY_API_USAGE_URL = os.getenv("TAVILY_API_USAGE_URL")

async def get_system_settings():
    """Get system settings from database"""
    try:
        settings = await settings_collection.find_one({"name": "general_settings"})
        
        if not settings:
            # Create default if not exists
            default_settings = {
                "name": "general_settings",
                "max_sessions_per_user": 1,
                "number_of_questions": 10,
                "load_more_questions": 5,
                "max_load_more_clicks": 3,
                "max_study_materials_per_session": 10,
                "study_materials_refresh_hours": 24,
                "tavily_api_key": "",  # ONLY ADD THIS
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            await settings_collection.insert_one(default_settings)
            return {
                "max_sessions_per_user": 1,
                "number_of_questions": 10,
                "load_more_questions": 5,
                "max_load_more_clicks": 3,
                "max_study_materials_per_session": 10,
                "study_materials_refresh_hours": 24,
                "tavily_api_key": "",  # ONLY ADD THIS
            }
        
        # Return all settings
        return {
            "max_sessions_per_user": settings.get("max_sessions_per_user", 1),
            "number_of_questions": settings.get("number_of_questions", 10),
            "load_more_questions": settings.get("load_more_questions", 5),
            "max_load_more_clicks": settings.get("max_load_more_clicks", 3),
            "max_study_materials_per_session": settings.get("max_study_materials_per_session", 10),
            "study_materials_refresh_hours": settings.get("study_materials_refresh_hours", 24),
            "tavily_api_key": settings.get("tavily_api_key", ""),  # ONLY ADD THIS
        }
    
    except Exception as e:
        print(f"Error getting settings: {e}")
        return {
            "max_sessions_per_user": 1,
            "number_of_questions": 10,
            "load_more_questions": 5,
            "max_load_more_clicks": 3,
            "max_study_materials_per_session": 10,
            "study_materials_refresh_hours": 24,
            "tavily_api_key": "",  
        }

async def update_system_settings(settings_data: dict):
    """Update system settings"""
    try:
        now = datetime.now(timezone.utc)
        
        # Prepare update data
        update_data = {
            "updated_at": now
        }
        
        # Add all settings fields (only include what's provided)
        if "max_sessions_per_user" in settings_data:
            update_data["max_sessions_per_user"] = settings_data["max_sessions_per_user"]
        
        if "number_of_questions" in settings_data:
            update_data["number_of_questions"] = settings_data["number_of_questions"]
        
        if "load_more_questions" in settings_data:
            update_data["load_more_questions"] = settings_data["load_more_questions"]
        
        if "max_load_more_clicks" in settings_data:
            update_data["max_load_more_clicks"] = settings_data["max_load_more_clicks"]
        
        if "max_study_materials_per_session" in settings_data:
            update_data["max_study_materials_per_session"] = settings_data["max_study_materials_per_session"]
        
        if "study_materials_refresh_hours" in settings_data:
            update_data["study_materials_refresh_hours"] = settings_data["study_materials_refresh_hours"]
        
        if "tavily_api_key" in settings_data:
            update_data["tavily_api_key"] = settings_data["tavily_api_key"]
        
        await settings_collection.update_one(
            {"name": "general_settings"},
            {
                "$set": update_data,
                "$setOnInsert": {
                    "created_at": now
                }
            },
            upsert=True
        )
        
        return {
            "success": True,
            "message": "Settings updated successfully",
            "settings": update_data
        }
    
    except Exception as e:
        print(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# This function to get real Tavily API usage
async def get_tavily_api_usage():
    try:
        # Get Tavily API key from settings
        settings = await get_system_settings()
        tavily_api_key = settings.get("tavily_api_key")
        
        if not tavily_api_key:
            return {
                "error": "Tavily API key not configured",
                "available": False
            }
        
        # Call Tavily usage API
        headers = {
            "Authorization": f"Bearer {tavily_api_key}"
        }
        
        response = requests.get(TAVILY_API_USAGE_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"Tavily API response data: {data}")
            
            # Extract credits from account data (monthly plan)
            account_data = data.get("account", {})
            total_credits = account_data.get("plan_limit", 1000) or 1000  # Default to 1000 if not found
            used_credits = account_data.get("plan_usage", 0) or 0
            
            # If not in account, try direct fields
            if total_credits == 1000 and used_credits == 0:
                total_credits = data.get("limit", 1000) or 1000
                used_credits = data.get("usage", 0) or 0
            
            remaining_credits = max(0, total_credits - used_credits)
            
            return {
                "available": True,
                "total_credits": total_credits,
                "used_credits": used_credits,
                "remaining_credits": remaining_credits,
                "last_checked": datetime.now(timezone.utc).isoformat()
            }
        else:
            error_text = response.text[:200] if response.text else "No error message"
            return {
                "available": False,
                "error": f"Tavily API error: {response.status_code} - {error_text}",
                "last_checked": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        print(f"Error getting Tavily usage: {e}")
        import traceback
        traceback.print_exc()
        return {
            "available": False,
            "error": str(e),
            "last_checked": datetime.now(timezone.utc).isoformat()
        }