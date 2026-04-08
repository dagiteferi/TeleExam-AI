import asyncio
from sqlalchemy import select
from app.db.postgres import get_engine
from app.models.department import Department
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

async def main():
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(select(Department))
        for dept in result.scalars():
            print(f"ID: {dept.id}, Code: {dept.code}, Name: {dept.name}")

asyncio.run(main())
