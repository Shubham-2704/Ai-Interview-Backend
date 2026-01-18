from pydantic import BaseModel
from typing import List, Optional

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

