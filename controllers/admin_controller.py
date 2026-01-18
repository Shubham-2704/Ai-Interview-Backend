from fastapi import HTTPException, Request, Depends
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from typing import List, Dict, Optional
from config.database import database
from models.admin_model import *
from utils.helper import *
from middlewares.auth_middlewares import protect
from utils.auth import *
from utils.hash import *
from google import genai
from utils.encryption import *

# Collections
users = database["users"]
sessions = database["sessions"]
questions = database["questions"]
study_materials = database["study_materials"]

async def check_admin_access(user_id: str):
    """Check if user is admin"""
    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user or user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user

# ---------- Get Dashboard Stats ----------
async def get_dashboard_stats(
    request: Request, 
    date_range: Optional[DateRangeRequest] = None,
    current_user: dict = Depends(protect)
):
    """Get comprehensive dashboard statistics"""
    
    # Get user and verify admin access
    await check_admin_access(current_user["id"])
    
    now = datetime.now(timezone.utc)
    
    # Determine date range
    if date_range and date_range.period:
        if date_range.period == "7d":
            start_date = now - timedelta(days=7)
        elif date_range.period == "30d":
            start_date = now - timedelta(days=30)
        elif date_range.period == "90d":
            start_date = now - timedelta(days=90)
        elif date_range.period == "year":
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=7)
    else:
        start_date = now - timedelta(days=7)
    
    # 1. Total Users
    total_users = await users.count_documents({})
    
    # 2. Total Sessions
    total_sessions = await sessions.count_documents({})
    
    # 3. Total Questions
    total_questions = await questions.count_documents({})
    
    # 4. Total Study Materials
    total_study_materials = await study_materials.count_documents({})
    
    # 5. Active Users Today
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    active_users_today = await users.count_documents({
        "updatedAt": {"$gte": today_start}
    })
    
    # 6. Average Session Time (in minutes)
    pipeline_avg_time = [
        {
            "$match": {
                "duration": {"$exists": True, "$ne": None}
            }
        },
        {
            "$group": {
                "_id": None,
                "avgDuration": {"$avg": "$duration"}
            }
        }
    ]
    
    avg_duration_result = await sessions.aggregate(pipeline_avg_time).to_list(1)
    if avg_duration_result and avg_duration_result[0].get("avgDuration"):
        avg_duration_seconds = avg_duration_result[0]["avgDuration"]
        # Assuming duration is stored in seconds, convert to minutes
        avg_session_time_minutes = avg_duration_seconds / 60
    else:
        avg_session_time_minutes = 30.0  # Default fallback
        
    # 7. Sessions per day (for chart)
    sessions_per_day = await get_sessions_per_day(start_date, now)
    
    # 8. Top Performing Users (based on sessions count)
    top_users = await get_top_performing_users(limit=5)
    
    # 9. Recent Users (last 7 days)
    recent_users = await get_recent_users(limit=5)
    
    # 10. System Status
    system_status = await get_system_status()
    
    # 11. Users by Role Distribution (NEW)
    users_by_role_pipeline = [
        {
            "$group": {
                "_id": "$role",
                "count": {"$sum": 1}
            }
        }
    ]
    
    role_cursor = users.aggregate(users_by_role_pipeline)
    users_by_role_list = await serialize_cursor(role_cursor)
    
    # Convert to object format expected by frontend
    users_by_role = {}
    for item in users_by_role_list:
        role_name = item["_id"]
        if role_name not in ["admin", "moderator", "user"]:
            role_name = "user"
        users_by_role[role_name] = item["count"]
    
    # Ensure all roles exist in response
    for role in ["user", "admin", "moderator"]:
        if role not in users_by_role:
            users_by_role[role] = 0
    
    # Return data directly without wrapper
    return {
        "totalUsers": total_users,
        "totalSessions": total_sessions,
        "totalQuestions": total_questions,
        "totalStudyMaterials": total_study_materials,
        "activeUsersToday": active_users_today,
        "avgSessionTime":  round(float(avg_session_time_minutes), 1),
        "sessionsPerDay": sessions_per_day,
        "topUsers": top_users,
        "recentUsers": recent_users,
        "systemStatus": system_status,
        "usersByRole": users_by_role,
    }

