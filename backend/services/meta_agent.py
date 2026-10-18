import json
from db.users import update_user, add_prospective_flag
from db.episodes import get_session_episodes
from db.facts import write_fact
from services.nvidia import complete

META_PROMPT = """
You are an adaptive learning analyst embedded in FocalPoint, an AI that learns
how users read and continuously improves its responses.

You have the user's complete session: every turn, what the AI said, how the user
read it (gaze events per paragraph), and the reward score derived from that data.

Your task is deep pattern analysis — not surface-level observations.
Look for:
- Which response formats caused confusion vs smooth reading
- Which topics triggered repeated re-reading
- Whether complexity has been trending up or down
- What the user's reading stamina looks like (do they stop halfway?)

Session data:
{episodes}

Current user profile:
{profile}

Return a raw JSON object (no markdown fences):
{{
  "insights": [
    "First specific, actionable insight about this user's reading behavior",
    "Second specific, actionable insight",
    "Third specific, actionable insight"
  ],
  "semantic_facts": [
    "User consistently re-reads paragraphs about <topic> — suggest analogies",
    "User reads smoothly when responses use bullet points under 150 words",
    "User loses interest after the third paragraph on abstract topics"
  ],
  "profile_updates": {{
    "complexity_score": <int 1-10>,
    "preferred_format": "<bullets|prose>",
    "avg_words_read": <int>,
    "reads_to_end": <bool>,
    "topics_to_simplify": ["<topic>"],
    "topics_comfortable": ["<topic>"]
  }},
  "new_prospective_flags": [
    {{
      "topic": "<topic name>",
      "action": "<simplify|use_analogy|define_terms>"
    }}
  ]
}}
"""

def _parse_json(raw: str) -> dict:
    # Strip markdown fences if the model adds them
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def run_meta_agent(user_id: str, session_id: str, current_profile: dict) -> list[str]:
    episodes = get_session_episodes(session_id)
    if not episodes:
        return []

    prompt = META_PROMPT.format(
        episodes=json.dumps(episodes, indent=2, default=str),
        profile=json.dumps(current_profile, indent=2, default=str),
    )

    raw = complete([
        {"role": "system", "content": "Return only the requested JSON object."},
        {"role": "user", "content": prompt},
    ], max_tokens=1200, temperature=0.2)
    print(f"[meta_agent] NVIDIA responded ({len(raw)} chars)")

    try:
        result = _parse_json(raw)
    except json.JSONDecodeError as e:
        print(f"[meta_agent] JSON parse failed: {e}\nRaw: {raw[:200]}")
        return []

    # Apply profile updates to MongoDB
    if updates := result.get("profile_updates"):
        cleaned = {k: v for k, v in updates.items() if v is not None}
        if cleaned:
            update_user(user_id, cleaned)

    # Apply prospective flags (deduplicate by topic)
    existing_flags = current_profile.get("prospective_flags", [])
    existing_topics = {f.get("topic") for f in existing_flags}
    for flag in result.get("new_prospective_flags", []):
        if flag.get("topic") and flag.get("action"):
            if flag["topic"] not in existing_topics:
                add_prospective_flag(user_id, flag)
                existing_topics.add(flag["topic"])

    # Write CoALA semantic facts to vector store
    for fact in result.get("semantic_facts", []):
        if fact and isinstance(fact, str):
            try:
                write_fact(user_id, fact, source="meta_agent")
            except Exception as e:
                print(f"[meta_agent] Failed to write fact: {e}")

    return result.get("insights", [])
