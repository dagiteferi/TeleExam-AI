from __future__ import annotations

import html

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, update

from app.admin.deps import require_superadmin, get_admin_db
from app.db.postgres import db_conn
from app.core.config import settings
from app.models.bank_account import BankAccount
from app.models.department import Department
from app.models.payment_request import PaymentRequest
from app.models.user import User
from app.schemas.payment import BankAccountCreate, BankAccountUpdate, BankAccountResponse, PaymentRequestResponse
from app.core.notify import send_telegram_message
from app.core.utils import display_name

router = APIRouter(prefix="/payments")


# ─────────────────────────────────────────────
#  BANK ACCOUNTS CRUD
# ─────────────────────────────────────────────

@router.get("/banks", response_model=list[BankAccountResponse], dependencies=[Depends(require_superadmin)])
async def get_banks(
    conn: AsyncConnection = Depends(get_admin_db),
    limit: int = 100,
    offset: int = 0,
) -> list[BankAccountResponse]:
    query = select(BankAccount).order_by(BankAccount.created_at.desc()).limit(limit).offset(offset)
    result = await conn.execute(query)
    banks = result.mappings().all()
    return [BankAccountResponse(**b) for b in banks]


@router.post("/banks", response_model=BankAccountResponse, dependencies=[Depends(require_superadmin)])
async def create_bank(
    bank_in: BankAccountCreate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> BankAccountResponse:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    import uuid, datetime
    new_id = uuid.uuid4()
    now = datetime.datetime.utcnow()
    stmt = (
        pg_insert(BankAccount)
        .values(
            id=new_id,
            created_at=now,
            updated_at=now,
            **bank_in.model_dump(),
        )
        .returning(BankAccount)
    )
    result = await conn.execute(stmt)
    await conn.commit()
    row = result.mappings().one()
    return BankAccountResponse(**row)


@router.put("/banks/{bank_id}", response_model=BankAccountResponse, dependencies=[Depends(require_superadmin)])
async def update_bank(
    bank_id: UUID,
    bank_update: BankAccountUpdate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> BankAccountResponse:
    import datetime
    values = bank_update.model_dump(exclude_unset=True)
    values["updated_at"] = datetime.datetime.utcnow()
    stmt = update(BankAccount).where(BankAccount.id == bank_id).values(**values)
    await conn.execute(stmt)
    await conn.commit()

    result = await conn.execute(select(BankAccount).where(BankAccount.id == bank_id))
    updated = result.mappings().one_or_none()
    if not updated:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return BankAccountResponse(**updated)


@router.delete("/banks/{bank_id}", dependencies=[Depends(require_superadmin)])
async def delete_bank(
    bank_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
):
    from sqlalchemy import delete
    result = await conn.execute(delete(BankAccount).where(BankAccount.id == bank_id))
    await conn.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return {"message": "Bank account deleted successfully"}


# ─────────────────────────────────────────────
#  PAYMENT REQUESTS MANAGEMENT
# ─────────────────────────────────────────────

@router.get("/requests", response_model=list[PaymentRequestResponse], dependencies=[Depends(require_superadmin)])
async def get_payment_requests(
    conn: AsyncConnection = Depends(get_admin_db),
    status_filter: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[PaymentRequestResponse]:
    query = select(PaymentRequest)
    if status_filter:
        query = query.where(PaymentRequest.status == status_filter)
    query = query.order_by(PaymentRequest.created_at.desc()).limit(limit).offset(offset)
    
    result = await conn.execute(query)
    requests = result.mappings().all()
    return await _with_labels(conn, requests)


def _amount_birr(kind: str | None) -> int:
    return settings.DUAL_DEPT_PRICE_BIRR if kind == "dual_department" else settings.PRO_PRICE_BIRR


async def _with_labels(conn: AsyncConnection, requests) -> list[PaymentRequestResponse]:
    """Adds the expected amount and the dual target department's name to each request."""
    dept_ids = {r["target_department_id"] for r in requests if r.get("target_department_id")}
    names: dict = {}
    if dept_ids:
        rows = await conn.execute(select(Department.id, Department.name).where(Department.id.in_(dept_ids)))
        names = {row.id: row.name for row in rows}
    return [
        PaymentRequestResponse(
            **r,
            target_department_name=names.get(r.get("target_department_id")),
            amount_birr=_amount_birr(r.get("kind")),
        )
        for r in requests
    ]


@router.post("/requests/{request_id}/approve", response_model=PaymentRequestResponse)
async def approve_payment_request(
    request_id: UUID,
    admin: dict = Depends(require_superadmin),
    conn: AsyncConnection = Depends(get_admin_db),
) -> PaymentRequestResponse:
    import datetime
    # 1. Fetch the request
    result = await conn.execute(select(PaymentRequest).where(PaymentRequest.id == request_id))
    pr = result.mappings().one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Payment request not found")

    if pr["status"] == "approved":
        raise HTTPException(status_code=400, detail="Already approved")

    # 2. Check the payment can be applied before changing anything.
    user_id = pr["user_id"]
    kind = pr.get("kind") or "pro"
    user_result = await conn.execute(select(User).where(User.id == user_id))
    user = user_result.mappings().one()
    if kind == "dual_department":
        # The dual fee is only an add-on: it must never stand in for the PRO payment.
        if not user["is_pro"] and not user["is_full_access"]:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"This is a Dual Degree payment ({settings.DUAL_DEPT_PRICE_BIRR} Birr) and cannot make the user PRO. "
                    f"The user is not PRO yet: approve their {settings.PRO_PRICE_BIRR} Birr PRO payment first, or reject this one."
                ),
            )
        target_department_id = pr.get("target_department_id") or user["secondary_department_id"]
        if not target_department_id:
            raise HTTPException(status_code=400, detail="This Dual Degree payment has no second department selected.")
        if target_department_id == user["department_id"]:
            raise HTTPException(status_code=400, detail="The second department is the same as the user's main department.")
    elif user["is_pro"]:
        raise HTTPException(
            status_code=400,
            detail="The user is already PRO, so this is probably a duplicate PRO payment. Reject it instead.",
        )

    now = datetime.datetime.utcnow()

    # 3. Update request status (no admin_id — superadmin has no DB row)
    await conn.execute(
        update(PaymentRequest)
        .where(PaymentRequest.id == request_id)
        .values(status="approved", rejection_reason=None, updated_at=now)
    )

    # 4. Apply the paid upgrade
    if kind == "dual_department":
        await conn.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                secondary_department_id=target_department_id,
                secondary_department_unlocked=True,
                updated_at=now,
            )
        )
    else:
        await conn.execute(update(User).where(User.id == user_id).values(is_pro=True, updated_at=now))

    await conn.commit()

    # 5. Notify user
    name = display_name(user)

    if kind == "dual_department":
        dept_name = await conn.scalar(select(Department.name).where(Department.id == target_department_id))
        notify_text = (
            f"🎓 <b>Dual Degree Payment Approved!</b>\n\n"
            f"Congratulations {name}, your Dual Degree payment was verified.\n"
            f"Your second department <b>{html.escape((dept_name or '').title())}</b> is now fully unlocked — "
            "exams, practice, progress and AI study plans.\n\n"
            "Tap <b>🔄 Switch Department</b> in the menu to move between your departments. Happy studying! 🎉"
        )
    else:
        notify_text = (
            f"✅ <b>Payment Approved!</b>\n\n"
            f"Congratulations {name}, your payment screenshot was verified.\n"
            "Your account has been upgraded to <b>PRO</b>!\n\n"
            "You now have unlimited access to the AI Tutor and all exams. Happy studying! 🎉"
        )
    await send_telegram_message(user["telegram_id"], notify_text, refresh_menu=True)

    pr_updated_result = await conn.execute(select(PaymentRequest).where(PaymentRequest.id == request_id))
    return (await _with_labels(conn, [pr_updated_result.mappings().one()]))[0]


