from fastapi import HTTPException
from datetime import datetime, timezone
from config.database import database

settings_collection = database["system_settings"]

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
                "max_study_materials_per_session": 10,  # ONLY THIS
                "study_materials_refresh_hours": 24,    # AND THIS
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            await settings_collection.insert_one(default_settings)
            return {
                "max_sessions_per_user": 1,
                "number_of_questions": 10,
                "load_more_questions": 5,
                "max_load_more_clicks": 3,
                "max_study_materials_per_session": 10,  # ONLY THIS
                "study_materials_refresh_hours": 24,    # AND THIS
            }
        
        # Return all settings
        return {
            "max_sessions_per_user": settings.get("max_sessions_per_user", 1),
            "number_of_questions": settings.get("number_of_questions", 10),
            "load_more_questions": settings.get("load_more_questions", 5),
            "max_load_more_clicks": settings.get("max_load_more_clicks", 3),
            "max_study_materials_per_session": settings.get("max_study_materials_per_session", 10),  # ONLY THIS
            "study_materials_refresh_hours": settings.get("study_materials_refresh_hours", 24),      # AND THIS
        }
    
    except Exception as e:
        print(f"Error getting settings: {e}")
        return {
            "max_sessions_per_user": 1,
            "number_of_questions": 10,
            "load_more_questions": 5,
            "max_load_more_clicks": 3,
            "max_study_materials_per_session": 10,  # ONLY THIS
            "study_materials_refresh_hours": 24,    # AND THIS
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
        
        # ONLY THESE TWO FOR RESOURCES:
        if "max_study_materials_per_session" in settings_data:
            update_data["max_study_materials_per_session"] = settings_data["max_study_materials_per_session"]
        
        if "study_materials_refresh_hours" in settings_data:
            update_data["study_materials_refresh_hours"] = settings_data["study_materials_refresh_hours"]
        
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

