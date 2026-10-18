from .mongo import get_db

DEFAULT_PROFILE = {
    "complexity_score":    9,
    "preferred_format":    "prose",
    "avg_words_read":      600,
    "reads_to_end":        True,
    "re_read_rate":        0.0,
    "topics_to_simplify":  [],
    "topics_comfortable":  [],
    "prospective_flags":   [],
    "sessions_seen":       0,
}

def get_user(user_id: str) -> dict:
    db   = get_db()
    user = db.users.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, **DEFAULT_PROFILE}
        db.users.insert_one(user)
    return user

def update_user(user_id: str, updates: dict):
    db = get_db()
    db.users.update_one({"_id": user_id}, {"$set": updates}, upsert=True)

def add_prospective_flag(user_id: str, flag: dict):
    db = get_db()
    db.users.update_one(
        {"_id": user_id},
        {"$push": {"prospective_flags": flag}}
    )
