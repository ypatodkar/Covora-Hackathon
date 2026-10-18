# FocalPoint — Project Master Doc
> AIEWF 2026 Hackathon · Shack15, SF · June 27–28
> Submission deadline: June 28, 12:00PM

> Historical hackathon plan. The current implementation uses NVIDIA for chat, session analysis, and embeddings; see README.md for setup.

---

## The Idea in One Sentence
A chat interface that watches how you read using eye-tracking, derives implicit reward signals from your gaze, and continuously adapts LLM response length, format, and depth — no feedback required, gets smarter every turn.

## One-Sentence Pitch to Judges
> "FocalPoint is implicit RLHF — we replace the human rater with the human eye. Your gaze IS the reward signal."

---

## Prize Targets

| Prize | Requirement | How we qualify |
|-------|-------------|----------------|
| Main prize | Continual Learning theme | Gaze-driven system prompt evolution per turn |
| Gemini $5,000 | Use Gemini 3.5 feature | Interactions API / Antigravity for meta-learning agent |
| DigitalOcean | Use DO platform | Deploy backend infrastructure |
| MongoDB | Use Atlas | Store all memory layers — episodic, semantic, procedural |

**Important:** Keep Gemini for the live demo. Do not add fallback model paths; broken model calls must fail visibly.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React (Vite) |
| Eye-tracking | MediaPipe FaceMesh/Iris (browser-based, no hardware) |
| Backend | Python + FastAPI |
| LLM | Gemini 3.5 Flash |
| Meta-agent | Gemini Interactions API / Antigravity |
| Database | MongoDB Atlas |
| Hosting | DigitalOcean |

---

## Cognitive Architecture

FocalPoint implements all six layers of cognitive memory:

### 1. Sensory Memory
- **What:** Raw gaze stream from MediaPipe FaceMesh/Iris
- **Format:** `{ x, y, timestamp }` every ~50ms
- **Lifetime:** Milliseconds — immediately processed into working memory
- **Where:** Browser in-memory buffer (not persisted)

### 2. Working Memory
- **What:** Live state of the current turn
- **Format:**
  ```json
  {
    "current_turn": 3,
    "active_response_id": "abc123",
    "live_gaze_zone": "paragraph_2",
    "zone_visit_counts": { "paragraph_1": 1, "paragraph_2": 4 },
    "session_reward_running": -0.3
  }
  ```
- **Lifetime:** One conversation turn
- **Where:** Frontend state (React useState / useRef)

### 3. Episodic Memory
- **What:** A record of exactly what happened each turn — what was shown, how it was read
- **Format:**
  ```json
  {
    "session_id": "sess_xyz",
    "turn": 3,
    "response_id": "abc123",
    "response_length": 320,
    "response_format": "prose",
    "gaze_events": [
      { "zone": "paragraph_2", "visits": 4, "flag": "confusion" },
      { "zone": "paragraph_3", "visits": 0, "flag": "skipped" }
    ],
    "reward": -0.5,
    "timestamp": "2026-06-28T10:32:00Z"
  }
  ```
- **Lifetime:** Persistent across sessions
- **Where:** MongoDB — `episodes` collection

### 4. Semantic Memory
- **What:** General knowledge about this user — their reading style, preferences, comfort level
- **Format:**
  ```json
  {
    "user_id": "user_001",
    "complexity_score": 4,
    "preferred_format": "bullets",
    "avg_words_per_response_read": 180,
    "reads_to_end": false,
    "re_read_rate": 0.35,
    "topics_to_simplify": ["recursion", "API design"],
    "topics_comfortable": ["Python basics", "databases"],
    "sessions_seen": 3,
    "last_updated": "2026-06-28T10:32:00Z"
  }
  ```
- **Lifetime:** Persistent, updated after every turn
- **Where:** MongoDB — `users` collection

### 5. Procedural Memory
- **What:** The adaptation rules — how to respond to each signal
- **Rules:**
  ```
  re_read detected (zone visits > 2 in 3s)  → simplify: bullets, short sentences, plain words
  rapid_skim detected (fast back-and-forth)  → simplify: reduce density, increase whitespace
  stopped_reading (gaze leaves at 50% depth) → shorten: cut response length by 40%
  smooth_readthrough                         → maintain or increase depth next turn
  skipped_section                            → that format element is unwanted, avoid it
  ```
- **Where:** Backend constants / rule engine (not in DB — baked into code)

### 6. Prospective Memory
- **What:** Things the system should remember to do in a future turn
- **Format:**
  ```json
  {
    "user_id": "user_001",
    "flags": [
      { "topic": "recursion", "action": "simplify", "triggered_turn": 2 },
      { "topic": "async/await", "action": "use_analogy", "triggered_turn": 4 }
    ]
  }
  ```
- **Lifetime:** Persistent
- **Where:** MongoDB — nested inside `users` collection

---

## ReACT Agent Loop

Every turn runs this loop:

