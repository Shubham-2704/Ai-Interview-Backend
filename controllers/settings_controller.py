from utils.encryption import encrypt, decrypt
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from config.database import database
from google import genai
import requests
import json
import os

settings_collection = database["system_settings"]
TAVILY_API_USAGE_URL = os.getenv("TAVILY_API_USAGE_URL")

async def get_system_settings():
    """Get system settings from database"""
    try:
        settings = await settings_collection.find_one({"name": "general_settings"})
        encrypted_key = settings.get("tavily_api_key")
        encrypted_gemini_key = settings.get("gemini_api_key")
        
        if not settings:
            # Create default if not exists
            default_settings = {
                "name": "general_settings",
                "allow_registration": True,
                "maintenance_mode": False,
                "max_sessions_per_user": 1,
                "number_of_questions": 10,
                "load_more_questions": 5,
                "max_load_more_clicks": 3,
                "max_study_materials_per_session": 10,
                "study_materials_refresh_hours": 24,
                "tavily_api_key": "",
                "gemini_api_key":"",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            await settings_collection.insert_one(default_settings)
            return {
                "allow_registration": True,
                "maintenance_mode": False,
                "max_sessions_per_user": 1,
                "number_of_questions": 10,
                "load_more_questions": 5,
                "max_load_more_clicks": 3,
                "max_study_materials_per_session": 10,
                "study_materials_refresh_hours": 24,
                "tavily_api_key": "",
                "gemini_api_key":"",
            }
        
        # Return all settings
        return {
            "allow_registration": settings.get("allow_registration", True),  
            "maintenance_mode": settings.get("maintenance_mode", False),  
            "max_sessions_per_user": settings.get("max_sessions_per_user", 1),
            "number_of_questions": settings.get("number_of_questions", 10),
            "load_more_questions": settings.get("load_more_questions", 5),
            "max_load_more_clicks": settings.get("max_load_more_clicks", 3),
            "max_study_materials_per_session": settings.get("max_study_materials_per_session", 10),
            "study_materials_refresh_hours": settings.get("study_materials_refresh_hours", 24),
            "tavily_api_key": decrypt(encrypted_key) if encrypted_key else "",
            "gemini_api_key": decrypt(encrypted_gemini_key) if encrypted_gemini_key else "",
            "has_tavily_key": bool(encrypted_key),
            "has_gemini_key": bool(encrypted_gemini_key)
        }
    
    except Exception as e:
        print(f"Error getting settings: {e}")
        return {
            "allow_registration": True,  
            "maintenance_mode": False,  
            "max_sessions_per_user": 1,
            "number_of_questions": 10,
            "load_more_questions": 5,
            "max_load_more_clicks": 3,
            "max_study_materials_per_session": 10,
            "study_materials_refresh_hours": 24,
            "tavily_api_key": "",
            "gemini_api_key":""  
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
        if "allow_registration" in settings_data:
            update_data["allow_registration"] = settings_data["allow_registration"]
        
        if "maintenance_mode" in settings_data:
            update_data["maintenance_mode"] = settings_data["maintenance_mode"]

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
            raw_key = settings_data["tavily_api_key"]

            # 🔍 Validate key with Tavily
            is_valid = validate_tavily_api_key(raw_key)
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content={"detail":"Invalid or unauthorized Tavily API key"}
                )

            # 🔐 Encrypt only AFTER validation
            encrypted_key = encrypt(raw_key)
            update_data["tavily_api_key"] = encrypted_key
        
        if "gemini_api_key" in settings_data:
            raw_gemin_key = settings_data["gemini_api_key"]

            try:
                client = genai.Client(api_key=raw_gemin_key)
                list(client.models.list())
            except Exception:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid or unauthorized Gemini API key"}
                )
            
            # 🔐 Encrypt only AFTER validation
            encrypted_gemini_key = encrypt(raw_gemin_key)
            update_data["gemini_api_key"] = encrypted_gemini_key
            
        
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
        # 🔐 Get encrypted Tavily API key directly from DB
        settings_doc = await settings_collection.find_one(
            {"name": "general_settings"},
            {"tavily_api_key": 1}
        )

        encrypted_key = settings_doc.get("tavily_api_key") if settings_doc else None

        if not encrypted_key:
            return {
                "available": False,
                "error": "Tavily API key not configured"
            }

        # 🔓 Decrypt key for Tavily API call
        tavily_api_key = decrypt(encrypted_key)

        headers = {
            "Authorization": f"Bearer {tavily_api_key}"
        }

        response = requests.get(
            TAVILY_API_USAGE_URL,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            # Extract credits from account data (monthly plan)
            account_data = data.get("account", {})
            total_credits = account_data.get("plan_limit", 1000) or 1000
            used_credits = account_data.get("plan_usage", 0) or 0

            # Fallback fields
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

def validate_tavily_api_key(api_key: str) -> bool:
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    response = requests.get(
        TAVILY_API_USAGE_URL,  # 👈 THIS IS TAVILY’S API
        headers=headers,
        timeout=8
    )

    return response.status_code == 200
