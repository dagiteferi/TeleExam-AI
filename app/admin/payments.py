from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, update

from app.admin.deps import require_superadmin, get_admin_db
from app.db.postgres import db_conn
from app.models.bank_account import BankAccount
from app.models.payment_request import PaymentRequest
from app.models.user import User
from app.schemas.payment import BankAccountCreate, BankAccountUpdate, BankAccountResponse, PaymentRequestResponse
from app.core.notify import send_telegram_message

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
    return [PaymentRequestResponse(**r) for r in requests]


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

    now = datetime.datetime.utcnow()

    # 2. Update request status (no admin_id — superadmin has no DB row)
    await conn.execute(
        update(PaymentRequest)
        .where(PaymentRequest.id == request_id)
        .values(status="approved", updated_at=now)
    )

    # 3. Upgrade user to PRO
    user_id = pr["user_id"]
    await conn.execute(update(User).where(User.id == user_id).values(is_pro=True, updated_at=now))

    await conn.commit()

    # 4. Notify user
    user_result = await conn.execute(select(User).where(User.id == user_id))
    user = user_result.mappings().one()
    name = user.get("first_name") or user.get("telegram_username") or "there"

    await send_telegram_message(
        user["telegram_id"],
        f"✅ <b>Payment Approved!</b>\n\n"
        f"Congratulations {name}, your payment screenshot was verified.\n"
        "Your account has been upgraded to <b>PRO</b>!\n\n"
        "You now have unlimited access to the AI Tutor and all exams. Happy studying! 🎉"
    )

    pr_updated_result = await conn.execute(select(PaymentRequest).where(PaymentRequest.id == request_id))
    pr_updated = pr_updated_result.mappings().one()
    return PaymentRequestResponse(**pr_updated)


@router.post("/requests/{request_id}/reject", response_model=PaymentRequestResponse)
async def reject_payment_request(
    request_id: UUID,
    admin: dict = Depends(require_superadmin),
    conn: AsyncConnection = Depends(get_admin_db),
) -> PaymentRequestResponse:
    import datetime
    result = await conn.execute(select(PaymentRequest).where(PaymentRequest.id == request_id))
    pr = result.mappings().one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Payment request not found")

    if pr["status"] == "rejected":
        raise HTTPException(status_code=400, detail="Already rejected")

    now = datetime.datetime.utcnow()
    await conn.execute(
        update(PaymentRequest)
        .where(PaymentRequest.id == request_id)
        .values(status="rejected", updated_at=now)
    )
    await conn.commit()

    # Notify user
    user_result = await conn.execute(select(User).where(User.id == pr["user_id"]))
    user = user_result.mappings().one()
    name = user.get("first_name") or user.get("telegram_username") or "there"

    await send_telegram_message(
        user["telegram_id"],
        f"❌ <b>Payment Rejected</b>\n\n"
        f"Sorry {name}, we could not verify your payment screenshot.\n"
        "Your request has been rejected. If you believe this is a mistake, please try submitting a clearer screenshot or contact support."
    )

    pr_updated_result = await conn.execute(select(PaymentRequest).where(PaymentRequest.id == request_id))
    pr_updated = pr_updated_result.mappings().one()
    return PaymentRequestResponse(**pr_updated)
