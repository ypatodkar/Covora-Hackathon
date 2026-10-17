"""Deterministic stand-ins for the model, one per output schema. They read the step's JSON inputs."""

import re
from urllib.parse import urlsplit

_GENERIC_TITLES = {"About", "Our Team", "Team"}


def query_plan(inp: dict) -> dict:
    wave = inp.get("wave", 1)
    return {"queries": [f"metal fabrication shops Ohio wave {wave}", f"US machining companies small wave {wave}"]}


def extracted_companies(inp: dict) -> dict:
    companies = []
    for r in inp["results"]:
        host = urlsplit(r["url"]).hostname or ""
        if host.endswith(".test"):
            parts = [p.strip() for p in re.split(r" \| | - ", r["title"])]
            name = next((p for p in parts if p not in _GENERIC_TITLES), parts[0])
            companies.append({"name": name, "domain": host, "source_url": r["url"]})
    # An invented company the validator must drop.
    companies.append({"name": "Ghost Corp", "domain": "ghost.test", "source_url": "https://ghost.test/"})
    return {"companies": companies}


STANDARD_HANDLERS = {"QueryPlan": query_plan, "ExtractedCompanies": extracted_companies}
