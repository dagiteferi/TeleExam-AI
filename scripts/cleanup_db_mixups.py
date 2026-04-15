import asyncio
import sys
import os
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker, joinedload

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.postgres import get_engine
from app.models.department import Department
from app.models.course import Course
from app.models.past_exam import PastExam, PastExamQuestion
from app.models.question import Question

async def cleanup_mixups():
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 1. Find the "accounting and finance" department
        res = await session.execute(select(Department).where(Department.name == "accounting and finance"))
        acc_dept = res.scalar_one_or_none()
        if not acc_dept:
            print("Accounting department not found.")
            return

        # 2. Find Nursing courses in Accounting department
        stmt = (
            select(Course)
            .where(Course.department_id == acc_dept.id)
            .where(Course.name.ilike("%nursing%"))
        )
        result = await session.execute(stmt)
        courses_to_remove = result.scalars().all()

        if not courses_to_remove:
            print("No misplaced Nursing courses found in Accounting department.")
            return

        print(f"Found {len(courses_to_remove)} misplaced courses in Accounting:")
        for c in courses_to_remove:
            print(f"  - {c.name}")

        # confirmation = input("\nProceed with deletion? (y/n): ")
        # if confirmation.lower() != 'y':
        #    print("Abort.")
        #    return
        
        # 3. Perform Deletion
        for course in courses_to_remove:
            # 3.1 Delete PastExamQuestions and PastExams for this course
            pe_res = await session.execute(select(PastExam).where(PastExam.course_id == course.id))
            past_exams = pe_res.scalars().all()
            for pe in past_exams:
                await session.execute(delete(PastExamQuestion).where(PastExamQuestion.past_exam_id == pe.id))
                await session.execute(delete(PastExam).where(PastExam.id == pe.id))
            
            # 3.2 Delete Questions belonging to this course
            await session.execute(delete(Question).where(Question.course_id == course.id))
            
            # 3.3 Delete Topics belonging to this course
            from app.models.topic import Topic
            await session.execute(delete(Topic).where(Topic.course_id == course.id))
            
            # 3.4 Finally delete the course
            await session.execute(delete(Course).where(Course.id == course.id))
            
        await session.commit()
        print("Cleanup completed successfully.")

if __name__ == "__main__":
    asyncio.run(cleanup_mixups())
