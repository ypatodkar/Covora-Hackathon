from datetime import datetime, timezone
import math
import os
from .mongo import get_db
from services.embeddings import embed, embed_query
from services.nvidia import EMBEDDING_DIM

INDEX_NAME    = "user_facts_nvidia_vector_index"
VECTOR_FIELD  = "nvidia_embedding"

def ensure_vector_index():
    db = get_db()
    if os.getenv("MONGODB_VECTOR_SEARCH", "atlas") == "local":
        db.command("ping")
        print("[facts] Using local cosine similarity for semantic search")
        return
    existing = list(db.user_facts.list_search_indexes())
    names = [idx.get("name") for idx in existing]
    if INDEX_NAME not in names:
        db.user_facts.create_search_index({
            "name": INDEX_NAME,
            "type": "vectorSearch",
            "definition": {
                "fields": [
                    {
                        "type":         "vector",
                        "path":         VECTOR_FIELD,
                        "numDimensions": EMBEDDING_DIM,
                        "similarity":   "cosine",
                    },
                    {
                        "type": "filter",
                        "path": "user_id",
                    },
                ]
            },
        })
        print(f"[facts] Created vector search index '{INDEX_NAME}'")

def write_fact(user_id: str, fact: str, source: str = "meta_agent"):
    db     = get_db()
    vector = embed(fact)
    db.user_facts.insert_one({
        "user_id":    user_id,
        "fact":       fact,
        VECTOR_FIELD:  vector,
        "source":     source,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

def get_relevant_facts(user_id: str, query: str, limit: int = 3) -> list[str]:
    db           = get_db()
    query_vector = embed_query(query)

    try:
        if os.getenv("MONGODB_VECTOR_SEARCH", "atlas") == "local":
            candidates = db.user_facts.find(
                {"user_id": user_id, VECTOR_FIELD: {"$exists": True}},
                {"fact": 1, VECTOR_FIELD: 1, "_id": 0},
            )
            ranked = []
            query_norm = math.hypot(*query_vector)
            for candidate in candidates:
                vector = candidate[VECTOR_FIELD]
                if len(vector) != len(query_vector):
                    continue
                denominator = query_norm * math.hypot(*vector)
                if denominator:
                    score = sum(a * b for a, b in zip(query_vector, vector)) / denominator
                    ranked.append((score, candidate["fact"]))
            ranked.sort(key=lambda item: item[0], reverse=True)
            return [fact for _, fact in ranked[:limit]]

        results = db.user_facts.aggregate([
            {
                "$vectorSearch": {
                    "index":       INDEX_NAME,
                    "path":        VECTOR_FIELD,
                    "queryVector": query_vector,
                    "numCandidates": limit * 10,
                    "limit":       limit,
                    "filter":      {"user_id": user_id},
                }
            },
            {"$project": {"fact": 1, "_id": 0}},
        ])
        return [r["fact"] for r in results]
    except Exception as e:
        print(f"[facts] Vector search failed ({e}), returning empty")
        return []
