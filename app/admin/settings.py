from __future__ import annotations

import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.admin.deps import require_superadmin, get_admin_db
from app.models.app_setting import AppSetting

router = APIRouter(prefix="/settings")


class AppSettingCreate(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    is_public: bool = False


class AppSettingUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class AppSettingResponse(BaseModel):
    key: str
    value: Optional[str]
    description: Optional[str]
    is_public: bool


@router.get("", response_model=list[AppSettingResponse], dependencies=[Depends(require_superadmin)])
async def list_settings(
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[AppSettingResponse]:
    """Returns all app settings."""
    result = await conn.execute(select(AppSetting).order_by(AppSetting.key))
    return [AppSettingResponse(**dict(row._mapping)) for row in result]


@router.put("/{key}", response_model=AppSettingResponse, dependencies=[Depends(require_superadmin)])
async def upsert_setting(
    key: str,
    body: AppSettingCreate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> AppSettingResponse:
    """Creates or fully replaces an app setting by key."""
    now = datetime.datetime.utcnow()
    stmt = (
        pg_insert(AppSetting)
        .values(
            key=key,
            value=body.value,
            description=body.description,
            is_public=body.is_public,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["key"],
            set_={
                "value": body.value,
                "description": body.description,
                "is_public": body.is_public,
                "updated_at": now,
            },
        )
        .returning(AppSetting)
    )
    result = await conn.execute(stmt)
    await conn.commit()
    row = result.mappings().one()
    return AppSettingResponse(**dict(row))


@router.patch("/{key}", response_model=AppSettingResponse, dependencies=[Depends(require_superadmin)])
async def patch_setting(
    key: str,
    body: AppSettingUpdate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> AppSettingResponse:
    """Partially updates an app setting."""
    from sqlalchemy import update
    result = await conn.execute(select(AppSetting).where(AppSetting.key == key))
    existing = result.mappings().one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    update_data = body.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.datetime.utcnow()
    await conn.execute(update(AppSetting).where(AppSetting.key == key).values(**update_data))
    await conn.commit()

    result = await conn.execute(select(AppSetting).where(AppSetting.key == key))
    updated = result.mappings().one()
    return AppSettingResponse(**dict(updated))


@router.delete("/{key}", dependencies=[Depends(require_superadmin)])
async def delete_setting(
    key: str,
    conn: AsyncConnection = Depends(get_admin_db),
):
    """Deletes an app setting by key."""
    result = await conn.execute(delete(AppSetting).where(AppSetting.key == key))
    await conn.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {"message": f"Setting '{key}' deleted"}
