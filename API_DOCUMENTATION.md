# TeleExam AI API Documentation

This document provides a detailed overview of the TeleExam AI backend API endpoints for frontend integration.

---

## Authentication

All endpoints under `/api` (except those explicitly public) require authentication via Telegram Bot Headers.

-   **X-Telegram-Secret**: A secret key shared between the Telegram Bot and the backend.
-   **X-Telegram-Id**: The Telegram user's ID.

Public endpoints under `/api/public` do not require these headers.

---

## API Endpoints

### 1. AI Endpoints (`app/api/ai.py`)

These endpoints provide AI-powered functionalities like question explanations, chat interactions, and study plan generation.

#### 1.1. Explain Question

-   **Method**: `POST`
-   **Path**: `/api/ai/explain`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/ai.py`

-   **Description**: Provides an AI-generated explanation for a given question and user answer.

-   **Parameters**:
    -   **Body**: `ExplainRequest`
        -   `question_id` (string, UUID): The ID of the question to explain.
        -   `user_answer` (string, optional): The user's answer to the question.

-   **Request Example**:

    ```json
    {
        "question_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "user_answer": "A"
    }
    ```

-   **Response Model**: `ExplainResponse`
    -   `success` (boolean): Always `true`.
    -   `explanation` (string): The AI-generated explanation for the question.
    -   `key_points` (array of strings): Key points from the explanation.
    -   `weak_topic_suggestion` (string, optional): Suggestion for a weak topic if identified.

-   **Response Example**:

    ```json
    {
        "success": true,
        "explanation": "The correct answer is A because...",
        "key_points": ["Key point 1", "Key point 2"],
        "weak_topic_suggestion": "Review Data Structures"
    }
    ```

#### 1.2. Chat Interaction

-   **Method**: `POST`
-   **Path**: `/api/ai/chat`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/ai.py`

-   **Description**: Allows for chat-based interaction with the AI, potentially in the context of a specific question.

-   **Parameters**:
    -   **Body**: `ChatRequest`
        -   `message` (string): The user's chat message.
        -   `question_id` (string, UUID): The ID of the question related to the chat (if any).

-   **Request Example**:

    ```json
    {
        "message": "Can you elaborate on this concept?",
        "question_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
    }
    ```

-   **Response Model**: `ChatResponse`
    -   `success` (boolean): Always `true`.
    -   `ai_response` (string): The AI's response to the chat message.

-   **Response Example**:

    ```json
    {
        "success": true,
        "ai_response": "Certainly, let me explain further..."
    }
    ```

#### 1.3. Create Study Plan

