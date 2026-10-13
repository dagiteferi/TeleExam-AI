from __future__ import annotations

import datetime
import html

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, update, delete, or_, and_, func
from sqlalchemy.orm import aliased

from app.admin.deps import require_admin, require_superadmin, require_permission, get_admin_db
from app.db.postgres import db_conn
from app.db.redis import (
    get_redis_client,
    get_flag_key,
    get_ban_cache_key,
    get_ai_usage_key,
    get_diagnostic_trial_key,
)
from app.models.user import User
from app.models.department import Department
from app.models.exam_result import ExamResult
from app.models.course import Course
from app.models.user_answer import UserAnswer
from app.models.user_topic_error import UserTopicError
from app.models.bookmark import Bookmark
from app.models.payment_request import PaymentRequest
from app.models.activity_log import ActivityLog
from app.schemas.admin import (
    PlatformUserResponse,
    UserAdminUpdate,
    UserFlaggedResponse,
    GrantFullAccessRequest,
    GrantFullAccessResponse,
    UserDetailResponse,
    UserExamSummary,
    InvitedUserSummary,
    DepartmentListItem,
)
from app.core.notify import send_telegram_message
from app.core.utils import display_name
from redis.asyncio import Redis

router = APIRouter(prefix="/users")


# ─────────────────────────────────────────────
#  STATIC routes MUST come before /{user_id}/*
# ─────────────────────────────────────────────

