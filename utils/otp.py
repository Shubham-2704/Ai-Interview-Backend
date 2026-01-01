import random
from datetime import datetime, timedelta, timezone

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def otp_expiry(minutes: int = 5) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)