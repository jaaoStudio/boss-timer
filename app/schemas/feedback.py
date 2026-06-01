# app/schemas/feedback.py
from enum import Enum
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from .auth import PublicUser


class FeedbackType(str, Enum):
    bug = "bug"
    feature = "feature"


class FeedbackStatus(str, Enum):
    pending = "pending"
    open = "open"
    planning = "planning"
    done = "done"
    rejected = "rejected"


class FeedbackCreate(BaseModel):
    type: FeedbackType
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class FeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus


class FeedbackResponse(BaseModel):
    id: int
    type: FeedbackType
    title: str
    description: Optional[str] = None
    status: FeedbackStatus
    created_at: datetime
    vote_count: int = 0
    voted_by_me: bool = False
    creator: Optional[PublicUser] = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackListResponse(BaseModel):
    items: List[FeedbackResponse]
    total: int


class FeedbackVoteResponse(BaseModel):
    feedback_id: int
    voted: bool
    vote_count: int
