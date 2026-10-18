# FocalPoint — Eye-Tracking Frontend
### Your job, your files, your integration contract

---

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/FocalPoint.git
cd FocalPoint/frontend
npm install
npm run dev     # runs at http://localhost:5173
```

Copy env:
```bash
cp .env.example .env
# Ask Yash for values over iMessage
```

Backend runs at `http://localhost:8000` — Yash handles that side.

---

## Ports (do not change these)

| Service | URL |
|---------|-----|
| Your frontend | `http://localhost:5173` |
| Yash's backend | `http://localhost:8000` |

---

## The Only Thing You Build

A React chat interface that:
1. Shows LLM responses paragraph by paragraph
2. Tracks where the user's eyes go using the webcam
3. Detects reading signals (re-read, skim, skip)
4. Sends gaze events + user message to the backend in one request
5. Displays the response + a live heatmap + a stats panel

Nothing else. No database. No LLM calls. No auth.

---

## Install

```bash
npm install webgazer
```

---

## Exact Data Formats (must match Yash's backend exactly)

### What you send — `POST http://localhost:8000/chat`

```json
{
  "user_id": "demo_user",
  "message": "explain recursion to me",
  "previous_response_id": "resp_abc123",
  "gaze_events": [
    { "zone": "zone_0", "visits": 1, "flag": "smooth" },
    { "zone": "zone_1", "visits": 4, "flag": "confusion" },
    { "zone": "zone_2", "visits": 0, "flag": "skipped" }
  ]
}
```

**Rules:**
- `user_id` — always hardcode `"demo_user"` for the hackathon
- `previous_response_id` — send `null` on the very first message, then always send the `response_id` you received from the last backend response
- `gaze_events` — send `[]` on first message, then always send the events from the response the user just finished reading
- `flag` must be exactly one of: `"smooth"` | `"confusion"` | `"skipped"` | `"skim"`
- `zone` must be exactly: `"zone_0"`, `"zone_1"`, `"zone_2"` ... (zero-indexed, matches paragraph index)
- `visits` — integer, how many times gaze landed in this zone

### What you receive — response from `POST /chat`

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

**What to do with each field:**
- `response_id` — store this in state, send it back as `previous_response_id` next turn
- `text` — render this as the chat response, split into zones
- `reward` — show in the stats panel (number between -1.0 and +1.0)
- `user_profile.complexity_score` — show in stats panel (0–10)
- `user_profile.preferred_format` — show in stats panel (`"bullets"` or `"prose"`)

---

## App State (keep it simple)

```jsx
const [messages, setMessages] = useState([])        // chat history
const [input, setInput] = useState('')              // current input
const [loading, setLoading] = useState(false)       // waiting for backend
const [lastResponseId, setLastResponseId] = useState(null)  // for next request
const [userProfile, setUserProfile] = useState({ complexity_score: 5, preferred_format: 'prose' })
const [lastReward, setLastReward] = useState(null)

const zoneLog = useRef({})        // { zone_0: [t1, t2], zone_1: [t1] }
const gazerReady = useRef(false)  // true after webgazer initializes
```

---

## WebGazer Setup

```jsx
useEffect(() => {
  webgazer
    .setGazeListener((data, timestamp) => {
      if (!data || !gazerReady.current) return
      handleGaze(data.x, data.y, timestamp)
    })
    .begin()
    .then(() => {
      gazerReady.current = true
    })

  webgazer.showVideoPreview(false)
  webgazer.showPredictionPoints(true)  // red dot — keep on during testing

  return () => webgazer.end()
}, [])
```

---

## Zone Mapping

Split response text into paragraphs, give each a stable DOM id:

```jsx
function ResponseDisplay({ text, responseId }) {
  const paragraphs = text
    .split('\n')
    .map(p => p.trim())
    .filter(p => p.length > 0)

  return (
    <div id={`response-${responseId}`}>
      {paragraphs.map((para, i) => (
        <p
          key={`${responseId}-${i}`}
          id={`zone_${i}`}
          data-zone={`zone_${i}`}
          style={{
            marginBottom: '1rem',
            padding: '4px 8px',
            borderRadius: '4px',
            background: getHeatColor(`zone_${i}`)
          }}
        >
          {para}
        </p>
      ))}
    </div>
  )
}
```

Reset zone log each time a new response arrives:

```js
// call this when new response arrives from backend
function resetZoneLog() {
  zoneLog.current = {}
}
```

---

## Gaze → Zone Detection

```js
function handleGaze(x, y, timestamp) {
  const zone = getZoneAtGaze(x, y)
  if (!zone) return

  if (!zoneLog.current[zone]) zoneLog.current[zone] = []
  zoneLog.current[zone].push(timestamp)
}

function getZoneAtGaze(x, y) {
  const zones = document.querySelectorAll('[data-zone]')
  for (const el of zones) {
    const rect = el.getBoundingClientRect()
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      return el.getAttribute('data-zone')
    }
  }
  return null
}
```

---

## Flag Computation (run this before sending each request)

