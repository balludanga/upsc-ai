from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import ask, auth, quiz, study, mains

Base.metadata.create_all(bind=engine)

app = FastAPI(title="UPSC Study Buddy API")

# Allow your mobile app to call this from anywhere during development.
# Tighten this to your app's actual origin(s) before a real public launch.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ask.router)
app.include_router(quiz.router)
app.include_router(study.router)
app.include_router(mains.router)


@app.get("/health")
def health():
    return {"status": "ok"}
