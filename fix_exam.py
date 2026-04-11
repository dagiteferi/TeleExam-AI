import asyncio
import sys
import os

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.postgres import get_engine
from app.models.past_exam import PastExam
from app.models.department import Department

async def fix_exam_year_semester():
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Find the department
        dept_code = "accounting_and_finance"
        result = await session.execute(select(Department).where(Department.code == dept_code))
        department = result.scalar_one_or_none()
        if not department:
            print("Department not found")
            return

        # Update past_exams with year=2018, semester='tir' to year=2017, semester='hamle'
        stmt = (
            update(PastExam)
            .where(
                PastExam.department_id == department.id,
                PastExam.year == 2018,
                PastExam.semester == 'tir'
            )
            .values(year=2017, semester='hamle')
        )
        result = await session.execute(stmt)
        await session.commit()
        print(f"Updated {result.rowcount} past_exam records")

if __name__ == "__main__":
    asyncio.run(fix_exam_year_semester())