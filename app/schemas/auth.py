from pydantic import BaseModel
from typing import Optional


class TokenData(BaseModel):
    user_id: Optional[str] = None