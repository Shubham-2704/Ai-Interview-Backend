import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager

load_dotenv()

MONGO_DETAILS = os.getenv("MONGO_URI")

client = AsyncIOMotorClient(MONGO_DETAILS)
# database = client["ai-interview-platform"]       #local
database = client["intervia"]                   #atlas
users = database["users"]

@asynccontextmanager
async def lifespan(app):
    print("✅ Connected to MongoDB!")
    await users.create_index("email", unique=True)
    await users.create_index("googleId", unique=True, sparse=True)
    await database["password_reset_otps"].create_index("expiresAt", expireAfterSeconds=0)
    await database["password_reset_limits"].create_index("userId", unique=True)
    await database["password_reset_limits"].create_index("blockedUntil", expireAfterSeconds=0)

    yield
    client.close()
    print("❌ MongoDB connection closed.")