async def get_sessions_per_day(start_date: datetime, end_date: datetime) -> List[Dict]:
    """Get sessions count per day for the last 7 days - FIXED VERSION"""
    
    # Use a broader timezone-agnostic approach
    pipeline = [
        {
            "$project": {
                "dateOnly": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$createdAt"
                        # Don't specify timezone - let MongoDB use stored timezone
                    }
                }
            }
        },
        {
            "$match": {
                "dateOnly": {
                    "$gte": start_date.strftime("%Y-%m-%d"),
                    "$lte": end_date.strftime("%Y-%m-%d")
                }
            }
        },
        {
            "$group": {
                "_id": "$dateOnly",
                "count": {"$sum": 1}
            }
        },
        {
            "$sort": {"_id": 1}
        },
        {
            "$project": {
                "date": "$_id",
                "sessions": "$count",
                "_id": 0
            }
        }
    ]
    
    results = await sessions.aggregate(pipeline).to_list(None)
    
    print(f"\n📊 DEBUG: Found {len(results)} days with sessions")
    for r in results:
        print(f"  {r['date']}: {r['sessions']} sessions")
    
    # Generate chart data for last 7 days
    chart_data = []
    for i in range(6, -1, -1):  # Last 7 days including today
        chart_date = end_date - timedelta(days=i)
        date_str = chart_date.strftime("%Y-%m-%d")
        day_abbr = chart_date.strftime("%a")
        
        matching = next((r for r in results if r["date"] == date_str), None)
        
        chart_data.append({
            "date": date_str,
            "day": day_abbr,
            "sessions": matching["sessions"] if matching else 0
        })
    
    return chart_data

async def get_top_performing_users(limit: int = 5) -> List[Dict]:
    """Get top performing users based on session count"""
    pipeline = [
        {
            "$lookup": {
                "from": "sessions",
                "localField": "_id",
                "foreignField": "user",
                "as": "user_sessions"
            }
        },
        {
            "$lookup": {
                "from": "questions",
                "let": {"userSessions": "$user_sessions._id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$in": ["$session", "$$userSessions"]
                            }
                        }
                    }
                ],
                "as": "user_questions"
            }
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "email": 1,
                "profileImageUrl": 1,
                "sessionCount": {"$size": "$user_sessions"},
                "questionCount": {"$size": "$user_questions"},
                "score": {
                    "$cond": [
                        {"$gt": [{"$size": "$user_sessions"}, 0]},
                        {
                            "$multiply": [
                                100,
                                {
                                    "$divide": [
                                        {"$size": "$user_questions"},
                                        {"$multiply": [{"$size": "$user_sessions"}, 20]}
                                    ]
                                }
                            ]
                        },
                        0
                    ]
                }
            }
        },
        {
            "$match": {
                "sessionCount": {"$gt": 0}
            }
        },
        {
            "$sort": {"score": -1, "sessionCount": -1}
        },
        {
            "$limit": limit
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "email": 1,
                "profileImageUrl": 1,
                "sessions": "$sessionCount",
                "questions": "$questionCount",
                "score": {"$round": ["$score", 1]}
            }
        }
    ]
    
    cursor = users.aggregate(pipeline)
    results = await serialize_cursor(cursor)
    
    # Format the results for frontend
    formatted_results = []
    for user in results:
        formatted_results.append({
            "id": str(user.get("_id")),  # Convert ObjectId to string
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "profileImageUrl": user.get("profileImageUrl", ""),
            "sessions": user.get("sessions", 0),
            "questions": user.get("questions", 0),
            "score": user.get("score", 0)
        })
    
    return formatted_results

async def get_recent_users(limit: int = 5) -> List[Dict]:
    """Get recently registered users"""
    pipeline = [
        {
            "$sort": {"createdAt": -1}
        },
        {
            "$limit": limit
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "email": 1,
                "profileImageUrl": 1,
                "role": 1,
                "createdAt": 1,
                "updatedAt": 1,
                "isActive": {
                    "$cond": [
                        {"$gte": ["$updatedAt", {"$dateSubtract": {"startDate": "$$NOW", "unit": "day", "amount": 7}}]},
                        True,
                        False
                    ]
                }
            }
        }
    ]
    
    cursor = users.aggregate(pipeline)
    results = await serialize_cursor(cursor)
    
    # Format the results for frontend
    formatted_results = []
    for user in results:
        formatted_results.append({
            "id": str(user.get("_id")),  # Convert ObjectId to string
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "profileImageUrl": user.get("profileImageUrl", ""),
            "role": user.get("role", "user"),
            "isActive": user.get("isActive", False),
            "joined": user["createdAt"].strftime("%b %d") if user.get("createdAt") else "N/A"
        })
    
    return formatted_results

