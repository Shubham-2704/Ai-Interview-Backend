from config.database import database
from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime, timedelta
from utils.helper import *
from controllers.ai_controller import*

from models.question_model import (
    AddQuestionsRequest,
    UpdateNoteRequest,
)

users = database["users"]
sessions = database["sessions"]
questions = database["questions"]

# ---------- Add questions to a session ----------
async def add_questions_to_session_service(body: AddQuestionsRequest, user):
    session = await sessions.find_one({"_id": ObjectId(body.sessionId)})

    if not session:
        raise HTTPException(404, "Session not found")

    # create new questions
    docs = []
    for q in body.questions:
        doc = {
            "session": ObjectId(body.sessionId),
            "question": q.question,
            "answer": q.answer,
            "isPinned": False,
            "note": "",
            "createdAt": datetime.now(),
            "updatedAt": datetime.now(),
        }
        docs.append(doc)

    result = await questions.insert_many(docs)

    # map inserted ids
    inserted_ids = list(result.inserted_ids)

    # push ids to session.questions
    await sessions.update_one(
        {"_id": ObjectId(body.sessionId)},
        {"$push": {"questions": {"$each": inserted_ids}}}
    )

    # return documents with id strings
    for i, _id in enumerate(inserted_ids):
        docs[i]["_id"] = _id  # keep _id, let utils convert
        docs[i] = serialize_doc(docs[i])


    return {
        "success": True,
        "message": "Questions added to session successfully",
        "createdQuestions": docs,
    }


# ---------- Pin / Unpin question ----------
async def toggle_pin_question_service(question_id: str):
    q = await questions.find_one({"_id": ObjectId(question_id)})

    if not q:
        raise HTTPException(404, "Question not found")

    new_pin_state = not q.get("isPinned", False)

    await questions.update_one(
        {"_id": ObjectId(question_id)},
        {"$set": {"isPinned": new_pin_state}}
    )

    q["isPinned"] = new_pin_state

    return {"success": True, "question": serialize_doc(q)}


# ---------- Update Question Note ----------
async def update_question_note_service(question_id: str, body: UpdateNoteRequest):
    q = await questions.find_one({"_id": ObjectId(question_id)})

    if not q:
        raise HTTPException(404, "Question not found")

    note = body.note or ""

    await questions.update_one(
        {"_id": ObjectId(question_id)},
        {"$set": {"note": note}}
    )

    q["note"] = note

    return {"success": True, "question": serialize_doc(q)}

