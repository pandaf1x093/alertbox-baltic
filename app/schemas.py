from pydantic import BaseModel
from datetime import datetime

class ReportOut(BaseModel):
    id: int
    created_at: datetime
    period: str
    region: str
    lang: str
    content: str

    class Config:
        from_attributes = True
