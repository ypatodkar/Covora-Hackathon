from datetime import datetime, timezone
from .mongo import get_db

def write_episode(episode: dict):
    db = get_db()
    db.episodes.insert_one(episode)

def get_recent_episodes(user_id: str, limit: int = 5) -> list[dict]:
    db = get_db()
    return list(
        db.episodes
        .find({"user_id": user_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )

def get_session_episodes(session_id: str) -> list[dict]:
    db = get_db()
    return list(
        db.episodes
        .find({"session_id": session_id}, {"_id": 0})
        .sort("turn", 1)
    )
