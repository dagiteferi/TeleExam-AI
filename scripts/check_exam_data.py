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

# Configuration: Set the path to the JSON file or directory to check.
# To check only one file, put the full path here: e.g., "data/exams/2017_yekatit_nursing.json"
# Change this line at the top of scripts/check_exam_data.py
TARGET_PATH = "data/exams/2016_sene_nursing.json"


def validate_question(q_data: Dict[str, Any], course_name: str, q_index: int) -> List[str]:
    errors = []
    
    # 1. Required Top-Level Question Fields
    required_fields = ["question_text", "options", "correct_answer", "topic", "difficulty"]
    for field in required_fields:
        if field not in q_data:
            errors.append(f"Course '{course_name}', Q#{q_index}: Missing required field '{field}'")
        elif field == "question_text" and not str(q_data[field]).strip():
            errors.append(f"Course '{course_name}', Q#{q_index}: Question text is empty")

    # 2. Options Validation
    if "options" in q_data:
        options = q_data["options"]
        if not isinstance(options, dict):
             errors.append(f"Course '{course_name}', Q#{q_index}: 'options' must be a dictionary")
        else:
            # Create a case-insensitive map of options
            norm_options = {str(k).upper(): v for k, v in options.items()}
            for opt in ["A", "B", "C", "D"]:
                if opt not in norm_options:
                    errors.append(f"Course '{course_name}', Q#{q_index}: ❌ Option '{opt}' is COMPLETELY MISSING")
                elif not str(norm_options[opt]).strip():
                    errors.append(f"Course '{course_name}', Q#{q_index}: ⚠️ Option '{opt}' is an empty string")

    # 3. Correct Answer Validation
    if "correct_answer" in q_data:
        answer = str(q_data["correct_answer"]).upper()
        if answer not in ["A", "B", "C", "D"]:
            errors.append(f"Course '{course_name}', Q#{q_index}: Invalid correct_answer '{answer}' (Must be A, B, C, or D)")
        elif "options" in q_data and isinstance(q_data["options"], dict):
            norm_options = {str(k).upper(): v for k, v in q_data["options"].items()}
            if answer not in norm_options:
                errors.append(f"Course '{course_name}', Q#{q_index}: Correct answer '{answer}' points to a missing option")

    # 4. Difficulty Validation
    if "difficulty" in q_data:
        valid_diffs = ["easy", "medium", "hard"]
        if str(q_data["difficulty"]).lower() not in valid_diffs:
            errors.append(f"Course '{course_name}', Q#{q_index}: Invalid difficulty '{q_data['difficulty']}'")

    return errors

def check_file(file_path: Path):
    rel_path = file_path.name
    results = {"file": rel_path, "errors": [], "warnings": [], "dept": "Unknown", "q_count": 0}
    
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        results["errors"].append(f"CRITICAL: Failed to parse JSON: {e}")
        return results

    # Check top-level fields
    for field in ["department", "year", "semester", "courses"]:
        if field not in data:
            results["errors"].append(f"Missing top-level field: '{field}'")
    
    if not results["errors"]:
        results["dept"] = data["department"]
        
        # --- FILENAME CONSISTENCY CHECK (WARNING) ---
        dept_slug = slugify(results["dept"])
        file_name_slug = slugify(file_path.stem)
        if dept_slug != "general" and dept_slug not in file_name_slug:
             results["warnings"].append(f"Internal dept name '{results['dept']}' does not match filename")
        # ----------------------------------

        courses = data["courses"]
        
        hashes = set()
        for i_c, course in enumerate(courses):
            c_name = course.get("course_name", f"Index {i_c}")
            questions = course.get("questions", [])
            
            if not questions:
                results["errors"].append(f"Course '{c_name}' has 0 questions")
                continue
            
            for q_idx, q in enumerate(questions):
                results["q_count"] += 1
                q_errs = validate_question(q, c_name, q_idx)
                results["errors"].extend(q_errs)
                
                # Check for duplicates (WARNING)
                if "question_text" in q and "options" in q:
                    opts = q["options"]
                    if isinstance(opts, dict):
                        h = compute_hash(q["question_text"], [str(opts.get("A","")), str(opts.get("B","")), str(opts.get("C","")), str(opts.get("D",""))])
                        if h in hashes:
                            results["warnings"].append(f"Course '{c_name}', Q#{q_idx}: 🔄 Duplicate question found")
                        hashes.add(h)

    return results

def main():
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        target = Path(TARGET_PATH)

    if not target.exists():
        print(f"Path not found: {target}")
        return

    all_files = list(target.glob("*.json")) if target.is_dir() else ([target] if target.is_file() else [])
    
    if not all_files:
        print(f"No .json files found at {target}")
        return

    file_results = []
    for f in sorted(all_files):
        print(f"Checking {f.name}...")
        file_results.append(check_file(f))

    # Print Summary Table
    print("\n" + "="*120)
    print(f"{'STATUS':<10} | {'FILE NAME':<40} | {'DEPT':<15} | {'Qs':<5} | {'DETAILS'}")
    print("-" * 120)
    
    pass_count = 0
    for res in file_results:
        # Determine status
        if res["errors"]:
            status = "❌ FAIL"
        elif res["warnings"]:
            status = "⚠️ WARN"
            pass_count += 1
        else:
            status = "✅ OK"
            pass_count += 1
        
        detail_msg = f"{len(res['errors'])} errors, {len(res['warnings'])} warnings"
        print(f"{status:<10} | {res['file'][:40]:<40} | {res['dept'][:15]:<15} | {res['q_count']:<5} | {detail_msg}")
        
        # Show specific issues
        if res["errors"]:
            print("      [ERRORS]:")
            for e in res["errors"][:5]:
                print(f"        - {e}")
            if len(res["errors"]) > 5: print(f"        ... and {len(res['errors'])-5} more")
            
        if res["warnings"]:
            print("      [WARNINGS]:")
            for w in res["warnings"][:5]:
                print(f"        - {w}")
            if len(res["warnings"]) > 5: print(f"        ... and {len(res['warnings'])-5} more")

    print("="*120)
    print(f"SUMMARY: {pass_count}/{len(file_results)} files passed (including warnings).")

if __name__ == "__main__":
    main()