@router.get("/departments", response_model=list[DepartmentListItem], dependencies=[Depends(require_permission("view_users"))])
async def list_user_departments(
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[DepartmentListItem]:
    """Returns all departments for filtering users."""
    result = await conn.execute(select(Department).order_by(Department.name))
    return [DepartmentListItem(**dict(row)) for row in result.mappings()]


@router.get("/", response_model=list[PlatformUserResponse], dependencies=[Depends(require_permission("view_users"))])
async def get_all_users(
    conn: AsyncConnection = Depends(get_admin_db),
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
    is_pro: bool | None = None,
    is_banned: bool | None = None,
    invited_by: UUID | None = None,
    department_id: UUID | None = None,
) -> list[PlatformUserResponse]:
    """Requires: view_users permission or superadmin."""
    Inviter = aliased(User)

    exam_stats_sq = (
        select(
            ExamResult.user_id,
            func.count(ExamResult.id).label("exams_count"),
            func.avg(ExamResult.score_percent).label("avg_score"),
        )
        .group_by(ExamResult.user_id)
        .subquery()
    )

    query = (
        select(
            User.id,
            User.telegram_id,
            User.telegram_username,
            User.first_name,
            User.last_name,
            User.department_id,
            Department.name.label("department_name"),
            Department.code.label("department_code"),
            User.invited_by_user_id,
            Inviter.telegram_username.label("invited_by_username"),
            Inviter.first_name.label("invited_by_name"),
            User.invite_count,
            User.is_pro,
            User.is_full_access,
            User.plan_expiry,
            User.is_banned,
            User.ban_reason,
            User.banned_until,
            User.created_at,
            User.updated_at,
            func.coalesce(exam_stats_sq.c.exams_count, 0).label("exams_count"),
            exam_stats_sq.c.avg_score.label("avg_score"),
        )
        .outerjoin(Department, User.department_id == Department.id)
        .outerjoin(Inviter, User.invited_by_user_id == Inviter.id)
        .outerjoin(exam_stats_sq, User.id == exam_stats_sq.c.user_id)
    )

    if search:
        try:
            tid = int(search)
            query = query.where(User.telegram_id == tid)
        except ValueError:
            search_query = f"%{search}%"
            query = query.where(
                or_(
                    User.telegram_username.ilike(search_query),
                    User.first_name.ilike(search_query),
                    User.last_name.ilike(search_query),
                    Department.name.ilike(search_query),
                )
            )

    if department_id is not None:
        query = query.where(User.department_id == department_id)

    if is_pro is not None:
        query = query.where(User.is_pro == is_pro)

    if is_banned is not None:
        query = query.where(User.is_banned == is_banned)

    if invited_by:
        query = query.where(User.invited_by_user_id == invited_by)

    query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await conn.execute(query)
    users = result.mappings().all()
    return [
        PlatformUserResponse(
            **{
                **dict(u),
                "avg_score": float(u["avg_score"]) if u.get("avg_score") is not None else None,
            }
        )
        for u in users
    ]



@router.get("/flagged", response_model=list[UserFlaggedResponse], dependencies=[Depends(require_permission("view_users"))])
async def get_flagged_users(
    conn: AsyncConnection = Depends(get_admin_db),
    redis: Redis = Depends(get_redis_client),
) -> list[UserFlaggedResponse]:
    """Requires: view_users permission or superadmin."""
    pg_banned_users_result = await conn.execute(select(User).where(User.is_banned == True))
    pg_banned_users = pg_banned_users_result.mappings().all()

    redis_flagged_keys = []
    async for key in redis.scan_iter(f"{get_flag_key('*')}*"):
        redis_flagged_keys.append(key)

    redis_flagged_telegram_ids = []
    for key in redis_flagged_keys:
        try:
            redis_flagged_telegram_ids.append(int(key.split(':')[-1]))
        except (ValueError, IndexError):
            continue

    flagged_users_data = {}

    for user in pg_banned_users:
        flagged_users_data[user["telegram_id"]] = UserFlaggedResponse(
            user_id=user["id"], telegram_id=user["telegram_id"],
            is_banned_pg=True, ban_reason_pg=user["ban_reason"], flag_redis=None,
        )

    if redis_flagged_telegram_ids:
        redis_users_result = await conn.execute(select(User).where(User.telegram_id.in_(redis_flagged_telegram_ids)))
        redis_users = redis_users_result.mappings().all()

        for user in redis_users:
            flag_key = get_flag_key(user["telegram_id"])
            flag_value = await redis.get(flag_key)
            if user["telegram_id"] in flagged_users_data:
                flagged_users_data[user["telegram_id"]].flag_redis = flag_value
            else:
                flagged_users_data[user["telegram_id"]] = UserFlaggedResponse(
                    user_id=user["id"], telegram_id=user["telegram_id"],
                    is_banned_pg=user["is_banned"], ban_reason_pg=user["ban_reason"], flag_redis=flag_value,
                )

    return list(flagged_users_data.values())


@router.post(
    "/grant-full-access",
    response_model=GrantFullAccessResponse,
    dependencies=[Depends(require_superadmin)],
    summary="Grant a user unlimited access (bypasses all invite locks)",
)
async def grant_full_access(
    body: GrantFullAccessRequest,
    conn: AsyncConnection = Depends(get_admin_db),
) -> GrantFullAccessResponse:
    """
    Superadmin only.
    Sets `is_full_access = True` for the user with the given `telegram_id`.
    """
    result = await conn.execute(select(User).where(User.telegram_id == body.telegram_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": f"No user found with telegram_id={body.telegram_id}"}},
        )

    await conn.execute(
        update(User)
        .where(User.telegram_id == body.telegram_id)
        .values(is_full_access=True)
    )
    await conn.commit()

    await send_telegram_message(
        body.telegram_id,
        "🔓 <b>Full Access Granted!</b>\n\n"
        "You have been granted <b>unlimited access</b> to all courses and exam years by an administrator.\n"
        "You can now use all content without any invite restrictions."
    )

    return GrantFullAccessResponse(
        telegram_id=body.telegram_id,
        is_full_access=True,
        message=f"✅ Full access granted to telegram_id={body.telegram_id}. They can now use all content without invites.",
    )


@router.post(
    "/revoke-full-access",
    response_model=GrantFullAccessResponse,
    dependencies=[Depends(require_superadmin)],
    summary="Revoke unlimited access — user returns to normal invite-based locking",
)
async def revoke_full_access(
    body: GrantFullAccessRequest,
    conn: AsyncConnection = Depends(get_admin_db),
) -> GrantFullAccessResponse:
    """
    Superadmin only.
    Sets `is_full_access = False` for the user with the given `telegram_id`.
    """
    result = await conn.execute(select(User).where(User.telegram_id == body.telegram_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": f"No user found with telegram_id={body.telegram_id}"}},
        )

    await conn.execute(
        update(User)
        .where(User.telegram_id == body.telegram_id)
        .values(is_full_access=False)
    )
    await conn.commit()

    await send_telegram_message(
        body.telegram_id,
        "🔒 <b>Full Access Revoked</b>\n\n"
        "Your unlimited access has been revoked by an administrator.\n"
        "You are now subject to the normal invite-based content locking system."
    )

    return GrantFullAccessResponse(
        telegram_id=body.telegram_id,
        is_full_access=False,
        message=f"🔒 Full access revoked from telegram_id={body.telegram_id}. Normal invite locks restored.",
    )


# ─────────────────────────────────────────────
#  PARAMETERIZED routes  /{user_id}/*
# ─────────────────────────────────────────────

@router.get("/{user_id}", response_model=UserDetailResponse, dependencies=[Depends(require_permission("view_users"))])
async def get_user_detail(
    user_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
) -> UserDetailResponse:
    """Returns full details, department, inviter, exam statistics, and referrals for a user."""
    Inviter = aliased(User)

    user_stmt = (
        select(
            User.id,
            User.telegram_id,
            User.telegram_username,
            User.first_name,
            User.last_name,
            User.department_id,
            Department.name.label("department_name"),
            Department.code.label("department_code"),
            User.invite_code,
            User.invite_count,
            User.invited_by_user_id,
            Inviter.telegram_username.label("invited_by_username"),
            Inviter.first_name.label("invited_by_name"),
            User.is_pro,
            User.is_full_access,
            User.plan_expiry,
            User.is_banned,
            User.ban_reason,
            User.banned_until,
            User.created_at,
            User.updated_at,
        )
        .outerjoin(Department, User.department_id == Department.id)
        .outerjoin(Inviter, User.invited_by_user_id == Inviter.id)
        .where(User.id == user_id)
    )
    result = await conn.execute(user_stmt)
    user_row = result.mappings().one_or_none()
    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": "User not found"}},
        )

    user_dict = dict(user_row)

    # Aggregated Exam Statistics
    stats_stmt = (
        select(
            func.count(ExamResult.id).label("total_exams"),
            func.avg(ExamResult.score_percent).label("avg_score"),
            func.coalesce(func.sum(ExamResult.question_count), 0).label("total_questions"),
            func.coalesce(func.sum(ExamResult.correct_count), 0).label("total_correct"),
            func.coalesce(func.sum(ExamResult.wrong_count), 0).label("total_wrong"),
        )
        .where(ExamResult.user_id == user_id)
    )
    stats_res = await conn.execute(stats_stmt)
    stats_row = stats_res.mappings().one()

    user_dict["total_exams_taken"] = stats_row["total_exams"] or 0
    user_dict["average_score"] = float(stats_row["avg_score"]) if stats_row["avg_score"] is not None else None
    user_dict["total_questions_answered"] = int(stats_row["total_questions"] or 0)
    user_dict["total_correct_answers"] = int(stats_row["total_correct"] or 0)
    user_dict["total_wrong_answers"] = int(stats_row["total_wrong"] or 0)

    # Recent 5 Exams
    recent_exams_stmt = (
        select(
            ExamResult.id,
            Course.name.label("course_name"),
            ExamResult.mode,
            ExamResult.question_count,
            ExamResult.correct_count,
            ExamResult.wrong_count,
            ExamResult.score_percent,
            ExamResult.duration_seconds,
            ExamResult.submitted_at,
        )
        .outerjoin(Course, ExamResult.course_id == Course.id)
        .where(ExamResult.user_id == user_id)
        .order_by(ExamResult.submitted_at.desc())
        .limit(5)
    )
    recent_res = await conn.execute(recent_exams_stmt)
    user_dict["recent_exams"] = [
        UserExamSummary(
            id=r["id"],
            course_name=r["course_name"] or "General Practice",
            mode=r["mode"],
            question_count=r["question_count"],
            correct_count=r["correct_count"],
            wrong_count=r["wrong_count"],
            score_percent=float(r["score_percent"]),
            duration_seconds=r["duration_seconds"],
            submitted_at=r["submitted_at"],
        )
        for r in recent_res.mappings()
    ]

    # Invited Users (up to 10)
    invited_stmt = (
        select(
            User.id,
            User.telegram_id,
            User.telegram_username,
            User.first_name,
            User.last_name,
            User.is_pro,
            User.is_full_access,
            User.created_at,
        )
        .where(User.invited_by_user_id == user_id)
        .order_by(User.created_at.desc())
        .limit(10)
    )
    invited_res = await conn.execute(invited_stmt)
    user_dict["invited_users"] = [
        InvitedUserSummary(**dict(r))
        for r in invited_res.mappings()
    ]

    return UserDetailResponse(**user_dict)


@router.patch("/{user_id}", response_model=PlatformUserResponse, dependencies=[Depends(require_permission("view_users"))])
async def update_user_by_admin(
    user_id: UUID,
    user_update: UserAdminUpdate,
    conn: AsyncConnection = Depends(get_admin_db),
    redis: Redis = Depends(get_redis_client),
) -> PlatformUserResponse:
    """Requires: view_users permission or superadmin."""
    values = user_update.model_dump(exclude_unset=True)
    if "is_banned" in values:
        # A ban set here is permanent; lifting it clears the reason and any end time
        values["banned_until"] = None
        if not values["is_banned"]:
            values["ban_reason"] = None
    stmt = update(User).where(User.id == user_id).values(**values)
    await conn.execute(stmt)
    await conn.commit()

    result = await conn.execute(select(User).where(User.id == user_id))
    updated_user = result.mappings().one_or_none()
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "user_not_found", "message": "User not found"}})
    if "is_banned" in values:
        await redis.delete(get_ban_cache_key(updated_user["telegram_id"]))
    return PlatformUserResponse(**updated_user)