-   **Method**: `POST`
-   **Path**: `/api/ai/study-plan`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/ai.py`

-   **Description**: Generates a personalized study plan for the user based on their performance.

-   **Parameters**:
    -   **Body**: `StudyPlanRequest` (empty for now, but can be extended)

-   **Request Example**:

    ```json
    {}
    ```

-   **Response Model**: `StudyPlanResponse`
    -   `success` (boolean): `true` if the study plan was generated successfully.
    -   `study_plan` (object, optional): Details of the generated study plan.
        -   `summary` (string): A summary of the user's performance.
        -   `total_exams_done` (integer): Total number of exams completed.
        -   `overall_score_percent` (float): Overall score percentage.
        -   `weak_topics` (array of objects): List of weak topics.
            -   `topic` (string): Topic name.
            -   `errors` (integer): Number of errors in this topic.
            -   `focus` (string): Priority level for this topic (e.g., "High Priority").
        -   `daily_plan` (array of objects): Daily breakdown of study activities.
            -   `day` (integer): Day number.
            -   `topic` (string): Topic for the day.
            -   `action` (string): Suggested action (e.g., "Read + Practice").
    -   `message` (string, optional): User-facing notes or error messages.

-   **Response Example**:

    ```json
    {
        "success": true,
        "study_plan": {
            "summary": "You scored 62% overall. Weak in Databases, OS.",
            "total_exams_done": 5,
            "overall_score_percent": 62.5,
            "weak_topics": [
                {
                    "topic": "Databases",
                    "errors": 10,
                    "focus": "High Priority"
                }
            ],
            "daily_plan": [
                {
                    "day": 1,
                    "topic": "Databases",
                    "action": "Read + Practice"
                }
            ]
        },
        "message": "Study plan generated successfully."
    }
    ```

### 2. Public Endpoints (`app/api/public.py`)

These endpoints are publicly accessible and do not require any authentication headers.

#### 2.1. Get Discovery Metadata

-   **Method**: `GET`
-   **Path**: `/api/public/discovery-metadata`
-   **Permissions**: Public
-   **User Types**: Any
-   **Position in Code**: `app/api/public.py`

-   **Description**: Provides metadata for frontend selection menus, including departments, past exam details, and available courses.

-   **Parameters**: None

-   **Request Example**:

    ```
    GET /api/public/discovery-metadata
    ```

-   **Response Model**: `dict`
    -   `departments` (array of objects): List of active departments.
        -   `id` (string, UUID): Department ID.
        -   `name` (string): Department name.
    -   `exams` (array of objects): Distinct past exam metadata.
        -   `department_id` (string, UUID): Department ID.
        -   `year` (integer): Exam year.
        -   `semester` (string): Exam semester.
    -   `courses` (array of strings): List of active course names.
    -   `info` (string): Informational message.

-   **Response Example**:

    ```json
    {
        "departments": [
            {
                "id": "d1e2f3g4-h5i6-7890-1234-567890abcdef",
                "name": "Computer Science"
            }
        ],
        "exams": [
            {
                "department_id": "d1e2f3g4-h5i6-7890-1234-567890abcdef",
                "year": 2023,
                "semester": "Fall"
            }
        ],
        "courses": ["Data Structures", "Algorithms"],
        "info": "Selection metadata for TeleExam AI discovery"
    }
    ```

### 3. Questions Endpoints (`app/api/questions.py`)

These endpoints are for discovering and retrieving questions.

#### 3.1. Get Questions by Exam

-   **Method**: `GET`
-   **Path**: `/api/questions/by-exam`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/questions.py`

-   **Description**: Retrieves questions filtered by department, year, and semester.

-   **Parameters**:
    -   **Query**:
        -   `department_id` (string, UUID, required): The ID of the department.
        -   `year` (integer, optional): The year of the exam.
        -   `semester` (string, optional): The semester of the exam.
        -   `mode` (string, optional): "exam" or "practice" (default: "practice").

-   **Request Example**:

    ```
    GET /api/questions/by-exam?department_id=d1e2f3g4-h5i6-7890-1234-567890abcdef&year=2023&semester=Fall&mode=practice
    ```

-   **Response Model**: `DiscoveryResponse`
    -   `questions` (array of `QuestionItem` objects): List of questions.
        -   `id` (string, UUID): Question ID.
        -   `prompt` (string): The question prompt.
        -   `choice_a`, `choice_b`, `choice_c`, `choice_d` (string): Answer choices.
        -   `correct_choice` (string, optional): The correct answer choice (only in practice/quiz mode).
        -   `explanation` (string, optional): Explanation for the correct answer (only in practice/quiz mode).
        -   `year` (integer): Year of the question.
        -   `course_id` (string, UUID): Course ID.
        -   `course_name` (string): Course name.
        -   `topic_name` (string): Topic name.
    -   `total_count` (integer): Total number of questions found.

-   **Response Example**:

    ```json
    {
        "questions": [
            {
                "id": "q1w2e3r4-t5y6-7890-1234-567890abcdef",
                "prompt": "What is 2+2?",
                "choice_a": "3",
                "choice_b": "4",
                "choice_c": "5",
                "choice_d": "6",
                "correct_choice": "B",
                "explanation": "2+2 equals 4.",
                "year": 2023,
                "course_id": "c1v2b3n4-m5l6-7890-1234-567890abcdef",
                "course_name": "Mathematics",
                "topic_name": "Arithmetic"
            }
        ],
        "total_count": 1
    }
    ```

#### 3.2. Get Questions by Course

-   **Method**: `GET`
-   **Path**: `/api/questions/by-course`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/questions.py`

-   **Description**: Retrieves questions for a specific course across all available years.

-   **Parameters**:
    -   **Query**:
        -   `course_name` (string, required): The name of the course.
        -   `mode` (string, optional): "exam" or "practice" (default: "practice").

-   **Request Example**:

    ```
    GET /api/questions/by-course?course_name=Mathematics&mode=practice
    ```

-   **Response Model**: `DiscoveryResponse` (Same as Get Questions by Exam)

-   **Response Example**: (Same as Get Questions by Exam)

#### 3.3. Get Available Courses

-   **Method**: `GET`
-   **Path**: `/api/questions/discovery/courses`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/questions.py`

