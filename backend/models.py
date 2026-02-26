from pydantic import BaseModel
from typing import Optional

class TargetModel(BaseModel):
    id: int
    industry: str
    country: str
    state: Optional[str] = None
