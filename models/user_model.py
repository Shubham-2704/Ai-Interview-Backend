from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timezone 

class Timestamps(BaseModel):
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    profileImageUrl: Optional[str] = None
    adminInviteToken: Optional[str] = None
    geminiApiKey: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    profileImageUrl: Optional[str]
    token: str
    createdAt: datetime
    updatedAt: datetime
    hasGeminiKey: bool = False
    geminiKeyMasked: Optional[str] = None

class UpdateGeminiKey(BaseModel):
    apiKey: str
