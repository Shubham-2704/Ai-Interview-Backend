from config.database import database
from fastapi import Request, Depends
from middlewares.auth_middlewares import protect
from controllers.settings_controller import *
from models.user_model import *
from utils.hash import hash_password, verify_password
from utils.auth import generate_token, verify_google_token
from utils.helper import error_response
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from utils.encryption import encrypt, decrypt, mask_key
from google import genai
from utils.helper import *
from utils.otp import *
from utils.email import *

users = database["users"]
reset_otps = database["password_reset_otps"]
reset_limits = database["password_reset_limits"]

# Register User
async def register_user(data: UserCreate):
    user_exists = await users.find_one({"email": data.email})
    if user_exists:
        return error_response(400, "User with this email already exists")

    now = datetime.now(timezone.utc)

    gemini_key_encrypted = None
    role = "user"

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
        "role": role, 
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

    try:
        # Get settings to check if welcome email is enabled
        settings = await get_system_settings()
        if settings.get("send_welcome_email", True):
            # Send welcome email in background (don't block response)
            import asyncio
            asyncio.create_task(
                send_welcome_email_async(
                    to_email=data.email,
                    user_name=data.name
                )
            )
    except Exception as e:
        print(f"Error scheduling welcome email: {e}")
        # Don't fail registration if email fails

    return UserResponse(
        id=user_id,
        name=data.name,
        email=data.email,
        profileImageUrl=data.profileImageUrl,
        token=generate_token(user_id),
        createdAt=now,
        updatedAt=now,
        hasGeminiKey=bool(gemini_key_encrypted),
        geminiKeyMasked=masked,
        role=role
    )

# Google signup
async def google_signup(data: GoogleSignupRequest):
    """Handle Google signup/login"""
    # ✅ First, check if registration is allowed
    settings = await get_system_settings()
    
    # Verify Google token
    google_user = await verify_google_token(data.token)
    
    if not google_user:
        return error_response(401, "Invalid Google token")
    
    if not google_user.get("email_verified", False):
        return error_response(400, "Email not verified by Google")
    
    email = google_user["email"]
    name = google_user.get("name", "").strip()
    
    if not name:
        # Extract name from email if not provided
        name = email.split('@')[0]
    
    # Check if user already exists
    existing_user = await users.find_one({"email": email})
    
    now = datetime.now(timezone.utc)
    
    if existing_user:
        # ✅ EXISTING USER: Always allow login
        await users.update_one(
            {"_id": existing_user["_id"]},
            {"$set": {"updatedAt": now}}
        )
        
        gemini_key = existing_user.get("geminiApiKey")
        masked = None
        
        if gemini_key:
            try:
                masked = mask_key(decrypt(gemini_key))
            except:
                masked = None
        
        role = "user"
        if existing_user.get("role") == "admin":
            role = "admin"
        
        return UserResponse(
            id=str(existing_user["_id"]),
            name=existing_user["name"],
            email=existing_user["email"],
            profileImageUrl=existing_user.get("profileImageUrl") or google_user.get("picture"),
            token=generate_token(str(existing_user["_id"])),
            createdAt=existing_user.get("createdAt", now),
            updatedAt=now,
            hasGeminiKey=bool(gemini_key),
            geminiKeyMasked=masked,
            role=role
        )
    else:
        # ✅ NEW USER: Check if registration is allowed
        if not settings.get("allow_registration", True):
            return error_response(403, "New registrations are currently closed. Please try again later.")
        
        # Create new user
        new_user = {
            "name": name,
            "email": email,
            "password": None,  # No password for Google users
            "profileImageUrl": google_user.get("picture"),
            "authProvider": "google",
            "googleId": google_user.get("sub"),
            "role": "user",
            "emailVerified": True,  # Google already verified
            "createdAt": now,
            "updatedAt": now,
        }
        
        result = await users.insert_one(new_user)
        user_id = str(result.inserted_id)

        try:
            if settings.get("send_welcome_email", True):
                # Send welcome email in background
                import asyncio
                asyncio.create_task(
                    send_welcome_email_async(
                        to_email=email,
                        user_name=name
                    )
                )
        except Exception as e:
            print(f"Error scheduling welcome email for Google user: {e}")
        
        return UserResponse(
            id=user_id,
            name=name,
            email=email,
            profileImageUrl=google_user.get("picture"),
            token=generate_token(user_id),
            createdAt=now,
            updatedAt=now,
            hasGeminiKey=False,
            geminiKeyMasked=None,
            role="user"
        )
    
# Verify Admin Token
async def verify_admin_token(token_data: AdminTokenVerify):
    admin_fixed_token = os.getenv("ADMIN_FIXED_TOKEN")
    
    if not admin_fixed_token:
        return error_response(500, "Admin token not configured")
    if token_data.adminToken != admin_fixed_token:
        return error_response(403, "Invalid admin token")
    
    return success_response("Admin token verified")

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
    
    role = "user"
    if user.get("role") == "admin":
        role = "admin"

    return UserResponse(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        profileImageUrl=user.get("profileImageUrl"),
        token=generate_token(str(user["_id"])),
        createdAt=user.get("createdAt", now),
        updatedAt=now,
        hasGeminiKey=bool(gemini_key),
        geminiKeyMasked=masked,
        role=role
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
        "geminiKeyMasked": masked,
        "role": user.get("role")
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
        "geminiKeyMasked": masked,
        "role": updated_user.get("role")
    }

