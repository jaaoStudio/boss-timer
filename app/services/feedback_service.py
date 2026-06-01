# app/services/feedback_service.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple

from sqlalchemy import func, case, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.database import models
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackResponse,
    FeedbackStatus,
)


DAILY_SUBMIT_LIMIT = 10
HIDDEN_FROM_PUBLIC = {"pending", "rejected"}


class FeedbackService:

    @staticmethod
    def _vote_count_subq(db: Session):
        return (
            db.query(
                models.FeedbackVote.feedback_id.label("feedback_id"),
                func.count(models.FeedbackVote.id).label("vote_count"),
            )
            .group_by(models.FeedbackVote.feedback_id)
            .subquery()
        )

    @staticmethod
    def list_feedback(
        db: Session,
        viewer_user_id: Optional[int],
        is_admin: bool,
        sort: str = "votes",  # 'votes' | 'newest'
    ) -> List[FeedbackResponse]:
        """
        清單規則：
        - 已核准（非 pending/rejected）：全部可見
        - pending / rejected：只有提交者本人或 admin 可見
        排序：
        - 預設 done 在底部
        - 其他依 sort 參數（votes 或 newest）
        """
        vote_count_subq = FeedbackService._vote_count_subq(db)

        # 是否已被 viewer 投過
        my_vote_subq = None
        if viewer_user_id is not None:
            my_vote_subq = (
                db.query(models.FeedbackVote.feedback_id)
                .filter(models.FeedbackVote.user_id == viewer_user_id)
                .subquery()
            )

        query = db.query(
            models.FeedbackItem,
            func.coalesce(vote_count_subq.c.vote_count, 0).label("vote_count"),
        ).options(
            joinedload(models.FeedbackItem.creator),
        ).outerjoin(
            vote_count_subq,
            vote_count_subq.c.feedback_id == models.FeedbackItem.id,
        )

        # 可見性過濾
        if not is_admin:
            if viewer_user_id is None:
                # 匿名：只看已核准
                query = query.filter(
                    ~models.FeedbackItem.status.in_(HIDDEN_FROM_PUBLIC)
                )
            else:
                query = query.filter(
                    or_(
                        ~models.FeedbackItem.status.in_(HIDDEN_FROM_PUBLIC),
                        models.FeedbackItem.created_by == viewer_user_id,
                    )
                )

        # 排序：done 永遠在最下，其他依使用者選擇
        done_order = case(
            (models.FeedbackItem.status == "done", 1),
            else_=0,
        )

        if sort == "newest":
            query = query.order_by(
                done_order.asc(),
                models.FeedbackItem.created_at.desc(),
            )
        else:
            query = query.order_by(
                done_order.asc(),
                func.coalesce(vote_count_subq.c.vote_count, 0).desc(),
                models.FeedbackItem.created_at.desc(),
            )

        rows = query.all()

        my_voted_ids = set()
        if my_vote_subq is not None:
            my_voted_ids = {
                r[0]
                for r in db.query(models.FeedbackVote.feedback_id)
                .filter(models.FeedbackVote.user_id == viewer_user_id)
                .all()
            }

        results: List[FeedbackResponse] = []
        for item, vote_count in rows:
            results.append(
                FeedbackResponse(
                    id=item.id,
                    type=item.type,
                    title=item.title,
                    description=item.description,
                    status=item.status,
                    created_at=item.created_at,
                    vote_count=int(vote_count or 0),
                    voted_by_me=item.id in my_voted_ids,
                    creator=item.creator,
                )
            )

        return results

    @staticmethod
    def create_feedback(
        db: Session,
        user_id: int,
        payload: FeedbackCreate,
    ) -> models.FeedbackItem:
        """建立回饋（pending 狀態，需 admin 審核）。"""
        # Rate limit: 每使用者每天最多 DAILY_SUBMIT_LIMIT 筆
        since = datetime.now(timezone.utc) - timedelta(days=1)
        count = (
            db.query(func.count(models.FeedbackItem.id))
            .filter(
                models.FeedbackItem.created_by == user_id,
                models.FeedbackItem.created_at >= since,
            )
            .scalar()
        )
        if count >= DAILY_SUBMIT_LIMIT:
            raise FeedbackRateLimited(
                f"Daily submission limit reached ({DAILY_SUBMIT_LIMIT})"
            )

        item = models.FeedbackItem(
            type=payload.type.value,
            title=payload.title.strip(),
            description=payload.description.strip() if payload.description else None,
            status="pending",
            created_by=user_id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def toggle_vote(
        db: Session,
        user_id: int,
        feedback_id: int,
    ) -> Tuple[bool, int]:
        """
        投票或取消投票。回傳 (voted_now, vote_count)。
        只能對非 pending / rejected 的項目投票。
        """
        item = (
            db.query(models.FeedbackItem)
            .filter(models.FeedbackItem.id == feedback_id)
            .first()
        )
        if not item:
            raise FeedbackNotFound(f"Feedback {feedback_id} not found")
        if item.status in HIDDEN_FROM_PUBLIC:
            raise FeedbackNotVotable("Feedback is not available for voting")

        existing = (
            db.query(models.FeedbackVote)
            .filter(
                models.FeedbackVote.feedback_id == feedback_id,
                models.FeedbackVote.user_id == user_id,
            )
            .first()
        )

        if existing:
            db.delete(existing)
            voted_now = False
        else:
            db.add(
                models.FeedbackVote(
                    feedback_id=feedback_id,
                    user_id=user_id,
                )
            )
            voted_now = True

        db.commit()

        vote_count = (
            db.query(func.count(models.FeedbackVote.id))
            .filter(models.FeedbackVote.feedback_id == feedback_id)
            .scalar()
        ) or 0

        return voted_now, int(vote_count)

    @staticmethod
    def update_status(
        db: Session,
        feedback_id: int,
        status: FeedbackStatus,
    ) -> models.FeedbackItem:
        """管理員更新狀態（含 pending → open 的核准動作）。"""
        item = (
            db.query(models.FeedbackItem)
            .filter(models.FeedbackItem.id == feedback_id)
            .first()
        )
        if not item:
            raise FeedbackNotFound(f"Feedback {feedback_id} not found")

        item.status = status.value
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def delete_feedback(db: Session, feedback_id: int) -> None:
        """管理員硬刪除（含所有投票）。"""
        item = (
            db.query(models.FeedbackItem)
            .filter(models.FeedbackItem.id == feedback_id)
            .first()
        )
        if not item:
            raise FeedbackNotFound(f"Feedback {feedback_id} not found")
        db.delete(item)
        db.commit()


class FeedbackError(Exception):
    pass


class FeedbackNotFound(FeedbackError):
    pass


class FeedbackRateLimited(FeedbackError):
    pass


class FeedbackNotVotable(FeedbackError):
    pass
