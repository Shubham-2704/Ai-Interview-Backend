from config.database import database
from fastapi import Request, Depends
from middlewares.auth_middlewares import protect
from models.user_model import *
from utils.hash import hash_password, verify_password
from utils.auth import generate_token
from utils.helper import error_response
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from utils.encryption import encrypt, decrypt, mask_key
from google import genai
from utils.helper import *
from utils.otp import *
from utils.email import *

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
            client = genai.Client(api_key=data.geminiApiKey)
            list(client.models.list())   # basic validation call
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
            return error_response(400, "Email already registered, use a different email.")
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

reset_otps = database["password_reset_otps"]
async def forgot_password(data: ForgotPasswordRequest):
    user = await users.find_one({"email": data.email})
    if not user:
        return error_response(404, "User not found")

    now = datetime.now(timezone.utc)

    # 🛑 BLOCK CHECK
    existing = await reset_otps.find_one({"userId": user["_id"]})
    if existing and existing.get("blockedUntil"):
        blocked_until = existing["blockedUntil"]
        if blocked_until.tzinfo is None:
            blocked_until = blocked_until.replace(tzinfo=timezone.utc)

        if now < blocked_until:
            minutes_left = int((blocked_until - now).total_seconds() / 60)
            return error_response(
                429,
                f"Too many attempts. Try again after {minutes_left} minutes"
            )

    otp = generate_otp()
    now = datetime.now(timezone.utc)

    await reset_otps.update_one(
        {"userId": user["_id"]},
        {
            "$set": {
                "userId": user["_id"],
                "email": user["email"],
                "otp": hash_password(otp),
                "expiresAt": now + timedelta(minutes=5),  # ✅ 5 MIN
                "attempts": 0,
                "blockedUntil": None,
                "createdAt": now
            }
        },
        upsert=True
    )

    send_otp_email(
        to_email=user["email"],
        user_name=user["name"],
        otp=otp,
        expiry_minutes=5
    )

    return {
        "message": "OTP sent to your email",
        "expiresIn": 300  # seconds
    }

MAX_ATTEMPTS = 3
BLOCK_DURATION = timedelta(hours=1)

async def verify_reset_otp(data: VerifyOtpRequest):
    record = await reset_otps.find_one({"email": data.email})
    if not record:
        return error_response(400, "OTP expired or invalid")

    now = datetime.now(timezone.utc)

    # 🛑 BLOCK CHECK
    blocked_until = record.get("blockedUntil")
    if blocked_until:
        if blocked_until.tzinfo is None:
            blocked_until = blocked_until.replace(tzinfo=timezone.utc)

        if now < blocked_until:
            minutes_left = int((blocked_until - now).total_seconds() / 60)
            return error_response(
                429,
                f"Try again after {minutes_left} minutes"
            )

    # ❌ WRONG OTP
    if not verify_password(data.otp, record["otp"]):
        attempts = record.get("attempts", 0) + 1
        update = {"attempts": attempts}

        if attempts >= MAX_ATTEMPTS:
            update["blockedUntil"] = now + BLOCK_DURATION


        await reset_otps.update_one(
            {"_id": record["_id"]},
            {"$set": update}
        )

        return error_response(400, "Invalid OTP")

    return success_response("OTP verified successfully")

async def reset_password(data: ResetPasswordRequest):
    record = await reset_otps.find_one({"email": data.email})
    user = await users.find_one({"email": data.email})
    if verify_password(data.newPassword, user["password"]):
        return error_response(400, "New password cannot be the same as the old password")
    await users.update_one(
        {"email": data.email},
        {"$set": {
            "password": hash_password(data.newPassword),
            "updatedAt": datetime.now(timezone.utc)
        }}
    )

    # 🧹 DELETE OTP RECORD
    await reset_otps.delete_one({"_id": record["_id"]})

    return success_response("Password reset successfully")
