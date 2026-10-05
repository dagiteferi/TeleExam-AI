from __future__ import annotations
import uuid as _uuid
import datetime
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.deps import telegram_id_header, get_db_conn
from app.models.bank_account import BankAccount
from app.models.payment_request import PaymentRequest
from app.models.user import User
from app.schemas.payment import BankAccountResponse, PaymentRequestResponse
from app.db.supabase import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments")


@router.get("/banks", response_model=list[BankAccountResponse])
async def get_active_banks(
    conn: AsyncConnection = Depends(get_db_conn),
    telegram_id: str = Depends(telegram_id_header),
) -> list[BankAccountResponse]:
    """Returns a list of all active bank accounts for the user to make a payment to."""
    query = select(BankAccount).where(BankAccount.is_active == True)
    result = await conn.execute(query)
    banks = result.mappings().all()
    return [BankAccountResponse(**b) for b in banks]


@router.post("/submit", response_model=PaymentRequestResponse)
async def submit_payment_request(
    file: UploadFile = File(...),
    conn: AsyncConnection = Depends(get_db_conn),
    telegram_id: str = Depends(telegram_id_header),
) -> PaymentRequestResponse:
    """Accepts a payment screenshot from the user and creates a pending Payment Request."""

    # Cast telegram_id to int (it arrives as a string from the header)
    try:
        tg_id = int(telegram_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid Telegram ID")

    # 1. Verify user
    user_result = await conn.execute(select(User).where(User.telegram_id == tg_id))
    user = user_result.mappings().one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user["is_pro"]:
        raise HTTPException(status_code=400, detail="User is already PRO")

    # 2. Upload to Supabase Storage
    try:
        supabase = get_supabase()

        file_bytes = await file.read()
        file_ext = file.filename.split('.')[-1] if file.filename else "jpg"
        file_name = f"{user['id']}_{_uuid.uuid4()}.{file_ext}"

        supabase.storage.from_("payment-receipts").upload(
            path=file_name,
            file=file_bytes,
            file_options={"content-type": file.content_type or "image/jpeg"}
        )

        # Get public URL
        public_url = supabase.storage.from_("payment-receipts").get_public_url(file_name)
    except Exception as e:
        logger.error(f"Failed to upload screenshot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload screenshot to storage: {str(e)}")

    # 3. Create PaymentRequest using core INSERT
    new_id = _uuid.uuid4()
    now = datetime.datetime.utcnow()
    stmt = (
        pg_insert(PaymentRequest)
        .values(
            id=new_id,
            user_id=user["id"],
            screenshot_url=public_url,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        .returning(PaymentRequest)
    )
    result = await conn.execute(stmt)
    await conn.commit()
    row = result.mappings().one()
    return PaymentRequestResponse(**row)
