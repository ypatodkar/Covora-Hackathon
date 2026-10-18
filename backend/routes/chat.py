import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from models import ChatRequest, ChatResponse, UserProfileOut
from db.users import get_user, update_user
from db.episodes import write_episode, get_recent_episodes
from db.sessions import increment_turn, start_session
from services.reward import compute_reward, update_profile_from_reward
from services.prompt_builder import build_system_prompt
from services.nvidia import generate_response, generate_follow_up_questions

def _generate(system_prompt: str, message: str, history: list[dict] = None, complexity: int = 5) -> str:
    try:
        max_tokens = 4096 if complexity >= 8 else 1024
        return generate_response(system_prompt, message, history, max_tokens=max_tokens)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NVIDIA generation failed: {e}") from e

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    user    = get_user(req.user_id)
    reward  = None
    if req.session_id:
        start_session(req.user_id, req.session_id)

    # Process gaze from previous response
    if req.previous_response_id and req.gaze_events:
        reward          = compute_reward(req.gaze_events)
        profile_updates = update_profile_from_reward(user, reward, req.gaze_events, req.message)

        if profile_updates:
            update_user(req.user_id, profile_updates)
            user.update(profile_updates)

        # Write episodic memory
        recent  = get_recent_episodes(req.user_id, limit=1)
        turn_no = (recent[0].get("turn", 0) + 1) if recent else 1
        session_id = req.session_id or (req.previous_response_id[:8] if req.previous_response_id else "unknown")

        write_episode({
            "user_id":        req.user_id,
            "session_id":     session_id,
            "turn":           turn_no,
            "response_id":    req.previous_response_id,
            "gaze_events":    [e.model_dump() for e in req.gaze_events],
            "reward":         reward,
            "profile_after":  {
                "complexity_score": user.get("complexity_score"),
                "preferred_format": user.get("preferred_format"),
            },
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        })
        increment_turn(session_id)

    # Build adapted system prompt from current user profile + CoALA semantic retrieval
    system_prompt = build_system_prompt(user, req.message)

    history = [{"role": m.role, "content": m.content} for m in req.history]
    text    = _generate(system_prompt, req.message, history, complexity=user.get("complexity_score", 5))
    response_id = str(uuid.uuid4())
    if req.session_id:
        increment_turn(req.session_id)

    follow_ups = generate_follow_up_questions(req.message, text)

    return ChatResponse(
        response_id          = response_id,
        text                 = text,
        reward               = reward,
        user_profile         = UserProfileOut(
            complexity_score = user.get("complexity_score", 5),
            preferred_format = user.get("preferred_format", "prose"),
        ),
        system_prompt        = system_prompt,
        follow_up_questions  = follow_ups,
    )