```js
function computeGazeEvents(allZones) {
  // allZones = array of zone ids that exist in current response
  // e.g. ['zone_0', 'zone_1', 'zone_2']

  return allZones.map(zone => {
    const timestamps = zoneLog.current[zone] || []
    const visits = timestamps.length

    if (visits === 0) {
      return { zone, visits: 0, flag: 'skipped' }
    }

    // confusion: visited same zone 3+ times within 5 seconds
    if (visits >= 3) {
      const span = timestamps[timestamps.length - 1] - timestamps[0]
      if (span < 5000) {
        return { zone, visits, flag: 'confusion' }
      }
    }

    // skim: visited 2+ times but very fast (< 500ms total)
    if (visits >= 2) {
      const span = timestamps[timestamps.length - 1] - timestamps[0]
      if (span < 500) {
        return { zone, visits, flag: 'skim' }
      }
    }

    return { zone, visits, flag: 'smooth' }
  })
}
```

---

## Sending the Request

```js
async function sendMessage() {
  if (!input.trim() || loading) return
  setLoading(true)

  // 1. Compute gaze events from the response the user just read
  const currentZones = Array.from(document.querySelectorAll('[data-zone]'))
    .map(el => el.getAttribute('data-zone'))
  const gazeEvents = computeGazeEvents(currentZones)

  // 2. Build request
  const body = {
    user_id: 'demo_user',
    message: input,
    previous_response_id: lastResponseId,   // null on first turn
    gaze_events: gazeEvents                  // [] on first turn
  }

  // 3. Send
  const res = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  const data = await res.json()

  // 4. Update state
  setLastResponseId(data.response_id)
  setUserProfile(data.user_profile)
  setLastReward(data.reward)
  setMessages(prev => [
    ...prev,
    { role: 'user', text: input },
    { role: 'assistant', text: data.text, responseId: data.response_id }
  ])
  setInput('')
  resetZoneLog()     // clear gaze log for next response
  setLoading(false)
}
```

---

## Heatmap Colors

```js
function getHeatColor(zone) {
  const visits = (zoneLog.current[zone] || []).length
  if (visits === 0) return 'transparent'
  if (visits <= 2) return 'rgba(0, 200, 100, 0.15)'   // green — read cleanly
  if (visits <= 4) return 'rgba(255, 165, 0, 0.25)'   // orange — re-read
  return 'rgba(220, 50, 50, 0.35)'                     // red — confusion
}
```

Call `getHeatColor` inside `ResponseDisplay` (already wired above). The heatmap updates live as the user reads because WebGazer runs continuously — trigger a re-render by putting `zoneLog` updates through a state counter:

```js
const [gazeTick, setGazeTick] = useState(0)  // increment to force re-render

// inside handleGaze, after pushing to zoneLog:
setGazeTick(t => t + 1)
```

---

## Stats Panel

Show this beside the chat. Update on every response:

```jsx
function StatsPanel({ reward, profile }) {
  return (
    <div style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '8px' }}>
      <p><strong>Last Reward:</strong> {reward !== null ? reward.toFixed(2) : '—'}</p>
      <p><strong>Complexity Score:</strong> {profile.complexity_score} / 10</p>
      <p><strong>Preferred Format:</strong> {profile.preferred_format}</p>
    </div>
  )
}
```

---

## Full Component Layout

```
┌─────────────────────────────────┬───────────────┐
│                                 │  Stats Panel  │
│         Chat Window             │  Reward: -0.5 │
│                                 │  Complexity:4 │
│  [zone_0 — green]               │  Format: bullets│
│  [zone_1 — red]   ← heatmap    │               │
│  [zone_2 — transparent]         │               │
│                                 │               │
│  [input box]  [Send]            │               │
└─────────────────────────────────┴───────────────┘
```

---

## Integration Checklist (run through this before merging)

- [ ] `POST /chat` returns JSON with exactly: `response_id`, `text`, `reward`, `user_profile`
- [ ] `user_id` is always `"demo_user"` in every request
- [ ] `previous_response_id` is `null` on first turn, then always the last `response_id`
- [ ] `gaze_events` is `[]` on first turn
- [ ] Zone ids are `zone_0`, `zone_1`... matching paragraph index (zero-based)
- [ ] Flags are exactly one of: `smooth` | `confusion` | `skipped` | `skim`
- [ ] `zoneLog` is reset after every new response arrives
- [ ] Heatmap updates live while user reads
- [ ] Stats panel shows reward + complexity + format
- [ ] No CORS errors (Yash must allow `http://localhost:5173` on his backend)

---

## Build Order

| Step | Task | Time |
|------|------|------|
| 1 | React app running, basic chat UI | 30 min |
| 2 | WebGazer initialized, camera permission working | 30 min |
| 3 | Response split into zones with `data-zone` tags | 20 min |
| 4 | Gaze mapped to zones — verify in console | 30 min |
| 5 | Flag computation working | 30 min |
| 6 | `POST /chat` wired up end-to-end | 30 min |
| 7 | Heatmap colors updating live | 30 min |
| 8 | Stats panel showing reward + profile | 20 min |

**Total: ~4 hours. Start at step 1. Do not skip ahead.**

---

## Common Issues

| Problem | Fix |
|---------|-----|
| Camera permission denied | Must use Chrome. Make sure site is on `localhost`, not `127.0.0.1` |
| Gaze way off screen | WebGazer needs calibration — click around the page for 10 seconds first |
| CORS error on fetch | Tell Yash to add `http://localhost:5173` to FastAPI CORS origins |
| `webgazer is not defined` | Import as `import webgazer from 'webgazer'`, not a CDN script tag |
| Heatmap not updating | Make sure `setGazeTick` is being called inside `handleGaze` |

---

## Questions?

Ping Yash. His side: backend, Gemini, MongoDB, system prompt. Your side: webcam, gaze, heatmap, chat UI.