```
OBSERVE  → Gaze stream arrives from MediaPipe FaceMesh/Iris
           Zone visit counts computed
           Flags raised: { confusion, skim, skip, smooth }

REASON   → Agent reads:
           - Current flags (working memory)
           - User semantic profile (semantic memory)
           - Last 3 episodes (episodic memory)
           - Procedural rules
           Decides: what reward score? what should change next turn?

ACT      → 1. Write episode to MongoDB
           2. Update user semantic profile
           3. Update prospective flags if new topic confusion found
           4. Build updated system prompt for next LLM call
           5. Return updated system prompt to frontend

REPEAT   → Next user question uses updated system prompt
```

---

## Implicit RLHF — The Reward Function

| Gaze behavior | Detection method | Reward |
|--------------|-----------------|--------|
| Smooth read-through to end | All zones visited once, forward only | `+1.0` |
| Re-reads same line 2+ times | Zone visit count > 2 within 3s | `-0.5` |
| Rapid skimming small area | Fast gaze movement < 100px back-and-forth | `-0.3` |
| Stops reading at 50% | Gaze leaves response area before end | `-0.7` |
| Scrolls back up to re-read | Reverse scroll + gaze returns to earlier zone | `-0.4` |
| Skips entire section | Zone visit count = 0 | `-0.2` |

**Reward drives system prompt update:**
```
reward > 0.5   → current style working, maintain or go deeper
reward 0 to 0.5 → minor simplification
reward < 0     → significant simplification: bullets, shorter, plainer
reward < -0.5  → major reset: much shorter, much simpler
```

---

## Self-Improving Feedback Loop (Turn-by-Turn)

```
Turn 1:
  System prompt: neutral default
  Response: ~300 words, prose format
  Gaze: re-reads paragraph 2 three times
  Reward: -0.5
  Semantic update: complexity_score -= 1, preferred_format → "bullets"

Turn 2:
  System prompt: "Use bullet points. Short sentences. Avoid jargon."
  Response: ~180 words, bullets
  Gaze: smooth read-through
  Reward: +0.8
  Semantic update: complexity_score stable, re_read_rate improving

Turn 5:
  System prompt is now fully personalized to this user
  Response style, length, vocabulary all calibrated
  System is meaningfully smarter than Turn 1 — no user effort
```

---

## Meta-Learning Agent (Self-Improvement Layer)

After each session ends, a second agent pass runs via Gemini Interactions API:

```python
meta_prompt = """
You are analyzing a user's reading session to improve their profile.

Episodic memory (this session): {episodes}
Current semantic profile: {semantic_memory}
Prospective flags: {prospective_flags}

Tasks:
1. Identify 3 high-level patterns about how this user reads
2. Update their semantic profile with new insights
3. Add any new topics to simplify in prospective memory
4. Recommend a complexity_score (0-10) for next session

Return a JSON object with: insights, updated_profile, new_flags
"""
```

This is the **RSI / self-improvement** moment. The system reflects on itself after each session and upgrades its model of the user. Run this with Antigravity (Gemini Interactions API) for the Gemini prize.

---

## MongoDB Schema

### Collection: `users`
```json
{
  "_id": "user_001",
  "complexity_score": 4,
  "preferred_format": "bullets",
  "avg_words_read": 180,
  "reads_to_end": false,
  "re_read_rate": 0.35,
  "topics_to_simplify": ["recursion"],
  "topics_comfortable": ["Python basics"],
  "prospective_flags": [
    { "topic": "recursion", "action": "simplify", "triggered_turn": 2 }
  ],
  "sessions_seen": 3,
  "last_updated": "2026-06-28T10:32:00Z"
}
```

### Collection: `episodes`
```json
{
  "_id": "ep_abc123",
  "user_id": "user_001",
  "session_id": "sess_xyz",
  "turn": 3,
  "response_id": "resp_001",
  "response_length": 320,
  "response_format": "prose",
  "system_prompt_used": "...",
  "gaze_events": [
    { "zone": "paragraph_2", "visits": 4, "flag": "confusion" }
  ],
  "reward": -0.5,
  "timestamp": "2026-06-28T10:32:00Z"
}
```

### Collection: `sessions`
```json
{
  "_id": "sess_xyz",
  "user_id": "user_001",
  "started_at": "2026-06-28T10:00:00Z",
  "ended_at": "2026-06-28T10:45:00Z",
  "turns": 7,
  "avg_reward": 0.3,
  "meta_agent_run": true,
  "meta_insights": ["prefers short bullets", "struggles with analogies"]
}
```

---

## System Prompt Builder

```python
def build_system_prompt(user_profile, recent_episodes):
    base = "You are a helpful assistant."

    # Format preference
    if user_profile["preferred_format"] == "bullets":
        base += " Always respond using bullet points and numbered lists."
    
    # Complexity
    score = user_profile["complexity_score"]
    if score < 3:
        base += " Use very simple language. Short sentences. No jargon."
    elif score < 6:
        base += " Use clear, plain language. Avoid technical terms unless necessary."
    else:
        base += " You can use technical depth and nuance."
    
    # Length
    avg = user_profile["avg_words_read"]
    base += f" Keep responses under {avg + 50} words."
    
    # Topics to simplify
    if user_profile["topics_to_simplify"]:
        topics = ", ".join(user_profile["topics_to_simplify"])
        base += f" When discussing {topics}, use extra simple explanations and analogies."
    
    return base
```

