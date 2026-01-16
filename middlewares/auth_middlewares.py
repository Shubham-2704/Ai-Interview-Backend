from fastapi import Request, HTTPException
from utils.auth import decode_token
from config.database import database
from bson import ObjectId

users = database["users"]

# Protect Middleware (like Node.js protect)
async def protect(request: Request):
    auth = request.headers.get("Authorization")

    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authorized")

    token = auth.split(" ")[1]

    try:
        decoded = decode_token(token)
        user_id = decoded["id"]
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Fetch full user from MongoDB
    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Store full user in request
    request.state.user = {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
    }

    return request.state.user
