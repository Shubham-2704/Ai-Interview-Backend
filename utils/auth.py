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
    Verify Google OAuth token and return user info
    """
    try:
        async with httpx.AsyncClient() as client:
            # First, verify the token with Google
            token_info_response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            )
            
            if token_info_response.status_code != 200:
                return None
            
            token_info = token_info_response.json()
            
            # Verify the audience (client ID)
            if token_info.get("aud") != GOOGLE_CLIENT_ID:
                return None
            
            # Get additional user info from Google People API
            headers = {"Authorization": f"Bearer {token}"}
            user_info_response = await client.get(
                "https://people.googleapis.com/v1/people/me",
                params={"personFields": "names,emailAddresses,photos"},
                headers=headers
            )
            
            if user_info_response.status_code != 200:
                # If People API fails, use info from token
                return {
                    "email": token_info.get("email"),
                    "name": token_info.get("name"),
                    "picture": token_info.get("picture"),
                    "sub": token_info.get("sub"),
                    "email_verified": token_info.get("email_verified", False)
                }
            
            user_info = user_info_response.json()
            
            # Extract user data
            email = None
            name = None
            picture = None
            
            if "emailAddresses" in user_info and user_info["emailAddresses"]:
                email = user_info["emailAddresses"][0].get("value")
            
            if "names" in user_info and user_info["names"]:
                name = user_info["names"][0].get("displayName")
            
            if "photos" in user_info and user_info["photos"]:
                picture = user_info["photos"][0].get("url")
            
            return {
                "email": email or token_info.get("email"),
                "name": name or token_info.get("name"),
                "picture": picture or token_info.get("picture"),
                "sub": token_info.get("sub"),
                "email_verified": token_info.get("email_verified", False)
            }
            
    except Exception as e:
        print(f"Google token verification error: {e}")
        return None
