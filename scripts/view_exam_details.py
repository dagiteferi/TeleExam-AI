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

async def get_departments(session: AsyncSession):
    stmt = select(Department).order_by(Department.name)
    result = await session.execute(stmt)
    return result.scalars().all()

async def list_exams(department_id: str = None):
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        stmt = (
            select(PastExam)
            .options(
                joinedload(PastExam.department),
                joinedload(PastExam.course)
            )
        )
        
        if department_id:
            stmt = stmt.where(PastExam.department_id == department_id)
            
        stmt = stmt.order_by(PastExam.year.desc(), PastExam.semester)
        result = await session.execute(stmt)
        exams = result.scalars().all()
        
        if not exams:
            print("\nNo exams found for the selected criteria.")
            return []

        print(f"\n{'#' :<3} | {'Year':<6} | {'Sem':<10} | {'Dept':<15} | {'Course':<30} | {'Questions':<5}")
        print("-" * 90)
        
        for idx, exam in enumerate(exams, 1):
            count_stmt = select(func.count(PastExamQuestion.question_id)).where(PastExamQuestion.past_exam_id == exam.id)
            count_res = await session.execute(count_stmt)
            q_count = count_res.scalar()
            
            dept_name = exam.department.name if exam.department else "N/A"
            course_name = exam.course.name if exam.course else "N/A"
            
            print(f"{idx:<3} | {exam.year:<6} | {exam.semester[:10]:<10} | {dept_name[:15]:<15} | {course_name[:30]:<30} | {q_count:<5}")
        
        return exams

async def view_specific_exam(exam: PastExam):
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Load questions for this exam
        q_stmt = (
            select(Question)
            .options(joinedload(Question.topic))
            .join(PastExamQuestion, PastExamQuestion.question_id == Question.id)
            .where(PastExamQuestion.past_exam_id == exam.id)
        )
        q_result = await session.execute(q_stmt)
        questions = q_result.scalars().all()

        while True:
            print(f"\n{'='*20} Exam: {exam.course.name} ({exam.year}) {'='*20}")
            print(f"ID:         {exam.id}")
            print(f"Department: {exam.department.name}")
            print(f"Semester:   {exam.semester}")
            print(f"Total Qs:   {len(questions)}")
            print("-" * 60)
            print("1. View Topic Distribution")
            print("2. List All Questions (Text + Answer)")
            print("b. Back to Exam List")
            
            sub_choice = input("\nSelect detail option: ").strip().lower()
            
            if sub_choice == 'b':
                break
            elif sub_choice == '1':
                topics = {}
                for q in questions:
                    t_name = q.topic.name if q.topic else "General"
                    topics[t_name] = topics.get(t_name, 0) + 1
                    
                print("\n--- Topic Distribution ---")
                for t_name, count in sorted(topics.items()):
                    print(f"- {t_name:<40}: {count}")
                input("\nPress Enter to continue...")
            elif sub_choice == '2':
                print("\n--- Questions ---")
                for i, q in enumerate(questions, 1):
                    # Truncate question text for brevity
                    prompt_short = (q.prompt[:75] + '...') if len(q.prompt) > 75 else q.prompt
                    print(f"{i:<3}. [{q.correct_choice}] {prompt_short}")
                input("\nPress Enter to continue...")
            else:
                print("Invalid option.")

async def interactive_main():
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    while True:
        print("\n=== TeleExam DB Browser ===")
        print("1. View All Exams")
        print("2. Filter by Department")
        print("q. Quit")
        
        choice = input("\nSelect an option: ").strip().lower()
        
        if choice == 'q':
            break
            
        selected_dept_id = None
        if choice == '2':
            async with async_session() as session:
                depts = await get_departments(session)
                if not depts:
                    print("No departments found.")
                    continue
                
                print("\n--- Departments ---")
                for i, d in enumerate(depts, 1):
                    print(f"{i}. {d.name}")
                
                dept_choice = input("\nSelect department (or 'b' to go back): ").strip()
                if dept_choice.lower() == 'b':
                    continue
                try:
                    selected_dept_id = depts[int(dept_choice)-1].id
                except (ValueError, IndexError):
                    print("Invalid selection.")
                    continue
        elif choice != '1':
            print("Invalid option.")
            continue

        # List exams and allow selecting one for details
        exams = await list_exams(selected_dept_id)
        if exams:
            detail_choice = input("\nEnter Row # to see details (or Enter to skip): ").strip()
            if detail_choice:
                try:
                    idx = int(detail_choice) - 1
                    if 0 <= idx < len(exams):
                        await view_specific_exam(exams[idx])
                    else:
                        print("Invalid row number.")
                except ValueError:
                    print("Invalid input.")

def main():
    try:
        asyncio.run(interactive_main())
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
