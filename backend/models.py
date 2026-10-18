from pydantic import BaseModel
from typing import Any
from typing import Literal

class GazeEvent(BaseModel):
    zone:       str
    visits:     int
    flag:       Literal['smooth', 'confusion', 'skipped', 'skim']
    word_count: int = 0

class HistoryMessage(BaseModel):
    role:    Literal['user', 'assistant']
    content: str

class ChatRequest(BaseModel):
    user_id:              str
    message:              str
    session_id:           str | None = None
    history:              list[HistoryMessage] = []
    previous_response_id: str | None = None
    gaze_events:          list[GazeEvent] = []

class UserProfileOut(BaseModel):
    complexity_score:  int
    preferred_format:  str

class ChatResponse(BaseModel):
    response_id:          str
    text:                 str
    reward:               float | None
    user_profile:         UserProfileOut
    system_prompt:        str
    follow_up_questions:  list[str] = []

class SessionEndRequest(BaseModel):
    user_id:    str
    session_id: str

class SaveSessionRequest(BaseModel):
    user_id: str
    session: dict[str, Any]

class SaveProfileRequest(BaseModel):
    user_id: str
    profile: dict[str, Any]
