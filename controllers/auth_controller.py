from config.database import database
from fastapi import Request, Depends
from middlewares.auth_middlewares import protect
from models.user_model import *
from utils.hash import hash_password, verify_password
from utils.auth import generate_token
from utils.helper import error_response
from datetime import datetime, timezone
from bson import ObjectId
from utils.encryption import encrypt, decrypt, mask_key
import google.generativeai as genai


users = database["users"]

# Register User
async def register_user(data: UserCreate):
    user_exists = await users.find_one({"email": data.email})
    if user_exists:
        return error_response(400, "User with this email already exists")

    now = datetime.now(timezone.utc)

    gemini_key_encrypted = None

    # If user provided a Gemini key at signup, validate & encrypt it
    if data.geminiApiKey:
        try:
            genai.configure(api_key=data.geminiApiKey)
            list(genai.list_models())   # basic validation call
        except Exception:
            return error_response(400, "Invalid or unauthorized Gemini API key")

        gemini_key_encrypted = encrypt(data.geminiApiKey)


    new_user = {
        "name": data.name,
        "email": data.email,
        "password": hash_password(data.password),
        "profileImageUrl": data.profileImageUrl,
        "createdAt": now,
        "updatedAt": now
    }

    if gemini_key_encrypted:
        new_user["geminiApiKey"] = gemini_key_encrypted

    result = await users.insert_one(new_user)
    user_id = str(result.inserted_id)

    masked = (
        mask_key(data.geminiApiKey)
        if data.geminiApiKey
        else None
    )


    return UserResponse(
        id=user_id,
        name=data.name,
        email=data.email,
        profileImageUrl=data.profileImageUrl,
        token=generate_token(user_id),
        createdAt=now,
        updatedAt=now,
        hasGeminiKey=bool(gemini_key_encrypted),
        geminiKeyMasked=masked
    )


# Login User
async def login_user(data: UserLogin):
    user = await users.find_one({"email": data.email})
    if not user:
        return error_response(400, "Invalid email or password")

    if not verify_password(data.password, user["password"]):
        return error_response(400, "Invalid email or password")

    now = datetime.now(timezone.utc)

    # Update last login timestamp if desired
    await users.update_one(
        {"_id": user["_id"]},
        {"$set": {"updatedAt": now}}
    )
    gemini_key = user.get("geminiApiKey")
    masked = None

    if gemini_key:
        try:
            masked = mask_key(decrypt(gemini_key))
        except:
            masked = None

    return UserResponse(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        profileImageUrl=user.get("profileImageUrl"),
        token=generate_token(str(user["_id"])),
        createdAt=user.get("createdAt", now),
        updatedAt=now,
        hasGeminiKey=bool(gemini_key),
        geminiKeyMasked=masked
    )

# Get User Profile
async def get_profile(request: Request, user_data = Depends(protect)):
    user_id = request.state.user["id"]

    user = await users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        return error_response(404, "User not found")

    gemini_key = user.get("geminiApiKey")
    masked = None

    if gemini_key:
        try:
            masked = mask_key(decrypt(gemini_key))
        except:
            masked = None   # decryption failed → don't break profile

    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "profileImageUrl": user.get("profileImageUrl"),
        "createdAt": user.get("createdAt"),
        "updatedAt": user.get("updatedAt"),
        "hasGeminiKey": bool(gemini_key),
        "geminiKeyMasked": masked
    }

# Update User Profile
async def update_profile(request: Request, data: UserProfileUpdate, user_data = Depends(protect)):
    user_id = request.state.user["id"]

    user_obj = await users.find_one({"_id": ObjectId(user_id)})
    if not user_obj:
        return error_response(404, "User not found")

    update_fields = {"updatedAt": datetime.now(timezone.utc)}

    if data.name is not None:
        update_fields["name"] = data.name
    if data.email is not None and data.email != user_obj["email"]:
        # Check if new email already exists
        if await users.find_one({"email": data.email, "_id": {"$ne": ObjectId(user_id)}}):
            return error_response(400, "Email already registered")
        update_fields["email"] = data.email
    if data.profileImageUrl is not None:
        update_fields["profileImageUrl"] = data.profileImageUrl

    await users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_fields}
    )

    updated_user = await users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    
    gemini_key = updated_user.get("geminiApiKey")
    masked = None

    if gemini_key:
        try:
            masked = mask_key(decrypt(gemini_key))
        except:
            masked = None

    return {
        "id": str(updated_user["_id"]),
        "name": updated_user["name"],
        "email": updated_user["email"],
        "profileImageUrl": updated_user.get("profileImageUrl"),
        "createdAt": updated_user.get("createdAt"),
        "updatedAt": updated_user.get("updatedAt"),
        "hasGeminiKey": bool(gemini_key),
        "geminiKeyMasked": masked
    }
