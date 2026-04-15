import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker, joinedload

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.postgres import get_engine
from app.models.department import Department
from app.models.course import Course
from app.models.past_exam import PastExam

async def analyze_mixups():
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("--- Analyzing for Potential Mix-ups ---")
        
        # Look for Courses where the course name contains "Nursing" or "Biostatistics" 
        # but the department is NOT Nursing.
        # This is a heuristic.
        
        stmt = (
            select(Course)
            .options(joinedload(Course.department))
        )
        result = await session.execute(stmt)
        courses = result.scalars().all()
        
        mixups_found = []
        for c in courses:
            dept_name = c.department.name.lower()
            course_name = c.name.lower()
            
            # Heuristic: Nursing courses should be in Nursing department
            if "nursing" in course_name and "nursing" not in dept_name:
                mixups_found.append((c.name, c.department.name))
            
            # Heuristic: Accounting courses should be in Accounting department
            if ("accounting" in course_name or "finance" in course_name) and "accounting" not in dept_name:
                mixups_found.append((c.name, c.department.name))

        if not mixups_found:
            print("✅ No obvious mix-ups found based on course names.")
        else:
            print(f"⚠️ Found {len(mixups_found)} potential mix-ups:")
            for course, dept in mixups_found:
                print(f"  - Course: '{course}' is in Department: '{dept}'")
        
        print("\n--- Summary of Exams per Department ---")
        dept_stmt = select(Department).options(joinedload(Department.past_exams))
        dept_result = await session.execute(dept_stmt)
        depts = dept_result.scalars().unique().all()
        
        for d in depts:
            print(f"Department: {d.name} ({len(d.past_exams)} exams)")
            for pe in d.past_exams:
                # Need to load course name for each past exam
                # But for brevity, let's just count
                pass

if __name__ == "__main__":
    asyncio.run(analyze_mixups())