# Forgot Password - Step 1: Request OTP
async def forgot_password(data: ForgotPasswordRequest):
    user = await users.find_one({"email": data.email})
    if not user:
        return error_response(404, "User not found")

    now = datetime.now(timezone.utc)

    # ✅ GET SETTINGS
    settings = await get_system_settings()
    max_attempts = settings.get("max_password_reset_attempts", 3)
    block_duration_hours = settings.get("password_reset_block_duration_hours", 1)
    otp_expiry_minutes = settings.get("password_reset_otp_expiry_minutes", 5)
    block_duration = timedelta(hours=block_duration_hours)

    # 🛑 BLOCK CHECK (FROM reset_limits)
    limit = await reset_limits.find_one({"userId": user["_id"]})
    if limit and limit.get("blockedUntil"):
        blocked_until = limit["blockedUntil"]
        if blocked_until.tzinfo is None:
            blocked_until = blocked_until.replace(tzinfo=timezone.utc)

        if now < blocked_until:
            minutes_left = int((blocked_until - now).total_seconds() / 60)
            hours_left = minutes_left // 60
            minutes_remainder = minutes_left % 60

            if hours_left > 0:
                return error_response(
                    429,
                    f"Too many attempts. Try again after {hours_left} hours"
                )
            else:
                return error_response(
                    429,
                    f"Too many attempts. Try again after {minutes_remainder} minutes"
                )

    # 🔐 GENERATE OTP
    otp = generate_otp()

    # 🔑 STORE OTP (OTP COLLECTION ONLY)
    await reset_otps.update_one(
        {"userId": user["_id"]},
        {"$set": {
            "userId": user["_id"],
            "email": user["email"],
            "otp": hash_password(otp),
            "expiresAt": now + timedelta(minutes=otp_expiry_minutes),
            "createdAt": now
        }},
        upsert=True
    )

    # 📧 SEND EMAIL
    send_otp_email(
        to_email=user["email"],
        user_name=user["name"],
        otp=otp,
        expiry_minutes=otp_expiry_minutes
    )

    return {
        "message": "OTP sent to your email",
        "expiresIn": otp_expiry_minutes * 60
    }

# Forgot Password - Step 2: Verify OTP
async def verify_reset_otp(data: VerifyOtpRequest):
    settings = await get_system_settings()
    max_attempts = settings.get("max_password_reset_attempts", 3)
    block_duration_hours = settings.get("password_reset_block_duration_hours", 1)
    block_duration = timedelta(hours=block_duration_hours)

    record = await reset_otps.find_one({"email": data.email})
    if not record:
        return error_response(400, "OTP expired or invalid")

    now = datetime.now(timezone.utc)

    # 🛑 BLOCK CHECK (FROM reset_limits)
    limit = await reset_limits.find_one({"userId": record["userId"]})
    if limit and limit.get("blockedUntil"):
        blocked_until = limit["blockedUntil"]
        if blocked_until.tzinfo is None:
            blocked_until = blocked_until.replace(tzinfo=timezone.utc)

        if now < blocked_until:
            minutes_left = int((blocked_until - now).total_seconds() / 60)
            hours_left = minutes_left // 60
            minutes_remainder = minutes_left % 60

            if hours_left > 0:
                return error_response(429, f"Try again after {hours_left} hours")
            else:
                return error_response(429, f"Try again after {minutes_remainder} minutes")

    # ❌ WRONG OTP
    if not verify_password(data.otp, record["otp"]):
        attempts = (limit.get("attempts", 0) if limit else 0) + 1

        # 🔒 MAX ATTEMPTS REACHED
        if attempts >= max_attempts:
            await reset_limits.update_one(
                {"userId": record["userId"]},
                {"$set": {
                    "attempts": attempts,
                    "blockedUntil": now + block_duration,
                    "updatedAt": now
                }},
                upsert=True
            )

            return error_response(
                400,
                f"Maximum attempts ({max_attempts}) reached. Account blocked for {block_duration_hours} hours"
            )

        # 🔁 UPDATE ATTEMPTS
        await reset_limits.update_one(
            {"userId": record["userId"]},
            {"$set": {
                "attempts": attempts,
                "updatedAt": now
            }},
            upsert=True
        )

        remaining = max_attempts - attempts
        return error_response(
            400,
            f"Invalid OTP. You have {remaining} attempt(s) remaining"
        )

    # ✅ OTP CORRECT → CLEAR LIMITS
    await reset_limits.delete_one({"userId": record["userId"]})

    return success_response("OTP verified successfully")

# Forgot Password - Step 3: Reset Password
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
