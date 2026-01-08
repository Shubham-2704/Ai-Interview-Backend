from fastapi import Request, HTTPException
from fastapi.responses import FileResponse
from bson import ObjectId
from config.database import database
import tempfile
from utils.pdf_service import generate_pdf  

users = database["users"]
sessions = database["sessions"]
questions = database["questions"]

async def download_session_pdf(session_id: str, request: Request):
    user = request.state.user

    session = await sessions.find_one({
        "_id": ObjectId(session_id),
        "user": ObjectId(user["id"])
    })

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    qs = await questions.find(
        {"session": ObjectId(session_id)}
    ).sort("createdAt", 1).to_list(None)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

    # Call the generate_pdf function
    await generate_pdf(session, qs, tmp.name)

    return FileResponse(
        tmp.name,
        media_type="application/pdf",
        filename=f"{session['role']}-interview.pdf"
    )

