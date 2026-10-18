from datetime import datetime, timezone
from .mongo import get_db

def start_session(user_id: str, session_id: str):
    db = get_db()
    db.sessions.update_one(
        {"_id": session_id, "user_id": user_id},
        {"$setOnInsert": {
            "_id":          session_id,
            "id":           session_id,
            "user_id":      user_id,
            "started_at":   datetime.now(timezone.utc).isoformat(),
            "created_at":   datetime.now(timezone.utc).isoformat(),
            "ended_at":     None,
            "turns":        0,
            "avg_reward":   None,
            "meta_agent_run": False,
            "meta_insights":  [],
        }},
        upsert=True,
    )

def increment_turn(session_id: str):
    db = get_db()
    db.sessions.update_one({"_id": session_id}, {"$inc": {"turns": 1}})

def close_session(session_id: str, avg_reward: float, insights: list[str]):
    db = get_db()
    db.sessions.update_one(
        {"_id": session_id},
        {"$set": {
            "ended_at":       datetime.now(timezone.utc).isoformat(),
            "avg_reward":     avg_reward,
            "meta_agent_run": True,
            "meta_insights":  insights,
        }}
    )