@router.post("/requests/{request_id}/reject", response_model=PaymentRequestResponse)
async def reject_payment_request(
    request_id: UUID,
    reason: str | None = None,
    admin: dict = Depends(require_superadmin),
    conn: AsyncConnection = Depends(get_admin_db),
) -> PaymentRequestResponse:
    """Optional `reason` is stored on the request and sent to the user in the Telegram rejection message."""
    import datetime
    result = await conn.execute(select(PaymentRequest).where(PaymentRequest.id == request_id))
    pr = result.mappings().one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Payment request not found")

    if pr["status"] == "rejected":
        raise HTTPException(status_code=400, detail="Already rejected")

    reason = (reason or "").strip()[:500]
    now = datetime.datetime.utcnow()
    await conn.execute(
        update(PaymentRequest)
        .where(PaymentRequest.id == request_id)
        .values(status="rejected", rejection_reason=reason or None, updated_at=now)
    )
    await conn.commit()

    # Notify user
    user_result = await conn.execute(select(User).where(User.id == pr["user_id"]))
    user = user_result.mappings().one()
    name = display_name(user)
    reason_msg = f"Reason: <i>{html.escape(reason)}</i>\n\n" if reason else ""

    title = "Dual Degree Payment Rejected" if pr.get("kind") == "dual_department" else "Payment Rejected"
    await send_telegram_message(
        user["telegram_id"],
        f"❌ <b>{title}</b>\n\n"
        f"Sorry {name}, we could not verify your payment screenshot.\n"
        f"{reason_msg}"
        "Your request has been rejected. If you believe this is a mistake, please try submitting a clearer screenshot or contact support."
    )

    pr_updated_result = await conn.execute(select(PaymentRequest).where(PaymentRequest.id == request_id))
    return (await _with_labels(conn, [pr_updated_result.mappings().one()]))[0]
