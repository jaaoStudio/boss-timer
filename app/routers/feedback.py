# app/routers/feedback.py
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import models
from app.database.database import get_db
from app.dependencies import get_current_admin_user, limiter
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackListResponse,
    FeedbackResponse,
    FeedbackStatusUpdate,
    FeedbackVoteResponse,
)
from app.services.auth_service import get_current_user_from_token
from app.services.feedback_service import (
    FeedbackNotFound,
    FeedbackNotVotable,
    FeedbackRateLimited,
    FeedbackService,
)


router = APIRouter(prefix="/feedback", tags=["feedback"])


def _get_optional_user(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """匿名用戶回傳 None，登入用戶回傳 User。"""
    if not access_token:
        return None
    try:
        return get_current_user_from_token(access_token, db)
    except HTTPException:
        return None


def _require_user(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> models.User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required",
        )
    return get_current_user_from_token(access_token, db)


@router.get("/", response_model=FeedbackListResponse)
@limiter.limit("60/minute")
async def list_feedback(
    request: Request,
    sort: str = Query("votes", pattern="^(votes|newest)$"),
    db: Session = Depends(get_db),
    viewer: Optional[models.User] = Depends(_get_optional_user),
):
    """取得回饋清單（匿名可看已核准項目，登入後可額外看到自己的 pending/rejected）。"""
    items = FeedbackService.list_feedback(
        db,
        viewer_user_id=viewer.id if viewer else None,
        is_admin=bool(viewer and viewer.is_admin),
        sort=sort,
    )
    return FeedbackListResponse(items=items, total=len(items))


@router.post("/", response_model=FeedbackResponse, status_code=201)
@limiter.limit("20/minute")
async def create_feedback(
    request: Request,
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(_require_user),
):
    """建立回饋（pending 狀態，需 admin 審核）。"""
    try:
        item = FeedbackService.create_feedback(db, user_id=user.id, payload=payload)
    except FeedbackRateLimited as e:
        raise HTTPException(status_code=429, detail=str(e))

    return FeedbackResponse(
        id=item.id,
        type=item.type,
        title=item.title,
        description=item.description,
        status=item.status,
        created_at=item.created_at,
        vote_count=0,
        voted_by_me=False,
        creator=user,
    )


@router.post("/{feedback_id}/vote", response_model=FeedbackVoteResponse)
@limiter.limit("60/minute")
async def toggle_vote(
    request: Request,
    feedback_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(_require_user),
):
    """投票或取消投票（toggle）。"""
    try:
        voted_now, vote_count = FeedbackService.toggle_vote(
            db, user_id=user.id, feedback_id=feedback_id
        )
    except FeedbackNotFound:
        raise HTTPException(status_code=404, detail="Feedback not found")
    except FeedbackNotVotable as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FeedbackVoteResponse(
        feedback_id=feedback_id,
        voted=voted_now,
        vote_count=vote_count,
    )


@router.patch("/{feedback_id}", response_model=FeedbackResponse)
@limiter.limit("60/minute")
async def admin_update_status(
    request: Request,
    feedback_id: int,
    payload: FeedbackStatusUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin_user),
):
    """管理員更新狀態（pending → open 視為核准）。"""
    try:
        item = FeedbackService.update_status(db, feedback_id, payload.status)
    except FeedbackNotFound:
        raise HTTPException(status_code=404, detail="Feedback not found")

    # 取回最新票數
    from sqlalchemy import func
    vote_count = (
        db.query(func.count(models.FeedbackVote.id))
        .filter(models.FeedbackVote.feedback_id == feedback_id)
        .scalar()
    ) or 0

    return FeedbackResponse(
        id=item.id,
        type=item.type,
        title=item.title,
        description=item.description,
        status=item.status,
        created_at=item.created_at,
        vote_count=int(vote_count),
        voted_by_me=False,
        creator=item.creator,
    )


@router.delete("/{feedback_id}", status_code=204)
@limiter.limit("30/minute")
async def admin_delete(
    request: Request,
    feedback_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin_user),
):
    """管理員刪除回饋（連同所有投票一併刪除）。"""
    try:
        FeedbackService.delete_feedback(db, feedback_id)
    except FeedbackNotFound:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return None
