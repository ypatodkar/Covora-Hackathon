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


_INDUSTRY_WORDS = ["metal fabrication", "machining", "plastics manufacturing", "valve manufacturing",
                   "food manufacturing", "manufacturing", "software"]  # fmt: skip
_STATES = ["Ohio", "Michigan", "Vermont", "Texas", "Indiana"]
_MANUFACTURING = ("fabrication", "machining", "plastics", "valve", "manufacturing")


def _fact(field: str, value: str, url: str, quote: str) -> dict:
    return {"field": field, "value": value, "source_url": url, "quote": quote, "label": "verified"}


def extracted_facts(inp: dict) -> dict:
    facts, seen = [], set()
    for page in inp["pages"]:
        text = page["text"]
        m = re.search(r"(?:about )?(\d+) employees", text)
        if m and "employee_count" not in seen:
            facts.append(_fact("employee_count", m.group(1), page["url"], m.group(0)))
            seen.add("employee_count")
        word = next((w for w in _INDUSTRY_WORDS if w in text.lower()), None)
        if word and "industry" not in seen:
            facts.append(
                {"field": "industry", "value": word, "source_url": page["url"], "quote": word, "label": "verified"}
            )
            seen.add("industry")
        loc = re.search(r"in ([A-Z][a-z]+(?: [A-Z][a-z]+)?), (" + "|".join(_STATES) + ")", text)
        if loc and "location" not in seen:
            place = f"{loc.group(1)}, {loc.group(2)}"
            facts.append(_fact("location", place, page["url"], place))
            seen.add("location")
    if inp["pages"]:
        # An invented revenue figure with no quote: the validator must drop it.
        facts.append(_fact("revenue_usd", "8000000", inp["pages"][0]["url"], ""))
    return {"facts": facts}


def fit_judgment(inp: dict) -> dict:
    facts = inp["facts"]
    by_field: dict[str, list[dict]] = {}
    for f in facts:
        by_field.setdefault(f["field"], []).append(f)
    criteria = []
    for c in inp["criteria"]:
        status, ids = "unknown", []
        if c["name"] == "industry" and by_field.get("industry"):
            ids = [f["id"] for f in by_field["industry"]]
            value = by_field["industry"][0]["value"]
            status = (
                "not_met" if "software" in value else "met" if any(w in value for w in _MANUFACTURING) else "unknown"
            )
        elif c["name"] == "location" and by_field.get("location"):
            ids = [f["id"] for f in by_field["location"]]
            status = "met" if any(s in by_field["location"][0]["value"] for s in _STATES) else "unknown"
        elif c["name"] == "employee_range" and by_field.get("employee_count"):
            ids = [f["id"] for f in by_field["employee_count"]]
            low, high = (int(n.replace(",", "")) for n in re.findall(r"[\d,]+", c["description"])[:2])
            status = "met" if low <= int(by_field["employee_count"][0]["value"]) <= high else "not_met"
        criteria.append({"criterion": c["name"], "status": status, "fact_ids": ids})
    return {"criteria": criteria, "confidence": "medium", "reason": "Judged from the company's own website."}


STANDARD_HANDLERS.update({"ExtractedFacts": extracted_facts, "FitJudgment": fit_judgment})


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_ROLES = {
    "owner": ("executive", "owner"), "president": ("executive", "owner"), "coo": ("operations", "c_level"),
    "ceo": ("executive", "c_level"), "operations manager": ("operations", "manager"),
    "partnerships": ("partnerships", "director"), "plant manager": ("operations", "manager"),
}  # fmt: skip


def _role(title: str) -> tuple[str, str]:
    lower = title.lower()
    return next((v for k, v in _ROLES.items() if k in lower), ("other", "individual"))


def extracted_people(inp: dict) -> dict:
    people, seen = [], set()
    linkedin = [s["url"] for s in inp["sources"] if "linkedin.com/in/" in s["url"]]
    for source in inp["sources"]:
        for line in source["text"].splitlines():
            m = re.match(r"\s*([A-Z][a-z]+ [A-Z][a-z]+) — ([^,]+)(?:, (.*))?$", line)
            if not m or m.group(1) in seen:
                continue
            name, title = m.group(1), m.group(2).strip()
            email = _EMAIL.search(m.group(3) or "")
            function, seniority = _role(title)
            person = {"full_name": name, "title": title, "function": function, "seniority": seniority,
                      "source_url": source["url"], "email": email.group(0) if email else None,
                      "linkedin_url": next((u for u in linkedin if name.split()[0].lower() in u), None)}  # fmt: skip
            if name == "Mark Ellison":
                person["email"] = "mark@ohio-precision.test"  # invented: not in any source
            people.append(person)
            seen.add(name)
    if inp["sources"]:
        people.append({"full_name": "Zed Phantom", "title": "COO", "function": "operations", "seniority": "c_level",
                       "source_url": inp["sources"][0]["url"]})  # fmt: skip
    return {"people": people}


STANDARD_HANDLERS["ExtractedPeople"] = extracted_people