@router.post("/{user_id}/toggle-pro", response_model=PlatformUserResponse, dependencies=[Depends(require_permission("view_users"))])
async def toggle_user_pro(
    user_id: UUID,
    is_pro: bool | None = None,
    conn: AsyncConnection = Depends(get_admin_db),
) -> PlatformUserResponse:
    """
    Toggles or explicitly sets the PRO status of a user.
    - No query param → toggle current value
    - ?is_pro=true  → force PRO
    - ?is_pro=false → force Free (revoke PRO)
    Sends a Telegram notification to the user after changing their status.
    """
    result = await conn.execute(select(User).where(User.id == user_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": "User not found"}},
        )

    new_pro_status = not user["is_pro"] if is_pro is None else is_pro

    await conn.execute(update(User).where(User.id == user_id).values(is_pro=new_pro_status))
    await conn.commit()

    # Send Telegram notification
    name = display_name(user)
    if new_pro_status:
        await send_telegram_message(
            user["telegram_id"],
            f"⭐ <b>You're now PRO, {name}!</b>\n\n"
            "An administrator has upgraded your account to <b>PRO</b>.\n\n"
            "You now have access to:\n"
            "• 🤖 <b>AI Tutor</b> — unlimited explanations & study plans\n"
            "• 📚 <b>All Courses & Exam Years</b> — full content unlocked\n"
            "• 🎯 <b>Unlimited Daily Questions</b>\n\n"
            "Enjoy your PRO experience! 🎉"
        )
    else:
        await send_telegram_message(
            user["telegram_id"],
            f"🔓 <b>PRO Access Revoked, {name}</b>\n\n"
            "Your <b>PRO</b> subscription has been revoked by an administrator.\n"
            "Your account has been returned to the <b>Free</b> tier.\n\n"
            "You can still access free content and earn invites to unlock more.\n"
            "Contact support if you believe this was a mistake."
        )

    updated_result = await conn.execute(select(User).where(User.id == user_id))
    updated_user = updated_result.mappings().one_or_none()
    return PlatformUserResponse(**updated_user)


@router.post("/{user_id}/reset-access", response_model=PlatformUserResponse, dependencies=[Depends(require_superadmin)])
async def reset_user_access(
    user_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
) -> PlatformUserResponse:
    """
    Superadmin only.
    Fully resets a user's access: is_pro=False, is_full_access=False, invite_count=0.
    Notifies the user via Telegram.
    """
    result = await conn.execute(select(User).where(User.id == user_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": "User not found"}},
        )

    await conn.execute(
        update(User)
        .where(User.id == user_id)
        .values(is_pro=False, is_full_access=False, invite_count=0)
    )
    await conn.commit()

    name = display_name(user)
    await send_telegram_message(
        user["telegram_id"],
        f"⚠️ <b>Account Access Reset, {name}</b>\n\n"
        "Your account access has been fully reset by an administrator:\n"
        "• PRO status: <b>Removed</b>\n"
        "• Full access: <b>Removed</b>\n"
        "• Invite count: <b>Reset to 0</b>\n\n"
        "You are now on the Free tier. Contact support if you have questions."
    )

    updated_result = await conn.execute(select(User).where(User.id == user_id))
    updated_user = updated_result.mappings().one_or_none()
    return PlatformUserResponse(**updated_user)


@router.delete("/{user_id}", dependencies=[Depends(require_superadmin)])
async def delete_user(
    user_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
    redis: Redis = Depends(get_redis_client),
):
    """
    Superadmin only.
    Permanently deletes a user and all their data (answers, exam results, topic errors,
    bookmarks, payment requests). Activity logs are kept but detached from the user,
    and users they invited keep their accounts with the referral link cleared.
    """
    result = await conn.execute(select(User.telegram_id).where(User.id == user_id))
    telegram_id = result.scalar_one_or_none()
    if telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": "User not found"}},
        )

    # Children first — these foreign keys have no ON DELETE CASCADE
    user_exam_ids = select(ExamResult.id).where(ExamResult.user_id == user_id)
    await conn.execute(
        delete(UserAnswer).where(
            or_(UserAnswer.user_id == user_id, UserAnswer.exam_result_id.in_(user_exam_ids))
        )
    )
    await conn.execute(delete(ExamResult).where(ExamResult.user_id == user_id))
    await conn.execute(delete(UserTopicError).where(UserTopicError.user_id == user_id))
    await conn.execute(delete(Bookmark).where(Bookmark.user_id == user_id))
    await conn.execute(delete(PaymentRequest).where(PaymentRequest.user_id == user_id))
    await conn.execute(update(ActivityLog).where(ActivityLog.user_id == user_id).values(user_id=None))
    await conn.execute(update(User).where(User.invited_by_user_id == user_id).values(invited_by_user_id=None))
    await conn.execute(delete(User).where(User.id == user_id))
    await conn.commit()

    await redis.delete(
        get_flag_key(telegram_id),
        get_ban_cache_key(telegram_id),
        get_ai_usage_key(telegram_id),
        get_diagnostic_trial_key(telegram_id),
    )
    return {"message": f"User telegram_id={telegram_id} deleted permanently"}


@router.post("/{user_id}/ban", response_model=PlatformUserResponse, dependencies=[Depends(require_permission("ban_user"))])
async def ban_user(
    user_id: UUID,
    reason: str,
    duration_hours: int | None = None,
    conn: AsyncConnection = Depends(get_admin_db),
    redis: Redis = Depends(get_redis_client),
) -> PlatformUserResponse:
    """Requires: ban_user permission or superadmin. No duration_hours = permanent ban."""
    if duration_hours is not None and duration_hours <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": {"code": "invalid_duration", "message": "duration_hours must be positive"}})
    banned_until = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=duration_hours)
        if duration_hours else None
    )
    stmt = update(User).where(User.id == user_id).values(is_banned=True, ban_reason=reason, banned_until=banned_until)
    await conn.execute(stmt)
    await conn.commit()

    result = await conn.execute(select(User).where(User.id == user_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "user_not_found", "message": "User not found"}})

    flag_key = get_flag_key(user["telegram_id"])
    ttl = duration_hours * 3600 if duration_hours else 24 * 3600
    await redis.set(flag_key, "blocked", ex=ttl)
    await redis.delete(get_ban_cache_key(user["telegram_id"]))

    name = display_name(user)
    duration_msg = f" for {duration_hours} hour(s)" if duration_hours else ""
    await send_telegram_message(
        user["telegram_id"],
        f"🚫 <b>Account Restricted, {name}</b>\n\n"
        f"Your account has been <b>banned{duration_msg}</b> by an administrator.\n"
        f"Reason: <i>{html.escape(reason)}</i>\n\n"
        "Contact support if you believe this was a mistake."
    )

    return PlatformUserResponse(**user)


@router.post("/{user_id}/unban", response_model=PlatformUserResponse, dependencies=[Depends(require_permission("ban_user"))])
async def unban_user(
    user_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
    redis: Redis = Depends(get_redis_client),
) -> PlatformUserResponse:
    """Requires: ban_user permission or superadmin."""
    stmt = update(User).where(User.id == user_id).values(is_banned=False, ban_reason=None, banned_until=None)
    await conn.execute(stmt)
    await conn.commit()

    result = await conn.execute(select(User).where(User.id == user_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "user_not_found", "message": "User not found"}})

    flag_key = get_flag_key(user["telegram_id"])
    await redis.delete(flag_key, get_ban_cache_key(user["telegram_id"]))

    name = display_name(user)
    await send_telegram_message(
        user["telegram_id"],
        f"✅ <b>Account Restored, {name}!</b>\n\n"
        "Your account restriction has been lifted by an administrator.\n"
        "You can now use TeleExam again. Welcome back!"
    )

    return PlatformUserResponse(**user)
