from fastapi import HTTPException, Request
from datetime import datetime
from bson import ObjectId
from utils.helper import *
from models.session_model import *
from config.database import database

sessions = database["sessions"]
questions = database["questions"]

# Create a new session
async def create_new_session(request: Request, data: SessionCreate):
    user = request.state.user
    
    now = datetime.now()

    # 1️⃣ Create session document
    session_doc = {
        "user": ObjectId(user["id"]),
        "role": data.role,
        "experience": data.experience,
        "topicsToFocus": data.topicsToFocus,
        "description": data.description,
        "questions": [],
        "createdAt": now,
        "updatedAt": now,
    }

    session_result = await sessions.insert_one(session_doc)
    session_id = session_result.inserted_id

    question_ids = []

    # 2️⃣ Insert questions (if provided)
    if data.questions:
        for q in data.questions:
            question_doc = {
                "session": session_id,
                "question": q.question,
                "answer": q.answer,
                "isPinned": q.isPinned,
                "createdAt": now,
                "updatedAt": now,
            }

            q_result = await questions.insert_one(question_doc)
            question_ids.append(q_result.inserted_id)

        # attach ids to session
        await sessions.update_one(
            {"_id": session_id},
            {"$set": {"questions": question_ids}}
        )

    # 3️⃣ Prepare API response (map _id → id)
    response = {
        "id": str(session_id),
        "user": user["id"],
        "role": data.role,
        "experience": data.experience,
        "topicsToFocus": data.topicsToFocus,
        "description": data.description,
        "questions": [str(qid) for qid in question_ids],
        "createdAt": now,
        "updatedAt": now,
    }

    return response

# Get my sessions
async def get_my_sessions(request: Request):
    user = request.state.user

    cursor = sessions.find(
        {"user": ObjectId(user["id"])}
    ).sort("createdAt", -1)

    results = []
    async for doc in cursor:
        q_cursor = questions.find({"_id": {"$in": doc.get("questions", [])}})
        q_list = await serialize_cursor(q_cursor)

        doc = serialize_doc(doc)
        doc["questions"] = q_list
        results.append(doc)

    return results

# Get session by id
async def get_session_by_id(request: Request, session_id: str):

    session = await sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        raise HTTPException(404, "Session not found")

    q_cursor = questions.find({"session": ObjectId(session_id)}).sort(
        [("isPinned", -1), ("createdAt", 1)]
    )

    session = serialize_doc(session)
    session["questions"] = await serialize_cursor(q_cursor)

    return {"success": True, "session": session}

# Delete session by id
async def delete_session(request: Request, session_id: str):
    user = request.state.user

    session = await sessions.find_one({"_id": ObjectId(session_id)})

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check ownership
    if str(session["user"]) != user["id"]:
        raise HTTPException(
            status_code=401,
            detail="Not authorized to delete this session"
        )

    # delete questions first
    await questions.delete_many({"session": ObjectId(session_id)})

    # delete session        
    await sessions.delete_one({"_id": ObjectId(session_id)})

    return {
        "success": True,
        "message": "Session deleted successfully"
    }