async def get_system_status() -> Dict:
    """Get system health and performance metrics"""
    now = datetime.now(timezone.utc)
    
    # Get active connections (users active in last 5 minutes)
    five_min_ago = now - timedelta(minutes=5)
    active_connections = await users.count_documents({
        "updatedAt": {"$gte": five_min_ago}
    })
    
    # Calculate uptime (simplified - you'd want to track this properly)
    total_requests = await get_total_requests_last_hour()
    
    # Calculate error rate (simplified)
    error_rate = 0.2
    
    # Database size/usage (simplified)
    db_usage = await calculate_database_usage()
    
    return {
        "apiResponseTime": 98,
        "databaseUsage": db_usage,
        "uptime": 99.9,
        "activeConnections": active_connections,
        "totalRequests": total_requests,
        "errorRate": error_rate
    }

async def get_total_requests_last_hour() -> int:
    """Get total API requests in last hour"""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    
    # Count sessions created in last hour as a proxy for requests
    return await sessions.count_documents({
        "createdAt": {"$gte": one_hour_ago}
    })

async def calculate_database_usage() -> float:
    """Calculate database usage percentage"""
    # Get total document counts
    total_users = await users.count_documents({})
    total_sessions = await sessions.count_documents({})
    total_questions = await questions.count_documents({})
    total_materials = await study_materials.count_documents({})
    
    total_docs = total_users + total_sessions + total_questions + total_materials
    
    # Simplified calculation
    max_capacity = 100000
    usage_percentage = (total_docs / max_capacity) * 100
    
    return round(min(usage_percentage, 100), 1)

# ---------- Get Users List (for admin) ----------
# ---------- Get Users List (for admin) ----------
async def get_admin_users_list(
    request: Request,
    page: int = 1,
    limit: int = 20,
    search: str = "",
    role: str = "all",
    status: str = "all",
    current_user: dict = Depends(protect)
):
    """Get users list for admin with filtering"""
    await check_admin_access(current_user["id"])
    
    skip = (page - 1) * limit
    
    # Build filter query
    filter_query = {}
    
    if search:
        filter_query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    
    if role != "all":
        filter_query["role"] = role
    
    if status == "active":
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        filter_query["updatedAt"] = {"$gte": week_ago}
    elif status == "inactive":
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        filter_query["updatedAt"] = {"$lt": week_ago}
    
    # Get users with session, question, and material counts
    pipeline = [
        {"$match": filter_query},
        {
            "$lookup": {
                "from": "sessions",
                "localField": "_id",
                "foreignField": "user",
                "as": "user_sessions"
            }
        },
        # FLEXIBLE MATERIALS LOOKUP - tries multiple field names
        {
            "$lookup": {
                "from": "study_materials",
                "let": {"userId": "$_id", "userIdStr": {"$toString": "$_id"}},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$or": [
                                    # Try user_id as ObjectId
                                    {"$eq": ["$user_id", "$$userId"]},
                                    # Try user_id as string
                                    {"$eq": ["$user_id", "$$userIdStr"]},
                                    # Try user field as ObjectId
                                    {"$eq": ["$user", "$$userId"]},
                                    # Try user field as string
                                    {"$eq": ["$user", "$$userIdStr"]},
                                    # Try createdBy field
                                    {"$eq": ["$createdBy", "$$userId"]},
                                    {"$eq": ["$createdBy", "$$userIdStr"]},
                                    # Try userId field
                                    {"$eq": ["$userId", "$$userId"]},
                                    {"$eq": ["$userId", "$$userIdStr"]}
                                ]
                            }
                        }
                    }
                ],
                "as": "user_materials"
            }
        },
        {
            "$lookup": {
                "from": "questions",
                "let": {"userId": "$_id"},
                "pipeline": [
                    {
                        "$lookup": {
                            "from": "sessions",
                            "localField": "session",
                            "foreignField": "_id",
                            "as": "question_session"
                        }
                    },
                    {
                        "$unwind": {
                            "path": "$question_session",
                            "preserveNullAndEmptyArrays": True
                        }
                    },
                    {
                        "$match": {
                            "$expr": {
                                "$eq": ["$question_session.user", "$$userId"]
                            }
                        }
                    }
                ],
                "as": "user_questions"
            }
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "email": 1,
                "profileImageUrl": 1,
                "role": 1,
                "createdAt": 1,
                "updatedAt": 1,
                "isActive": {
                    "$cond": [
                        {"$gte": ["$updatedAt", {"$dateSubtract": {"startDate": "$$NOW", "unit": "day", "amount": 7}}]},
                        True,
                        False
                    ]
                },
                "sessionCount": {"$size": "$user_sessions"},
                "materialCount": {"$size": "$user_materials"},
                "questionCount": {"$size": "$user_questions"}
            }
        },
        {"$sort": {"createdAt": -1}},
        {"$skip": skip},
        {"$limit": limit}
    ]
    
    cursor = users.aggregate(pipeline)
    users_list = await serialize_cursor(cursor)
    
    # Debug: Check what we're getting
    print(f"\n=== DEBUG: Found {len(users_list)} users ===")
    for i, user in enumerate(users_list):
        print(f"User {i+1}: {user.get('name')}")
        print(f"  Sessions: {user.get('sessionCount')}")
        print(f"  Materials: {user.get('materialCount')}")
        print(f"  Questions: {user.get('questionCount')}")
    
    # Format users list
    formatted_users = []
    for user in users_list:
        formatted_users.append({
            "id": str(user.get("_id")),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "profileImageUrl": user.get("profileImageUrl", ""),
            "role": user.get("role", "user"),
            "createdAt": user.get("createdAt"),
            "updatedAt": user.get("updatedAt"),
            "isActive": user.get("isActive", False),
            "sessionCount": user.get("sessionCount", 0),
            "materialCount": user.get("materialCount", 0),
            "questionCount": user.get("questionCount", 0)
        })
    
    # Get total count for pagination
    total = await users.count_documents(filter_query)
    
    # Return data directly without wrapper
    return {
        "users": formatted_users,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }

