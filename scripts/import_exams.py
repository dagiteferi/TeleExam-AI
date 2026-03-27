import asyncio
import json
import hashlib
from pathlib import Path
import structlog
import sys
import os

# Add project root to python path so scripts can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.postgres import get_engine
from app.models.department import Department
from app.models.course import Course
from app.models.topic import Topic
from app.models.question import Question, QuestionFormat
from app.models.past_exam import PastExam, PastExamQuestion

logger = structlog.get_logger(__name__)

def slugify(text: str) -> str:
    """Generate a simple slug for codes."""
    return str(text).lower().strip().replace(" ", "_").replace("-", "_")

def get_difficulty(diff_str: str) -> int:
    """Map string difficulty to integer scale (1-5)."""
    d = str(diff_str).lower().strip()
    if d == 'easy': return 1
    elif d == 'medium': return 3
    elif d == 'hard': return 5
    return 3

def compute_hash(prompt: str, choices: list[str]) -> bytes:
    """Compute a unique hash based on question prompt and choices."""
    text = prompt + "".join(choices)
    return hashlib.sha256(text.encode('utf-8')).digest()

async def import_exams_async(data_dir: str = "data/exams"):
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    path = Path(data_dir)
    if not path.exists():
        logger.error(f"Directory not found: {path}")
        return

    logger.info("Starting scalable exam ingestion process...")

    async with async_session() as session:
        for file in path.glob("*.json"):
            logger.info(f"Importing {file.name}")
            with open(file, encoding="utf-8") as f:
                data = json.load(f)

            dept_name = data.get("department", "general")
            dept_code = slugify(dept_name)
            
            # 1. Upsert Department
            result = await session.execute(select(Department).where(Department.code == dept_code))
            department = result.scalar_one_or_none()
            if not department:
                department = Department(code=dept_code, name=dept_name)
                session.add(department)
                await session.commit()
                await session.refresh(department)
            else:
                department.name = dept_name
                await session.commit()

            year = int(data.get("year", 2015))
            semester = str(data.get("semester", "1"))

            for course_data in data.get("courses", []):
                course_name = course_data["course_name"]
                course_code = slugify(course_name)
                
                # 2. Upsert Course
                result = await session.execute(
                    select(Course).where(Course.department_id == department.id, Course.code == course_code)
                )
                course = result.scalar_one_or_none()
                if not course:
                    course = Course(department_id=department.id, code=course_code, name=course_name)
                    session.add(course)
                    await session.commit()
                    await session.refresh(course)
                else:
                    course.name = course_name
                    await session.commit()

                # 3. Upsert Past Exam
                result = await session.execute(
                    select(PastExam).where(
                        PastExam.department_id == department.id,
                        PastExam.course_id == course.id,
                        PastExam.year == year,
                        PastExam.semester == semester
                    )
                )
                past_exam = result.scalar_one_or_none()
                if not past_exam:
                    past_exam = PastExam(
                        department_id=department.id,
                        course_id=course.id,
                        year=year,
                        semester=semester
                    )
                    session.add(past_exam)
                    await session.commit()
                    await session.refresh(past_exam)


                # 4. Iterate and Upsert Questions & Topics
                for q_data in course_data.get("questions", []):
                    topic_name = q_data.get("topic", "General")
                    topic_code = slugify(topic_name)
                    
                    # Upsert Topic
                    result = await session.execute(
                        select(Topic).where(Topic.course_id == course.id, Topic.code == topic_code)
                    )
                    topic = result.scalar_one_or_none()
                    if not topic:
                        topic = Topic(course_id=course.id, code=topic_code, name=topic_name)
                        session.add(topic)
                        await session.commit()
                        await session.refresh(topic)

                    prompt = q_data["question_text"]
                    options = q_data.get("options", {})
                    choice_a = options.get("A", "")
                    choice_b = options.get("B", "")
                    choice_c = options.get("C", "")
                    choice_d = options.get("D", "")
                    correct_choice = q_data.get("correct_answer", "A")
                    explanation = q_data.get("explanation", "")
                    difficulty = get_difficulty(q_data.get("difficulty", "Medium"))
                    
                    content_hash = compute_hash(prompt, [choice_a, choice_b, choice_c, choice_d])

                    # Upsert Question
                    result = await session.execute(
                        select(Question).where(Question.content_hash == content_hash)
                    )
                    question = result.scalar_one_or_none()
                    
                    if not question:
                        question = Question(
                            course_id=course.id,
                            topic_id=topic.id,
                            format=QuestionFormat.mcq,
                            prompt=prompt,
                            choice_a=choice_a,
                            choice_b=choice_b,
                            choice_c=choice_c,
                            choice_d=choice_d,
                            correct_choice=correct_choice,
                            difficulty=difficulty,
                            explanation_static=explanation,
                            content_hash=content_hash
                        )
                        session.add(question)
                        await session.commit()
                        await session.refresh(question)
                    else:
                        # Update existing question with potentially new mappings
                        question.prompt = prompt
                        question.choice_a = choice_a
                        question.choice_b = choice_b
                        question.choice_c = choice_c
                        question.choice_d = choice_d
                        question.correct_choice = correct_choice
                        question.difficulty = difficulty
                        question.explanation_static = explanation
                        question.course_id = course.id
                        question.topic_id = topic.id
                        await session.commit()

                    # 5. Link Question to Past Exam (ignoring uniqueness conflicts by checking first)
                    result = await session.execute(
                        select(PastExamQuestion).where(
                            PastExamQuestion.past_exam_id == past_exam.id,
                            PastExamQuestion.question_id == question.id
                        )
                    )
                    peq = result.scalar_one_or_none()
                    if not peq:
                        peq = PastExamQuestion(past_exam_id=past_exam.id, question_id=question.id)
                        session.add(peq)
                
                # Commit all links for the course
                await session.commit()
                
            logger.info(f"Completed processing of {file.name}")

    logger.info("All exams imported successfully!")

def main():
    asyncio.run(import_exams_async())

if __name__ == "__main__":
    main()