---

## API Contract (Single Source of Truth)

**One endpoint. Both sides must match this exactly.**

### `POST http://localhost:8000/chat`

**Request (frontend sends):**
```json
{
  "user_id": "demo_user",
  "message": "explain recursion to me",
  "previous_response_id": "resp_abc123",
  "gaze_events": [
    { "zone": "zone_0", "visits": 1,  "flag": "smooth"    },
    { "zone": "zone_1", "visits": 4,  "flag": "confusion" },
    { "zone": "zone_2", "visits": 0,  "flag": "skipped"   }
  ]
}
```

**Response (backend returns):**
```json
{
  "response_id": "resp_xyz456",
  "text": "Recursion is when a function calls itself...",
  "reward": -0.5,
  "user_profile": {
    "complexity_score": 4,
    "preferred_format": "bullets"
  }
}
```

**Rules both sides must follow:**
- `user_id` — always `"demo_user"` (hardcoded, no auth)
- `previous_response_id` — `null` on first turn, then always last `response_id`
- `gaze_events` — `[]` on first turn
- `flag` — exactly one of: `"smooth"` | `"confusion"` | `"skipped"` | `"skim"`
- `zone` — `"zone_0"`, `"zone_1"` ... (zero-indexed, matches paragraph index)
- `response_id` — UUID generated by backend, stored by frontend, sent back next turn
- Backend must allow CORS from `http://localhost:5173`

---

## Work Split

| Yash (Backend) | Teammate (Frontend) |
|----------------|---------------------|
| FastAPI + CORS setup | React chat UI |
| Gemini 3.5 Flash integration | MediaPipe FaceMesh/Iris initialization |
| Reward function computation | Zone mapping on response DOM |
| System prompt builder | Gaze event detection + flag computation |
| MongoDB read/write | Heatmap color overlay |
| Meta-agent (Antigravity) | Stats panel (reward + complexity + format) |

---

## Build Order (Tomorrow)

### Hour 1–2 (9AM–11AM): Foundation
- [ ] React app with basic chat UI
- [ ] FastAPI backend running
- [ ] Gemini 3.5 Flash connected and returning responses
- [ ] MongoDB Atlas connected

### Hour 3–4 (11AM–1PM): Eye-Tracking Core
- [ ] MediaPipe FaceMesh/Iris installed and calibrated in browser
- [ ] Response text divided into zones by paragraph
- [ ] Gaze coordinates mapped to zones in real-time
- [ ] Zone visit counter working

### Hour 5–6 (1PM–3PM): Signal Detection
- [ ] Re-read detection (zone visits > 2 in 3s)
- [ ] Skim detection (rapid back-and-forth)
- [ ] Stop-reading detection (gaze leaves response area)
- [ ] Reward score computed per turn

### Hour 7–8 (3PM–5PM): Learning Loop
- [ ] Reward drives semantic profile update in MongoDB
- [ ] System prompt builder reads user profile
- [ ] Next turn uses updated system prompt
- [ ] Episodic memory written to MongoDB after each turn

### Hour 9–10 (5PM–7PM): Self-Improvement Layer
- [ ] Session end triggers meta-agent call (Antigravity)
- [ ] Meta-agent reads episodes, updates semantic profile
- [ ] Prospective flags written back to MongoDB
- [ ] Full loop tested end-to-end

### Hour 11–12 (7PM–9PM): Polish + Demo Prep
- [ ] UI shows gaze heatmap overlay (impressive visually)
- [ ] UI shows live reward score per turn
- [ ] UI shows current user profile (complexity, format preference)
- [ ] Test with multiple question types

### Morning (8:30AM–12PM): Buffer + Submission
- [ ] Fix anything broken overnight
- [ ] Deploy to DigitalOcean
- [ ] Record 1-minute demo video
- [ ] Submit by 12PM

---

## Demo Script (3 minutes)

1. **(30s)** Open FocalPoint. Explain: "This chat interface watches how you read, not what you type."
2. **(30s)** Ask a complex question. Get a long, dense response. Let the judge see the gaze heatmap light up. Re-read a paragraph deliberately. Show the reward score drop to -0.5.
3. **(30s)** Ask a follow-up. Show the new response is shorter, uses bullets. Reward score climbs to +0.8.
4. **(30s)** Show the user profile panel: complexity dropped, format switched to bullets, re-read rate declining.
5. **(30s)** Explain the cognitive architecture: "Sensory → Working → Episodic → Semantic → Procedural → Prospective. Full cognitive stack, driven by gaze."
6. **(30s)** Show the meta-agent running after session end. MongoDB profile updating. "This is implicit RLHF — the eye is the reward signal. No human rater needed."

---

## Key Rules to Remember
- Re-read or repeated skim of same small area → **make next response simpler**
- Keep Gemini for the live demo (save credits during dev, use DO GenAI otherwise)
- The architecture diagram with all 6 memory types is your technicality score
- The live gaze heatmap is your demo wow moment
- "Implicit RLHF" is your one-line pitch

---

*Last updated: June 27, 2026*
