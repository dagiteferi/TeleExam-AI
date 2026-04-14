import asyncio
import sys
import os
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker, joinedload

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.postgres import get_engine
from app.models.department import Department
from app.models.course import Course
from app.models.past_exam import PastExam, PastExamQuestion
from app.models.question import Question

async def get_exam_details():
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get all past exams with their associations
        stmt = (
            select(PastExam)
            .options(
                joinedload(PastExam.department),
                joinedload(PastExam.course)
            )
            .order_by(PastExam.year.desc(), PastExam.semester)
        )
        result = await session.execute(stmt)
        exams = result.scalars().all()
        
        if not exams:
            print("No exams found in the database.")
            return

        print(f"{'ID':<38} | {'Dept':<15} | {'Year':<6} | {'Sem':<10} | {'Course':<30} | {'Questions':<5}")
        print("-" * 115)
        
        for exam in exams:
            # Count questions for this exam
            count_stmt = select(func.count(PastExamQuestion.question_id)).where(PastExamQuestion.past_exam_id == exam.id)
            count_res = await session.execute(count_stmt)
            q_count = count_res.scalar()
            
            dept_name = exam.department.name if exam.department else "N/A"
            course_name = exam.course.name if exam.course else "N/A"
            
            print(f"{str(exam.id):<38} | {dept_name[:15]:<15} | {exam.year:<6} | {exam.semester[:10]:<10} | {course_name[:30]:<30} | {q_count:<5}")

async def view_specific_exam(exam_id_str: str):
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        import uuid
        try:
            exam_id = uuid.UUID(exam_id_str)
        except ValueError:
            print(f"Invalid UUID: {exam_id_str}")
            return

        stmt = (
            select(PastExam)
            .options(
                joinedload(PastExam.department),
                joinedload(PastExam.course)
            )
            .where(PastExam.id == exam_id)
        )
        result = await session.execute(stmt)
        exam = result.scalar_one_or_none()
        
        if not exam:
            print(f"Exam with ID {exam_id_str} not found.")
            return

        print(f"\n--- Exam Details ---")
        print(f"ID:         {exam.id}")
        print(f"Department: {exam.department.name}")
        print(f"Course:     {exam.course.name}")
        print(f"Year:       {exam.year}")
        print(f"Semester:   {exam.semester}")
        
        # Get topic distribution
        topic_stmt = (
            select(Question.topic_id, Question.course_id, func.count(Question.id))
            .join(PastExamQuestion, PastExamQuestion.question_id == Question.id)
            .where(PastExamQuestion.past_exam_id == exam.id)
            .group_by(Question.topic_id, Question.course_id)
        )
        # This is a bit complex due to Topic association, let's just get questions and their topics
        q_stmt = (
            select(Question)
            .options(joinedload(Question.topic))
            .join(PastExamQuestion, PastExamQuestion.question_id == Question.id)
            .where(PastExamQuestion.past_exam_id == exam.id)
        )
        q_result = await session.execute(q_stmt)
        questions = q_result.scalars().all()
        
        print(f"Total Qs:   {len(questions)}")
        
        topics = {}
        for q in questions:
            t_name = q.topic.name if q.topic else "General"
            topics[t_name] = topics.get(t_name, 0) + 1
            
        print("\n--- Topic Distribution ---")
        for t_name, count in topics.items():
            print(f"- {t_name:<40}: {count}")

def main():
    if len(sys.argv) > 1:
        asyncio.run(view_specific_exam(sys.argv[1]))
    else:
        asyncio.run(get_exam_details())

if __name__ == "__main__":
    main()
