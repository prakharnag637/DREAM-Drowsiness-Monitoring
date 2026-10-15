from datetime import datetime
from pydantic import BaseModel

class HealthResponse(BaseModel):
    ok: bool
    service: str
    camera_available: bool

class SessionOut(BaseModel):
    id: int
    session_code: str
    started_at: datetime
    ended_at: datetime | None
    status: str
    class Config:
        from_attributes = True
