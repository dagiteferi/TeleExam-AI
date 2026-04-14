import json
import hashlib
import sys
import os
from pathlib import Path
import structlog
from typing import List, Dict, Any

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logger = structlog.get_logger(__name__)

def slugify(text: str) -> str:
    """Generate aclear simple slug for codes."""
    return str(text).lower().strip().replace(" ", "_").replace("-", "_")

def compute_hash(prompt: str, choices: list[str]) -> bytes:
    """Compute a unique hash based on question prompt and choices."""
    text = prompt + "".join(choices)
    return hashlib.sha256(text.encode('utf-8')).digest()

def validate_question(q_data: Dict[str, Any], course_index: int, q_index: int) -> List[str]:
    errors = []
    required_fields = ["question_text", "options", "correct_answer", "topic", "difficulty"]
    
    for field in required_fields:
        if field not in q_data:
            errors.append(f"Course {course_index}, Question {q_index}: Missing field '{field}'")
    
    if "options" in q_data:
        options = q_data["options"]
        for opt in ["A", "B", "C", "D"]:
            if opt not in options:
                errors.append(f"Course {course_index}, Question {q_index}: Missing option '{opt}'")
            elif not str(options[opt]).strip():
                errors.append(f"Course {course_index}, Question {q_index}: Option '{opt}' is empty")

    if "correct_answer" in q_data:
        if q_data["correct_answer"] not in ["A", "B", "C", "D"]:
            errors.append(f"Course {course_index}, Question {q_index}: Invalid correct_answer '{q_data['correct_answer']}'. Must be A, B, C, or D.")

    if "difficulty" in q_data:
        valid_diffs = ["easy", "medium", "hard"]
        if str(q_data["difficulty"]).lower() not in valid_diffs:
            errors.append(f"Course {course_index}, Question {q_index}: Invalid difficulty '{q_data['difficulty']}'. Must be Easy, Medium, or Hard.")

    return errors

def check_file(file_path: Path):
    print(f"\n{'='*20} Checking: {file_path.name} {'='*20}")
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse JSON in {file_path.name}: {e}")
        return False

    errors = []
    
    # Check top-level fields
    for field in ["department", "year", "semester", "courses"]:
        if field not in data:
            errors.append(f"Missing top-level field: '{field}'")
    
    if not errors:
        dept = data["department"]
        year = data["year"]
        semester = data["semester"]
        courses = data["courses"]
        
        print(f"Targeting Dept: {dept}, Year: {year}, Sem: {semester}")
        
        if not isinstance(courses, list) or not courses:
            errors.append("Field 'courses' must be a non-empty list")
        else:
            hashes = set()
            for c_idx, course in enumerate(courses):
                if "course_name" not in course:
                    errors.append(f"Course at index {c_idx} missing 'course_name'")
                if "questions" not in course or not isinstance(course["questions"], list) or not course["questions"]:
                    errors.append(f"Course {course.get('course_name', c_idx)} missing questions")
                    continue
                
                for q_idx, q in enumerate(course["questions"]):
                    q_errs = validate_question(q, c_idx, q_idx)
                    errors.extend(q_errs)
                    
                    # Check for duplicates within this file
                    if "question_text" in q and "options" in q:
                        opts = q["options"]
                        h = compute_hash(q["question_text"], [opts.get("A",""), opts.get("B",""), opts.get("C",""), opts.get("D","")])
                        if h in hashes:
                            errors.append(f"Duplicate question found in file: Course {c_idx}, Question {q_idx}")
                        hashes.add(h)

    if errors:
        print(f"❌ Found {len(errors)} errors:")
        for err in errors[:20]: # Show first 20 errors
            print(f"  - {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors.")
        return False
    else:
        print("✅ No errors found in file formatting or data structure.")
        return True

def main():
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        target = Path("data/exams")

    if not target.exists():
        logger.error(f"Path not found: {target}")
        sys.exit(1)

    all_files = []
    if target.is_file():
        all_files.append(target)
    else:
        all_files = list(target.glob("*.json"))

    success_count = 0
    for f in all_files:
        if check_file(f):
            success_count += 1
    
    print(f"\nSummary: {success_count}/{len(all_files)} files passed validation.")

if __name__ == "__main__":
    main()