-   **Description**: Retrieves unique course names available across all exams.

-   **Parameters**: None

-   **Request Example**:

    ```
    GET /api/questions/discovery/courses
    ```

-   **Response Model**: `list[dict]`
    -   Each dictionary contains:
        -   `id` (string, UUID): Course ID.
        -   `name` (string): Course name.

-   **Response Example**:

    ```json
    [
        {
            "id": "c1v2b3n4-m5l6-7890-1234-567890abcdef",
            "name": "Mathematics"
        },
        {
            "id": "x1y2z3a4-b5c6-7890-1234-567890abcdef",
            "name": "Physics"
        }
    ]
    ```

#### 3.4. Get Available Departments

-   **Method**: `GET`
-   **Path**: `/api/questions/discovery/departments`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/questions.py`

-   **Description**: Retrieves all available departments.

-   **Parameters**: None

-   **Request Example**:

    ```
    GET /api/questions/discovery/departments
    ```

-   **Response Model**: `list[dict]`
    -   Each dictionary contains:
        -   `id` (string, UUID): Department ID.
        -   `name` (string): Department name.

-   **Response Example**:

    ```json
    [
        {
            "id": "d1e2f3g4-h5i6-7890-1234-567890abcdef",
            "name": "Computer Science"
        },
        {
            "id": "p1o2i3u4-y5t6-7890-1234-567890abcdef",
            "name": "Electrical Engineering"
        }
    ]
    ```

#### 3.5. Get Exams by Department

-   **Method**: `GET`
-   **Path**: `/api/questions/discovery/department/{department_id}/exams`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/questions.py`

-   **Description**: Retrieves all available years and semesters for a specific department.

-   **Parameters**:
    -   **Path**:
        -   `department_id` (string, UUID, required): The ID of the department.

-   **Request Example**:

    ```
    GET /api/questions/discovery/department/d1e2f3g4-h5i6-7890-1234-567890abcdef/exams
    ```

-   **Response Model**: `list[dict]`
    -   Each dictionary contains:
        -   `year` (integer): Exam year.
        -   `semester` (string): Exam semester.

-   **Response Example**:

    ```json
    [
        {
            "year": 2023,
            "semester": "Fall"
        },
        {
            "year": 2022,
            "semester": "Spring"
        }
    ]
    ```

### 4. Render Endpoints (`app/api/render.py`)

These endpoints are for rendering question content as images.

#### 4.1. Render Question Image

-   **Method**: `GET`
-   **Path**: `/v1/render/{question_id}.png`
-   **Permissions**: Public
-   **User Types**: Any
-   **Position in Code**: `app/api/render.py`

-   **Description**: Returns the question prompt content as a PNG image to prevent text copying.

-   **Parameters**:
    -   **Path**:
        -   `question_id` (string, UUID, required): The ID of the question to render.

-   **Request Example**:

    ```
    GET /v1/render/q1w2e3r4-t5y6-7890-1234-567890abcdef.png
    ```

-   **Response Model**: `image/png` (binary data)

-   **Response Example**: (Binary image data)

### 5. Results Endpoints (`app/api/results.py`)

These endpoints are for retrieving user results and session-specific results.

#### 5.1. Get Overall Results

-   **Method**: `GET`
-   **Path**: `/api/results/{telegram_id}`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/results.py`

-   **Description**: Retrieves the overall results for a specific Telegram user.

-   **Parameters**:
    -   **Path**:
        -   `telegram_id` (integer, required): The Telegram ID of the user.

-   **Request Example**:

    ```
    GET /api/results/123456789
    ```

-   **Response Model**: `OverallResultsResponse` (details not fully available in provided schemas, assuming a structure for overall performance)
    -   `total_sessions` (integer): Total number of sessions completed.
    -   `average_score` (float): Average score across all sessions.
    -   `topics_mastered` (integer): Number of topics mastered.
    -   `weak_topics` (array of strings): List of weak topics.

-   **Response Example**:

    ```json
    {
        "total_sessions": 10,
        "average_score": 75.5,
        "topics_mastered": 5,
        "weak_topics": ["Databases", "Networking"]
    }
    ```

#### 5.2. Get Session Results

-   **Method**: `GET`
-   **Path**: `/api/results/session/{session_id}`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/results.py`

