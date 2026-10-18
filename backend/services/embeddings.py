from services.nvidia import embedding

def embed(text: str) -> list[float]:
    return embedding(text, "passage")

def embed_query(text: str) -> list[float]:
    return embedding(text, "query")