# ---------- Get User Details (admin) ----------
# async def get_admin_user_details(
#     request: Request,
#     user_id: str,
#     current_user: dict = Depends(protect)
# ):
#     """Get detailed user information for admin"""
#     await check_admin_access(current_user["id"])
    
#     user = await users.find_one({"_id": ObjectId(user_id)})
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
    
#     # Get user sessions
#     session_cursor = sessions.find({"user": ObjectId(user_id)}).sort("createdAt", -1)
#     user_sessions = await serialize_cursor(session_cursor)
    
#     # Get session IDs for counting questions
#     session_ids = [ObjectId(session["id"]) for session in user_sessions]
    
#     # Count total questions for this user (through sessions)
#     total_questions = 0
#     if session_ids:
#         total_questions = await questions.count_documents({"session": {"$in": session_ids}})
    
#     # Add questions count to each session
#     for session in user_sessions:
#         session["questionCount"] = await questions.count_documents({"session": ObjectId(session["id"])})
#         session["materialCount"] = await study_materials.count_documents({"session_id": session["id"]})
    
#     user_data = serialize_doc(user)
#     user_data.pop("password", None)
#     user_data.pop("geminiApiKey", None)
    
#     # Return data directly without wrapper
#     return {
#         "user": user_data,
#         "sessions": user_sessions,
#         "stats": {
#             "totalSessions": len(user_sessions),
#             "totalQuestions": total_questions,  # Fixed: Use calculated total
#             "totalMaterials": await study_materials.count_documents({"user_id": user_id}),
#             "avgQuestionsPerSession": len(user_sessions) and total_questions / len(user_sessions) or 0,
#             "completionRate": await calculate_user_completion_rate(user_id),
#             "lastLogin": user.get("updatedAt"),
#             "joinedDate": user.get("createdAt")
#         }
#     }

async def get_admin_user_details(
    request: Request,
    user_id: str,
    current_user: dict = Depends(protect)
):
    """Get detailed user information for admin"""
    await check_admin_access(current_user["id"])
    
    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user sessions
    session_cursor = sessions.find({"user": ObjectId(user_id)}).sort("createdAt", -1)
    user_sessions = await serialize_cursor(session_cursor)
    
    # Get session IDs for counting questions
    session_ids = [ObjectId(session["id"]) for session in user_sessions]
    
    # Count total questions for this user (through sessions)
    total_questions = 0
    if session_ids:
        total_questions = await questions.count_documents({"session": {"$in": session_ids}})
    
    # Add questions count to each session
    for session in user_sessions:
        session["questionCount"] = await questions.count_documents({"session": ObjectId(session["id"])})
        session["materialCount"] = await study_materials.count_documents({"session_id": session["id"]})
    
    # Serialize user document
    user_data = serialize_doc(user)
    
    # Remove password only
    user_data.pop("password", None)
    # DO NOT remove geminiApiKey - COMMENT OUT OR DELETE THIS LINE:
    # user_data.pop("geminiApiKey", None)
    
    # INSTEAD: Decrypt the Gemini API key if it exists
    if user_data.get("geminiApiKey"):
        try:
            decrypted_key = decrypt(user_data["geminiApiKey"])
            user_data["geminiApiKey"] = decrypted_key
        except Exception as e:
            print(f"Error decrypting API key: {e}")
            user_data["geminiApiKey"] = ""  # Set empty if decryption fails
    else:
        # If there's no Gemini API key in the database, set it to empty string
        user_data["geminiApiKey"] = ""
    
    # Return data directly without wrapper
    return {
        "user": user_data,
        "sessions": user_sessions,
        "stats": {
            "totalSessions": len(user_sessions),
            "totalQuestions": total_questions,
            "totalMaterials": await study_materials.count_documents({"user_id": user_id}),
            "avgQuestionsPerSession": len(user_sessions) and total_questions / len(user_sessions) or 0,
            "completionRate": await calculate_user_completion_rate(user_id),
            "lastLogin": user.get("updatedAt"),
            "joinedDate": user.get("createdAt")
        }
    }

