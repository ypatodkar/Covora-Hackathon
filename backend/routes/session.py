from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from models import SaveProfileRequest, SaveSessionRequest, SessionEndRequest, UserProfileOut
from db.mongo import get_db
from db.users import get_user, update_user, DEFAULT_PROFILE
from db.episodes import get_session_episodes
from db.sessions import close_session
from services.meta_agent import run_meta_agent

router = APIRouter()

@router.get("/profile", response_model=UserProfileOut)
async def get_profile(user_id: str = Query(...)):
    user = get_user(user_id)
    return UserProfileOut(
        complexity_score=user.get("complexity_score", 5),
        preferred_format=user.get("preferred_format", "prose"),
    )

@router.post("/profile", response_model=UserProfileOut)
async def save_profile(req: SaveProfileRequest):
    allowed = {"complexity_score", "preferred_format"}
    updates = {key: value for key, value in req.profile.items() if key in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="profile must include complexity_score or preferred_format")
    update_user(req.user_id, updates)
    user = get_user(req.user_id)
    return UserProfileOut(
        complexity_score=user.get("complexity_score", 5),
        preferred_format=user.get("preferred_format", "prose"),
    )

@router.get("/sessions")
async def list_sessions(user_id: str = Query(...)):
    db = get_db()
    return list(
        db.sessions
        .find(
            {"user_id": user_id, "messages": {"$exists": True}},
            {"_id": 0, "id": 1, "title": 1, "messages": 1, "created_at": 1, "updated_at": 1},
        )
        .sort("updated_at", -1)
        .limit(20)
    )

@router.post("/sessions")
async def save_session(req: SaveSessionRequest):
    session_id = req.session.get("id")
    title = req.session.get("title")
    messages = req.session.get("messages")
    if not session_id or not title or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="session must include id, title, and messages")

    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.sessions.update_one(
        {"_id": session_id, "user_id": req.user_id},
        {
            "$set": {
                "id": session_id,
                "title": title,
                "messages": messages,
                "updated_at": now,
            },
            "$setOnInsert": {
                "_id": session_id,
                "user_id": req.user_id,
                "created_at": now,
                "started_at": now,
                "ended_at": None,
                "turns": 0,
                "avg_reward": None,
                "meta_agent_run": False,
                "meta_insights": [],
            },
        },
        upsert=True,
    )
    return {"id": session_id}

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = Query(...)):
    db = get_db()
    result = db.sessions.delete_one({"_id": session_id, "user_id": user_id})
    if result.deleted_count != 1:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    return {"id": session_id, "deleted": True}

@router.post("/debug/reset-profile")
async def reset_profile(user_id: str = Query(...)):
    db = get_db()
    db.users.delete_one({"_id": user_id})
    db.episodes.delete_many({"user_id": user_id})
    get_user(user_id)  # re-creates with DEFAULT_PROFILE
    return {"reset": True, "user_id": user_id, "complexity_score": DEFAULT_PROFILE["complexity_score"]}

@router.post("/session/end")
def end_session(req: SessionEndRequest):
    user     = get_user(req.user_id)
    episodes = get_session_episodes(req.session_id)

    avg_reward = None
    if episodes:
        rewards    = [e["reward"] for e in episodes if e.get("reward") is not None]
        avg_reward = round(sum(rewards) / len(rewards), 2) if rewards else None

    # RSI: meta-agent analyzes session and upgrades user profile
    try:
        insights = run_meta_agent(req.user_id, req.session_id, user)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NVIDIA session analysis failed: {e}") from e
    close_session(req.session_id, avg_reward, insights)

    return {
        "session_id":  req.session_id,
        "avg_reward":  avg_reward,
        "insights":    insights,
        "turns":       len(episodes),
    }
