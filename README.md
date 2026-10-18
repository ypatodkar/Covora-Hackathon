# FocalPoint

FocalPoint is a gaze-aware LLM chat interface. The frontend tracks which response zones a user reads, skips, or revisits, sends those gaze events to a FastAPI backend, and the backend updates the next NVIDIA model system prompt from MongoDB-backed user/session memory.

## Current Architecture

- Frontend: React + Vite on `http://localhost:5173`
- Backend: FastAPI on `http://127.0.0.1:8000`
- Chat, follow-up questions, and session analysis: NVIDIA API Catalog chat completions
- Semantic memory: NVIDIA API Catalog embeddings
- Database: local MongoDB via Docker, or MongoDB Atlas, using `pymongo`
- Eye tracking: MediaPipe FaceMesh/Iris in the browser

The app intentionally has no mock or fallback response path. If NVIDIA generation, MongoDB, CORS, or the backend is broken, the UI shows the real backend error.

## What Changed

- Root `npm run dev` now starts both the backend and frontend.
- Eye tracking now uses local MediaPipe FaceMesh/Iris landmarks with calibrated screen-coordinate regression.
- Vite uses strict port `5173`, matching the backend CORS configuration.
- Frontend chat calls now require the FastAPI backend; local simulation was removed.
- Backend chat fails with a real `502` when NVIDIA generation fails.
- DigitalOcean/OpenAI fallback code was removed.
- `MONGODB_URI` is required; the backend no longer silently defaults to local MongoDB.
- Sessions and profile state now persist through backend endpoints and MongoDB, not browser localStorage.
- Added backend endpoints:
  - `GET /profile`
  - `POST /profile`
  - `GET /sessions`
  - `POST /sessions`
  - `DELETE /sessions/{session_id}`
- Gaze zones are scoped by response id so previous assistant messages do not pollute the next reward calculation.

## Requirements

- Node.js and npm
- Python 3
- Docker Desktop for local MongoDB (or a MongoDB Atlas connection string)
- NVIDIA API key

## Environment

Create `.env` in the repo root:

```bash
NVIDIA_API_KEY=your_nvidia_api_key
NVIDIA_CHAT_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB_NAME=focalpoint
MONGODB_VECTOR_SEARCH=local
```

`NVIDIA_CHAT_MODEL` is optional; the shown NVIDIA model is the default. A key exported in the shell takes precedence over `.env`. The same key serves chat, follow-up questions, session analysis, and semantic embeddings. Semantic memory uses `nvidia/nemotron-3-embed-1b` with 2048 dimensions. Local mode ranks these vectors by cosine similarity in Python. Atlas mode uses a separate vector index. Existing Gemini vectors are not searched by the new model.

For Atlas, set `MONGODB_URI` to your Atlas connection string and `MONGODB_VECTOR_SEARCH=atlas`. Local MongoDB stores data in the persistent Docker volume `focalpoint_mongodb_data` and listens only on this machine.

If another app uses port 8000, set `BACKEND_PORT=8001` and `VITE_API_BASE_URL=http://localhost:8001` in the root `.env`. Restart `npm run dev` after changing these values. The backend URLs below assume the default port 8000; substitute your configured port when testing.

To keep older semantic facts searchable, run this once after adding the NVIDIA key:

```bash
cd backend
.venv/bin/python migrate_embeddings.py
```

The migration adds NVIDIA embeddings to existing facts and can be rerun safely.

## Install

Install root dev tooling:

```bash
npm install
```

Install frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

Install backend dependencies:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

## Run

From the repo root:

```bash
npm run db:up
npm run dev
```

Keep Docker Desktop running when using local MongoDB. `npm run db:down` stops MongoDB while retaining its data. Atlas users can skip the `db:up` command.

This starts both services:

- Frontend: `http://localhost:5173`
- Backend: `http://127.0.0.1:8000`

Do not run only `cd frontend && npm run dev` for normal use. The UI needs the FastAPI backend for chat, profile updates, session history, and MongoDB writes.

## Verify

Check backend health:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

Check the demo profile:

```bash
curl 'http://127.0.0.1:8000/profile?user_id=demo_user'
```

Run production build:

```bash
npm run build
```

Run frontend lint:

```bash
cd frontend
npm run lint
```

## API Contract

### `POST /chat`

Request:

```json
{
  "user_id": "demo_user",
  "message": "explain recursion",
  "session_id": "s_123",
  "history": [],
  "previous_response_id": null,
  "gaze_events": []
}
```

Response:

```json
{
  "response_id": "uuid",
  "text": "LLM response",
  "reward": null,
  "user_profile": {
    "complexity_score": 5,
    "preferred_format": "prose"
  },
  "system_prompt": "current adapted prompt"
}
```

On model failure, `/chat` returns a non-2xx error. It does not return simulated text.

## Notes

- `demo_user` is hardcoded for the hackathon demo.
- MediaPipe iris calibration model may still use browser localStorage; chat/session/profile state does not.
- If port `5173` is already in use, `npm run dev` fails instead of moving the frontend to a different port.