-   **Description**: Retrieves the detailed results for a specific session.

-   **Parameters**:
    -   **Path**:
        -   `session_id` (string, required): The ID of the session.

-   **Request Example**:

    ```
    GET /api/results/session/s1e2s3s4-i5o6-7890-1234-567890abcdef
    ```

-   **Response Model**: `SessionResultResponse` (details not fully available in provided schemas, assuming a structure for session results)
    -   `session_id` (string, UUID): The ID of the session.
    -   `mode` (string): Session mode (e.g., "exam", "practice").
    -   `question_count` (integer): Total questions in the session.
    -   `correct_count` (integer): Number of correct answers.
    -   `wrong_count` (integer): Number of wrong answers.
    -   `score_percent` (float): Score percentage for the session.
    -   `submitted_at` (datetime): Timestamp of session submission.
    -   `per_topic_breakdown` (array of objects): Breakdown of performance per topic.

-   **Response Example**:

    ```json
    {
        "session_id": "s1e2s3s4-i5o6-7890-1234-567890abcdef",
        "mode": "practice",
        "question_count": 10,
        "correct_count": 7,
        "wrong_count": 3,
        "score_percent": 70.0,
        "submitted_at": "2026-03-30T10:00:00Z",
        "per_topic_breakdown": [
            {
                "topic": "Data Structures",
                "correct": 3,
                "total": 5
            }
        ]
    }
    ```

### 6. Sessions Endpoints (`app/api/sessions.py`)

These endpoints manage the lifecycle of user study sessions (exams, practice, quizzes).

#### 6.1. Start Session

-   **Method**: `POST`
-   **Path**: `/api/sessions/start`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/sessions.py`

-   **Description**: Initiates a new study session (exam, practice, or quiz).

-   **Parameters**:
    -   **Body**: `StartSessionRequest`
        -   `mode` (string, required): "exam", "practice", or "quiz".
        -   `department_id` (string, UUID, optional): Filter by department.
        -   `course_id` (string, UUID, optional): Filter by course.
        -   `topic_id` (string, UUID, optional): Filter by topic.
        -   `past_exam_id` (string, UUID, optional): Start a session based on a specific past exam.
        -   `exam_template_id` (string, UUID, optional): Start a session based on an exam template.
        -   `question_count` (integer, optional): Number of questions for quiz mode (min 5, max 10).

-   **Request Example**:

    ```json
    {
        "mode": "practice",
        "department_id": "d1e2f3g4-h5i6-7890-1234-567890abcdef",
        "question_count": 10
    }
    ```

-   **Response Model**: `StartSessionResponse`
    -   `session_id` (string, UUID): The ID of the newly created session.
    -   `mode` (string): The mode of the session.
    -   `status` (string): Current status, always "in_progress".
    -   `question_count` (integer): Total number of questions in the session.
    -   `ttl_seconds` (integer): Time-to-live for the session in seconds.
    -   `deadline_ts` (integer, optional): Unix timestamp of the session deadline (for exam mode).

-   **Response Example**:

    ```json
    {
        "session_id": "s1e2s3s4-i5o6-7890-1234-567890abcdef",
        "mode": "practice",
        "status": "in_progress",
        "question_count": 10,
        "ttl_seconds": 3600,
        "deadline_ts": null
    }
    ```

#### 6.2. Get Session Metadata

-   **Method**: `GET`
-   **Path**: `/api/sessions/{session_id}`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/sessions.py`

-   **Description**: Retrieves metadata for a specific session.

-   **Parameters**:
    -   **Path**:
        -   `session_id` (string, UUID, required): The ID of the session.

-   **Request Example**:

    ```
    GET /api/sessions/s1e2s3s4-i5o6-7890-1234-567890abcdef
    ```

-   **Response Model**: `dict` (TODO: Define a proper schema for session metadata)
    -   Contains various session-related information.

-   **Response Example**:

    ```json
    {
        "session_id": "s1e2s3s4-i5o6-7890-1234-567890abcdef",
        "current_question_index": 3,
        "total_questions": 10,
        "mode": "practice",
        "time_remaining": 1200
    }
    ```

#### 6.3. Get Question

