from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.database import lifespan
from routes.auth_routes import router as auth_router
from routes.session_routes import router as session_router
from routes.ai_routes import router as ai_router
from routes.question_routes import router as question_router
from starlette.staticfiles import StaticFiles


app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include Routers
app.include_router(auth_router)
app.include_router(session_router)
app.include_router(ai_router)
app.include_router(question_router)


@app.get("/")
async def root():
    return {"message": "API running successfully"}