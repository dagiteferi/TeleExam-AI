import json
from pathlib import Path
from app.db.supabase import get_supabase
import structlog

logger = structlog.get_logger(__name__)


def import_exams(data_dir: str = "data/exams"):
    supabase = get_supabase()
    path = Path(data_dir)

    if not path.exists():
        logger.error(f"Directory not found: {path}")
        return

    for file in path.glob("*.json"):
        logger.info(f"Importing {file.name}")
        with open(file, encoding="utf-8") as f:
            data = json.load(f)

        # Department
        dept_resp = supabase.table("departments").upsert({"name": data["department"]}).execute()
        dept_id = dept_resp.data[0]["id"]

        for course in data.get("courses", []):
            course_resp = supabase.table("courses").upsert({
                "department_id": dept_id,
                "course_name": course["course_name"]
            }).execute()
            course_id = course_resp.data[0]["id"]

            for q in course.get("questions", []):
                # Topic
                topic_resp = supabase.table("topics").upsert({
                    "course_id": course_id,
                    "topic_name": q.get("topic", "General")
                }).execute()
                topic_id = topic_resp.data[0]["id"]

                # Question
                q_payload = {
                    "question_text": q["question_text"],
                    "options": q["options"],
                    "correct_answer": q["correct_answer"],
                    "explanation": q.get("explanation"),
                    "difficulty": q.get("difficulty", "Medium"),
                    "topic_id": topic_id
                }
                q_resp = supabase.table("questions").insert(q_payload).execute()
                question_id = q_resp.data[0]["id"]

                # Exam + link
                exam_resp = supabase.table("exams").upsert({
                    "year": data["year"],
                    "semester": data["semester"],
                    "course_id": course_id
                }).execute()
                exam_id = exam_resp.data[0]["id"]

                supabase.table("exam_questions").upsert({
                    "exam_id": exam_id,
                    "question_id": question_id
                }).execute()

        logger.info(f"Completed {file.name}")

    logger.info("All exams imported successfully!")


if __name__ == "__main__":
    import_exams()