from fastapi import HTTPException
from bson import ObjectId
from config.database import database
from controllers.settings_controller import get_system_settings

sessions = database["sessions"]

async def check_session_limit(user_id: str):
    """
    Check if user can create more sessions - SIMPLIFIED
    """
    try:
        # Get limit from database
        max_sessions = await get_system_settings()
        max_sessions = max_sessions.get("max_sessions_per_user", 1)
        
        # If 0, unlimited
        if max_sessions == 0:
            return {
                "can_create": True,
                "limit": 0,
                "current": 0,
                "remaining": 0,
                "message": "Unlimited sessions allowed"
            }
        
        # Count user's sessions
        session_count = await sessions.count_documents({"user": ObjectId(user_id)})
        
        if session_count >= max_sessions:
            return {
                "can_create": False,
                "limit": max_sessions,
                "current": session_count,
                "remaining": 0,
                # "message": f"You have reached the maximum limit of {max_sessions} sessions, Please delete existing sessions to create new ones."
                "message": f"Session limit reached, delete existing sessions to create new ones."
            }
        
        return {
            "can_create": True,
            "limit": max_sessions,
            "current": session_count,
            "remaining": max_sessions - session_count,
            "message": f"You can create {max_sessions - session_count} more session(s)"
        }
    
    except Exception as e:
        print(f"Error checking session limit: {e}")
        # Allow creation on error
        return {
            "can_create": True,
            "limit": 0,
            "current": 0,
            "remaining": 0,
            "message": "Error checking limit. Session creation allowed."
        }
