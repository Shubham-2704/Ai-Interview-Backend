from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class DashboardStatsResponse(BaseModel):
    totalUsers: int
    totalSessions: int
    totalQuestions: int
    totalStudyMaterials: int
    activeUsersToday: int
    avgSessionTime: float
    sessionsPerDay: List[dict]
    topUsers: List[dict]
    recentUsers: List[dict]
    systemStatus: dict
    revenue: Optional[float] = None
    conversionRate: Optional[float] = None

class DateRangeRequest(BaseModel):
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    period: Optional[str] = "7d"  # 7d, 30d, 90d, year

class AdminCreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "user"
    profileImageUrl: Optional[str] = None
    isActive: bool = True
    sendWelcomeEmail: bool = True
    geminiApiKey: Optional[str] = None
    notes: Optional[str] = None
    joinDate: Optional[str] = None

