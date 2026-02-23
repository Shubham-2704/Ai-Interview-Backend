import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import httpx
from typing import Optional, Dict

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


def generate_token(user_id: str):
    payload = {
        "id": user_id,
        "exp": datetime.now() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

async def verify_google_token(token: str) -> Optional[Dict]:
    """
    Verify Google OAuth access token and return user info
    """
    try:
        async with httpx.AsyncClient() as client:
            # First, verify the token is valid and get basic info
            token_info_response = await client.get(
                f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={token}"
            )
            
            if token_info_response.status_code != 200:
                return None
            
            token_info = token_info_response.json()
            
            # Verify the audience (client ID)
            if token_info.get("audience") != GOOGLE_CLIENT_ID:
                return None
            
            # Get user info from Google UserInfo endpoint (this returns profile data)
            headers = {"Authorization": f"Bearer {token}"}
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers=headers
            )
            
            if user_info_response.status_code != 200:
                print(f"Userinfo endpoint failed: {user_info_response.status_code}")
                return None
            
            user_info = user_info_response.json()
            
            # The userinfo endpoint returns all the data we need directly
            return {
                "email": user_info.get("email"),
                "name": user_info.get("name"),
                "picture": user_info.get("picture"),
                "sub": user_info.get("id"),  # Google user ID
                "email_verified": user_info.get("verified_email", False)
            }
            
    except Exception as e:
        print(f"Google token verification error: {e}")
        return None