import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.chat import router as chat_router
from routes.session import router as session_router

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(dotenv_path=ENV_PATH, override=False)

app = FastAPI(title="FocalPoint API", version="1.0.0")

@app.on_event("startup")
def startup():
    try:
        from db.facts import ensure_vector_index
        ensure_vector_index()
    except Exception as e:
        print(f"[startup] Vector index setup failed (non-fatal): {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(session_router)

@app.get("/health")
def health():
    return {"status": "ok"}