-   **Method**: `GET`
-   **Path**: `/api/sessions/{session_id}/question`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/sessions.py`

-   **Description**: Retrieves the current question for an active session.

-   **Parameters**:
    -   **Path**:
        -   `session_id` (string, UUID, required): The ID of the session.

-   **Request Example**:

    ```
    GET /api/sessions/s1e2s3s4-i5o6-7890-1234-567890abcdef/question
    ```

-   **Response Model**: `GetQuestionResponse`
    -   `session_id` (string, UUID): The ID of the session.
    -   `question` (object, `QuestionPayload`): Details of the question.
        -   `question_id` (string, UUID): The ID of the question.
        -   `index` (integer): Current question index in the session.
        -   `total` (integer): Total questions in the session.
        -   `prompt` (string, optional): The question prompt.
        -   `image_url` (string, optional): URL to the question image (required for exam mode).
        -   `choice_a`, `choice_b`, `choice_c`, `choice_d` (string): Answer choices.
        -   `qtoken` (string): A short-lived, single-use token for submitting the answer.

-   **Response Example**:

    ```json
    {
        "session_id": "s1e2s3s4-i5o6-7890-1234-567890abcdef",
        "question": {
            "question_id": "q1w2e3r4-t5y6-7890-1234-567890abcdef",
            "index": 1,
            "total": 10,
            "prompt": "What is the capital of France?",
            "image_url": null,
            "choice_a": "Berlin",
            "choice_b": "Madrid",
            "choice_c": "Paris",
            "choice_d": "Rome",
            "qtoken": "some_short_lived_token"
        }
    }
    ```

#### 6.4. Submit Answer

-   **Method**: `POST`
-   **Path**: `/api/sessions/{session_id}/answer`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/sessions.py`

-   **Description**: Submits an answer for the current question in a session.

-   **Parameters**:
    -   **Path**:
        -   `session_id` (string, UUID, required): The ID of the session.
    -   **Body**: `SubmitAnswerRequest`
        -   `question_id` (string, UUID): The ID of the question being answered.
        -   `answer` (string, required): The chosen answer ("A", "B", "C", or "D").
        -   `qtoken` (string): The question token received with the question.

-   **Request Example**:

    ```json
    {
        "question_id": "q1w2e3r4-t5y6-7890-1234-567890abcdef",
        "answer": "C",
        "qtoken": "some_short_lived_token"
    }
    ```

-   **Response Model**: `SubmitAnswerResponse`
    -   `accepted` (boolean): `true` if the answer was accepted.
    -   `is_correct` (boolean, optional): `true` if the answer is correct (only for practice/quiz mode).
    -   `explanation` (string, optional): Explanation for the correct answer (only for practice/quiz mode).

-   **Response Example**:

    ```json
    {
        "accepted": true,
        "is_correct": true,
        "explanation": "Paris is indeed the capital of France."
    }
    ```

#### 6.5. Next Question

-   **Method**: `POST`
-   **Path**: `/api/sessions/{session_id}/next`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/sessions.py`

-   **Description**: Advances to the next question in the session.

-   **Parameters**:
    -   **Path**:
        -   `session_id` (string, UUID, required): The ID of the session.

-   **Request Example**:

    ```
    POST /api/sessions/s1e2s3s4-i5o6-7890-1234-567890abcdef/next
    ```

-   **Response Model**: `NextResponse`
    -   `session_id` (string, UUID): The ID of the session.
    -   `index` (integer): The index of the next question.

-   **Response Example**:

    ```json
    {
        "session_id": "s1e2s3s4-i5o6-7890-1234-567890abcdef",
        "index": 2
    }
    ```

#### 6.6. Submit Session

-   **Method**: `POST`
-   **Path**: `/api/sessions/{session_id}/submit`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/sessions.py`

-   **Description**: Submits and finalizes a study session, calculating results.

-   **Parameters**:
    -   **Path**:
        -   `session_id` (string, UUID, required): The ID of the session.

-   **Request Example**:

    ```
    POST /api/sessions/s1e2s3s4-i5o6-7890-1234-567890abcdef/submit
    ```

-   **Response Model**: `SubmitSessionResponse`
    -   `session_id` (string, UUID): The ID of the submitted session.
    -   `mode` (string): The mode of the session.
    -   `question_count` (integer): Total questions in the session.
    -   `correct_count` (integer): Number of correct answers.
    -   `wrong_count` (integer): Number of wrong answers.
    -   `score_percent` (float): Score percentage for the session.
    -   `submitted_at` (datetime): Timestamp of session submission.
    -   `per_topic_breakdown` (array of dict, optional): Breakdown of performance per topic.

