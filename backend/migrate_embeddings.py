"""Backfill existing semantic facts with NVIDIA embeddings after switching providers."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from db.mongo import get_db
from services.embeddings import embed
from db.facts import VECTOR_FIELD, ensure_vector_index


def main() -> None:
    if not os.getenv("NVIDIA_API_KEY"):
        raise RuntimeError("NVIDIA_API_KEY is not set")

    ensure_vector_index()
    collection = get_db().user_facts
    pending = collection.find(
        {"fact": {"$type": "string"}, VECTOR_FIELD: {"$exists": False}},
        {"fact": 1},
    )
    count = 0
    for item in pending:
        vector = embed(item["fact"])
        result = collection.update_one(
            {"_id": item["_id"], VECTOR_FIELD: {"$exists": False}},
            {"$set": {VECTOR_FIELD: vector}},
        )
        count += result.modified_count
    print(f"Backfilled {count} semantic facts with NVIDIA embeddings")


if __name__ == "__main__":
    main()