async def get_user_activity_data(user_id: str, months: int = 6) -> List[Dict]:
    """Get user activity data for the last N months"""
    now = datetime.now(timezone.utc)
    activity_data = []
    
    for i in range(months - 1, -1, -1):
        month_start = datetime(now.year, now.month - i, 1, tzinfo=timezone.utc)
        if month_start.month <= 0:
            month_start = datetime(now.year - 1, month_start.month + 12, 1, tzinfo=timezone.utc)
        
        month_end = month_start.replace(
            month=month_start.month % 12 + 1,
            year=month_start.year + (month_start.month // 12)
        ) - timedelta(days=1)
        
        sessions_count = await sessions.count_documents({
            "user": ObjectId(user_id),
            "createdAt": {"$gte": month_start, "$lte": month_end}
        })
        
        questions_count = await questions.count_documents({
            "session.user": ObjectId(user_id),
            "createdAt": {"$gte": month_start, "$lte": month_end}
        })
        
        activity_data.append({
            "month": month_start.strftime("%b"),
            "sessions": sessions_count,
            "questions": questions_count
        })
    
    return activity_data

async def calculate_user_completion_rate(user_id: str) -> float:
    """Calculate user's session completion rate"""
    total_sessions = await sessions.count_documents({"user": ObjectId(user_id)})
    
    if total_sessions == 0:
        return 0.0
    
    # Assuming sessions have a 'status' field
    completed_sessions = await sessions.count_documents({
        "user": ObjectId(user_id),
        "status": "completed"
    })
    
    return round((completed_sessions / total_sessions) * 100, 1)

# ---------- Delete User (admin) ----------
async def admin_delete_user(
    request: Request,
    user_id: str,
    current_user: dict = Depends(protect)
):
    """Delete user and all associated data (admin only)"""
    await check_admin_access(current_user["id"])
    
    if user_id == current_user["id"]:
        return error_response(400, "Cannot delete your own account")
    
    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return error_response(404, "User not found")
    
    # Get user's sessions
    user_sessions = await sessions.find({"user": ObjectId(user_id)}).to_list(None)
    session_ids = [session["_id"] for session in user_sessions]
    
    # Delete questions
    await questions.delete_many({"session": {"$in": session_ids}})
    
    # Delete study materials
    await study_materials.delete_many({"user_id": user_id})
    
    # Delete sessions
    await sessions.delete_many({"_id": {"$in": session_ids}})
    
    # Delete user
    await users.delete_one({"_id": ObjectId(user_id)})
    
    return success_response("User and all associated data deleted successfully")

# ---------- Get Sessions Stats ----------
async def get_sessions_stats(
    request: Request,
    date_range: DateRangeRequest = None,
    current_user: dict = Depends(protect)
):
    """Get sessions statistics for admin"""
    await check_admin_access(current_user["id"])
    
    now = datetime.now(timezone.utc)
    
    # Determine date range
    if date_range and date_range.period:
        if date_range.period == "7d":
            start_date = now - timedelta(days=7)
        elif date_range.period == "30d":
            start_date = now - timedelta(days=30)
        elif date_range.period == "90d":
            start_date = now - timedelta(days=90)
        else:
            start_date = now - timedelta(days=7)
    else:
        start_date = now - timedelta(days=7)
    
    # Get total sessions
    total_sessions = await sessions.count_documents({})
    
    # Get completed sessions
    completed_sessions = await sessions.count_documents({"status": "completed"})
    
    # Get average duration
    pipeline = [
        {
            "$match": {
                "duration": {"$exists": True, "$ne": None}
            }
        },
        {
            "$group": {
                "_id": None,
                "avgDuration": {"$avg": "$duration"},
                "avgQuestions": {"$avg": {"$size": {"$ifNull": ["$questions", []]}}}
            }
        }
    ]
    
    avg_result = await sessions.aggregate(pipeline).to_list(1)
    
    # Get sessions by role distribution
    role_pipeline = [
        {
            "$group": {
                "_id": "$role",
                "count": {"$sum": 1}
            }
        },
        {
            "$sort": {"count": -1}
        }
    ]
    
    role_cursor = sessions.aggregate(role_pipeline)
    role_distribution = await serialize_cursor(role_cursor)
    
    return success_response(
        "Sessions statistics retrieved successfully",
        {
            "totalSessions": total_sessions,
            "completedSessions": completed_sessions,
            "inProgressSessions": total_sessions - completed_sessions,
            "avgDuration": round(avg_result[0]["avgDuration"], 1) if avg_result else 30.0,
            "avgQuestions": round(avg_result[0]["avgQuestions"], 1) if avg_result else 24.0,
            "roleDistribution": role_distribution,
            "completionRate": round((completed_sessions / total_sessions * 100), 1) if total_sessions > 0 else 0
        }
    )

# ---------- Get All Sessions (for admin) ----------
async def get_admin_sessions_list(
    request: Request,
    page: int = 1,
    limit: int = 20,
    search: str = "",
    status: str = "all",
    current_user: dict = Depends(protect)
):
    """Get all sessions for admin with filtering"""
    await check_admin_access(current_user["id"])
    
    skip = (page - 1) * limit
    
    # Build filter query
    filter_query = {}
    
    if search:
        filter_query["$or"] = [
            {"role": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    if status != "all":
        filter_query["status"] = status
    
    # Get sessions with user details
    pipeline = [
        {"$match": filter_query},
        {
            "$lookup": {
                "from": "users",
                "localField": "user",
                "foreignField": "_id",
                "as": "user_info"
            }
        },
        {
            "$unwind": "$user_info"
        },
        {
            "$project": {
                "_id": 1,
                "role": 1,
                "experience": 1,
                "description": 1,
                "status": 1,
                "duration": 1,
                "createdAt": 1,
                "updatedAt": 1,
                "user": {
                    "id": {"$toString": "$user_info._id"},
                    "name": "$user_info.name",
                    "email": "$user_info.email"
                },
                "questionCount": {"$size": {"$ifNull": ["$questions", []]}}
            }
        },
        {"$sort": {"createdAt": -1}},
        {"$skip": skip},
        {"$limit": limit}
    ]
    
    cursor = sessions.aggregate(pipeline)
    sessions_list = await serialize_cursor(cursor)
    
    # Format sessions list
    formatted_sessions = []
    for session in sessions_list:
        formatted_sessions.append({
            "id": session["_id"],
            "role": session.get("role", ""),
            "experience": session.get("experience", ""),
            "description": session.get("description", ""),
            "status": session.get("status", "active"),
            "duration": session.get("duration", 0),
            "createdAt": session.get("createdAt"),
            "updatedAt": session.get("updatedAt"),
            "user": session.get("user", {}),
            "questionCount": session.get("questionCount", 0)
        })
    
    # Get total count for pagination
    total = await sessions.count_documents(filter_query)
    
    return success_response(
        "Sessions list retrieved successfully",
        {
            "sessions": formatted_sessions,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }
    )

# ---------- Get User Statistics ----------
async def get_user_statistics():
    """Get user statistics for dashboard cards"""
    # User distribution by role
    users_by_role_pipeline = [
        {
            "$group": {
                "_id": "$role",
                "count": {"$sum": 1}
            }
        }
    ]
    
    role_cursor = users.aggregate(users_by_role_pipeline)
    users_by_role = await role_cursor.to_list(None)
    
    # Convert to dictionary
    role_distribution = {}
    total_users = 0
    for item in users_by_role:
        role = item["_id"] or "user"  # Default to user if role is None
        role_distribution[role] = item["count"]
        total_users += item["count"]
    
    # Ensure all roles exist
    for role in ["user", "admin", "moderator"]:
        if role not in role_distribution:
            role_distribution[role] = 0
    
    # Active users (active in last 7 days)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    active_users = await users.count_documents({
        "updatedAt": {"$gte": week_ago}
    })
    
    # New users this week
    new_users_this_week = await users.count_documents({
        "createdAt": {"$gte": week_ago}
    })
    
    # Calculate average metrics
    pipeline = [
        {
            "$lookup": {
                "from": "sessions",
                "localField": "_id",
                "foreignField": "user",
                "as": "user_sessions"
            }
        },
        {
            "$lookup": {
                "from": "questions",
                "localField": "_id",
                "foreignField": "session.user",
                "as": "user_questions"
            }
        },
        {
            "$lookup": {
                "from": "study_materials",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "user_materials"
            }
        },
        {
            "$project": {
                "sessionCount": {"$size": "$user_sessions"},
                "questionCount": {"$size": "$user_questions"},
                "materialCount": {"$size": "$user_materials"}
            }
        },
        {
            "$group": {
                "_id": None,
                "avgSessions": {"$avg": "$sessionCount"},
                "avgQuestions": {"$avg": "$questionCount"},
                "avgMaterials": {"$avg": "$materialCount"}
            }
        }
    ]
    
    avg_cursor = users.aggregate(pipeline)
    avg_results = await avg_cursor.to_list(1)
    
    avg_metrics = avg_results[0] if avg_results else {
        "avgSessions": 0,
        "avgQuestions": 0,
        "avgMaterials": 0
    }
    
    return {
        "totalUsers": total_users,
        "roleDistribution": role_distribution,
        "activeUsers": active_users,
        "inactiveUsers": total_users - active_users,
        "newUsersThisWeek": new_users_this_week,
        "avgSessionsPerUser": round(avg_metrics.get("avgSessions", 0), 1),
        "avgQuestionsPerUser": round(avg_metrics.get("avgQuestions", 0), 1),
        "avgMaterialsPerUser": round(avg_metrics.get("avgMaterials", 0), 1)
    }

# ---------- Create User (Admin) ----------
async def admin_create_user(
    request: Request,
    data: AdminCreateUserRequest,
    current_user: dict = Depends(protect)
):
    """Create new user (admin only)"""
    # Check admin access
    await check_admin_access(current_user["id"])
    
    # Check if email already exists
    existing = await users.find_one({"email": data.email})
    if existing:
        return error_response(400, "Email already registered")
    
    now = datetime.now(timezone.utc)
    
    # Handle join date
    join_date = now
    if data.joinDate:
        try:
            join_date = datetime.fromisoformat(data.joinDate.replace('Z', '+00:00'))
        except:
            join_date = now
    
    # Handle Gemini API key (optional)
    gemini_key_encrypted = None
    if data.geminiApiKey:
        try:
            # Validate the Gemini API key
            client = genai.Client(api_key=data.geminiApiKey)
            list(client.models.list())
            # Encrypt the key
            gemini_key_encrypted = encrypt(data.geminiApiKey)
        except Exception as e:
            print(f"Gemini API key validation failed: {e}")
            return error_response(400, "Invalid or unauthorized Gemini API key")
    
    # Create user document
    user_doc = {
        "name": data.name,
        "email": data.email,
        "password": hash_password(data.password),
        "role": data.role,
        "profileImageUrl": data.profileImageUrl,
        "notes": data.notes,
        "createdAt": join_date,
        "updatedAt": now,
        "isActive": data.isActive
    }
    
    # Add encrypted Gemini key if provided
    if gemini_key_encrypted:
        user_doc["geminiApiKey"] = gemini_key_encrypted
    
    # Insert user
    result = await users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Get created user
    created_user = await users.find_one({"_id": ObjectId(user_id)})
    
    # Mask Gemini key for response
    gemini_key_masked = None
    if created_user.get("geminiApiKey"):
        try:
            decrypted_key = decrypt(created_user["geminiApiKey"])
            gemini_key_masked = mask_key(decrypted_key)
        except Exception as e:
            print(f"Error decrypting API key: {e}")
            gemini_key_masked = None
    
    # Prepare response
    response_data = {
        "id": user_id,
        "name": created_user["name"],
        "email": created_user["email"],
        "profileImageUrl": created_user.get("profileImageUrl"),
        "role": created_user.get("role", "user"),
        "createdAt": created_user["createdAt"].isoformat(),
        "updatedAt": created_user["updatedAt"].isoformat(),
        "hasGeminiKey": bool(created_user.get("geminiApiKey")),
        "geminiKeyMasked": gemini_key_masked,
        "isActive": created_user.get("isActive", True),
        "notes": created_user.get("notes"),
    }
    
    # Send welcome email if requested
    if data.sendWelcomeEmail:
        # Add your email sending logic here
        print(f"Would send welcome email to: {data.email}")
    
    return success_response(
        "User created successfully",
        {
            "user": response_data,
            "welcomeEmailSent": data.sendWelcomeEmail
        }
    )

# ---------- Get User Statistics Endpoint ----------
async def get_user_stats_endpoint(
    request: Request,
    current_user: dict = Depends(protect)
):
    """Get user statistics for dashboard"""
    await check_admin_access(current_user["id"])
    
    stats = await get_user_statistics()
    
    # Return data directly without wrapper
    return {
        "totalUsers": stats.get("totalUsers", 0),
        "roleDistribution": stats.get("roleDistribution", {"user": 0, "admin": 0, "moderator": 0}),
        "activeUsers": stats.get("activeUsers", 0),
        "inactiveUsers": stats.get("inactiveUsers", 0),
        "newUsersThisWeek": stats.get("newUsersThisWeek", 0),
        "avgSessionsPerUser": stats.get("avgSessionsPerUser", 0),
        "avgQuestionsPerUser": stats.get("avgQuestionsPerUser", 0),
        "avgMaterialsPerUser": stats.get("avgMaterialsPerUser", 0)
    }

async def admin_delete_session(
    request: Request,
    session_id: str,
    current_user: dict = Depends(protect)
):
    """Delete session (admin only - bypasses ownership check)"""
    await check_admin_access(current_user["id"])
    
    session = await sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        return error_response(404, "Session not found")
    
    # Admin can delete any session, no ownership check
    
    # Delete questions first
    await questions.delete_many({"session": ObjectId(session_id)})
    
    # Delete session        
    await sessions.delete_one({"_id": ObjectId(session_id)})
    
    return success_response("Session deleted successfully")

async def admin_update_user(
    request: Request,
    user_id: str,
    data: dict,
    current_user: dict = Depends(protect)
):
    """Update user information (admin only)"""
    await check_admin_access(current_user["id"])
    
    if user_id == current_user["id"]:
        return error_response(400, "Cannot modify your own admin status")
    
    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return error_response(404, "User not found")
    
    update_fields = {"updatedAt": datetime.now(timezone.utc)}
    
    if data.get("name") is not None:
        update_fields["name"] = data["name"]
    
    if data.get("email") is not None and data["email"] != user["email"]:
        # Check if email already exists
        existing = await users.find_one({"email": data["email"], "_id": {"$ne": ObjectId(user_id)}})
        if existing:
            return error_response(400, "Email already in use")
        update_fields["email"] = data["email"]
    
    if data.get("role") is not None:
        if data["role"] not in ["user", "admin", "moderator"]:
            return error_response(400, "Invalid role")
        update_fields["role"] = data["role"]
    
    if data.get("isActive") is not None:
        update_fields["isActive"] = data["isActive"]
        if not data["isActive"]:
            # Mark as inactive by setting updatedAt far in the past
            update_fields["updatedAt"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
    
    # Handle Gemini API Key (if provided)
    if data.get("geminiApiKey") is not None:
        if data["geminiApiKey"]:  # If not empty string
            # VALIDATE THE NEW KEY HERE
            try:
                client = genai.Client(api_key=data["geminiApiKey"])
                list(client.models.list())
            except Exception as e:
                print(f"Gemini API key validation failed: {e}")
                return error_response(400, "Invalid or unauthorized Gemini API key")
            
            # Only save if validation passed
            encrypted_key = encrypt(data["geminiApiKey"])
            update_fields["geminiApiKey"] = encrypted_key
        else:
            # If empty string, remove the API key
            update_fields["geminiApiKey"] = None
    
    # Handle profile image URL
    if data.get("profileImageUrl") is not None:
        update_fields["profileImageUrl"] = data["profileImageUrl"]
    
    # Handle experience level
    if data.get("experience") is not None:
        update_fields["experience"] = data["experience"]
    
    # Handle notes
    if data.get("notes") is not None:
        update_fields["notes"] = data["notes"]
    
    await users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_fields}
    )
    
    # Get updated user WITH the Gemini key
    updated_user = await users.find_one(
        {"_id": ObjectId(user_id)}, 
        {"password": 0}  # Only remove password, NOT geminiApiKey
    )
    
    # Decrypt the Gemini key for the response
    if updated_user.get("geminiApiKey"):
        try:
            decrypted_key = decrypt(updated_user["geminiApiKey"])
            updated_user["geminiApiKey"] = decrypted_key
        except Exception as e:
            print(f"Error decrypting API key: {e}")
            updated_user["geminiApiKey"] = ""  # Set empty if decryption fails
    
    # Convert datetime objects to ISO format strings before serializing
    for key, value in updated_user.items():
        if isinstance(value, datetime):
            updated_user[key] = value.isoformat()
    
    return success_response(
        "User updated successfully",
        {"user": serialize_doc(updated_user)}
    )
