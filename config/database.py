import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager

load_dotenv()

MONGO_DETAILS = os.getenv("MONGO_URI")

client = AsyncIOMotorClient(MONGO_DETAILS)
database = client["ai-interview-platform"]
users = database["users"]

@asynccontextmanager
async def lifespan(app):
    print("✅ Connected to MongoDB!")
    await users.create_index("email", unique=True)
    await users.create_index("googleId", unique=True, sparse=True)

    yield
    client.close()
    print("❌ MongoDB connection closed.")