-   **Response Example**:

    ```json
    {
        "session_id": "s1e2s3s4-i5o6-7890-1234-567890abcdef",
        "mode": "practice",
        "question_count": 10,
        "correct_count": 8,
        "wrong_count": 2,
        "score_percent": 80.0,
        "submitted_at": "2026-03-30T10:30:00Z",
        "per_topic_breakdown": [
            {
                "topic": "Data Structures",
                "correct": 4,
                "total": 5
            },
            {
                "topic": "Algorithms",
                "correct": 4,
                "total": 5
            }
        ]
    }
    ```

### 7. User Endpoints (`app/api/user.py`)

These endpoints manage user-related operations, including creation, retrieval, and invite codes.

#### 7.1. Upsert User

-   **Method**: `POST`
-   **Path**: `/api/users/upsert`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/user.py`

-   **Description**: Creates a new user or updates an existing user's information.

-   **Parameters**:
    -   **Body**: `UserUpsertRequest`
        -   `telegram_id` (integer, required): The Telegram ID of the user.
        -   `telegram_username` (string, optional): The Telegram username.
        -   `first_name` (string, optional): The user's first name.
        -   `last_name` (string, optional): The user's last name.
        -   `ref_code` (string, UUID, optional): Referral code if the user was invited.

-   **Request Example**:

    ```json
    {
        "telegram_id": 123456789,
        "telegram_username": "john_doe",
        "first_name": "John",
        "last_name": "Doe",
        "ref_code": "r1e2f3c4-o5d6-7890-1234-567890abcdef"
    }
    ```

-   **Response Model**: `UserResponse`
    -   `user_id` (string, UUID): The internal ID of the user.
    -   `telegram_id` (integer): The Telegram ID of the user.
    -   `invite_code` (string, UUID): The user's unique invite code.
    -   `invite_count` (integer): Number of users invited by this user.
    -   `is_pro` (boolean): `true` if the user has a pro plan.
    -   `plan_expiry` (datetime, optional): Expiry date of the pro plan.

-   **Response Example**:

    ```json
    {
        "user_id": "u1s2e3r4-i5d6-7890-1234-567890abcdef",
        "telegram_id": 123456789,
        "invite_code": "i1n2v3i4-t5e6-7890-1234-567890abcdef",
        "invite_count": 0,
        "is_pro": false,
        "plan_expiry": null
    }
    ```

#### 7.2. Get Current User

-   **Method**: `GET`
-   **Path**: `/api/users/me`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/user.py`

-   **Description**: Retrieves the information of the current authenticated user.

-   **Parameters**: None

-   **Request Example**:

    ```
    GET /api/users/me
    ```

-   **Response Model**: `UserResponse` (Same as Upsert User)

-   **Response Example**: (Same as Upsert User)

#### 7.3. Get User Invite Code

-   **Method**: `GET`
-   **Path**: `/api/users/me/invite-code`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/user.py`

-   **Description**: Retrieves the invite code for the current authenticated user.

-   **Parameters**: None

-   **Request Example**:

    ```
    GET /api/users/me/invite-code
    ```

-   **Response Model**: `string` (UUID)

-   **Response Example**:

    ```
    "i1n2v3i4-t5e6-7890-1234-567890abcdef"
    ```

#### 7.4. Redeem Invite Code

-   **Method**: `POST`
-   **Path**: `/api/users/me/redeem-invite-code`
-   **Permissions**: Authenticated (Telegram Bot Headers)
-   **User Types**: Telegram User
-   **Position in Code**: `app/api/user.py`

-   **Description**: Redeems an invite code, associating the current user with the inviter.

-   **Parameters**:
    -   **Body**:
        -   `invite_code` (string, required): The invite code to redeem.

-   **Request Example**:

    ```json
    {
        "invite_code": "i1n2v3i4-t5e6-7890-1234-567890abcdef"
    }
    ```

-   **Response Model**: `UserResponse` (Same as Upsert User)

-   **Response Example**: (Same as Upsert User, with potentially updated `invite_count` for the inviter and `is_pro`/`plan_expiry` for the current user if the invite grants benefits)
