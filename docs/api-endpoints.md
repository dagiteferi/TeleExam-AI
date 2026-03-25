# TeleExam AI - API Endpoints Documentation

**Version:** 1.0  
**Date:** March 25, 2026  
**Base URL:** `https://teleexam-ai.hf.space` (or your Hugging Face Space URL)

---

## Authentication & Context

All API endpoints are secured and require authentication.

**Authentication Header:**
- `X-Telegram-Secret`: `{{TELEGRAM_WEBHOOK_SECRET}}` (A pre-shared secret for backend-to-backend communication).

**User Context:**
- For most operations, the `telegram_id` must be sent in the request body.
- A custom FastAPI middleware validates the `X-Telegram-Secret` and, upon successful authentication, sets `app.current_telegram_id`. This ID is then used for Row Level Security (RLS) in the database, ensuring data isolation per user.

---

## 1. User Management

### POST `/api/users/upsert`

**Description:** Creates a new user or updates an existing user's information based on their `telegram_id`. This is typically called when a user first interacts with the Telegram bot.

**Permissions:** Authenticated via `X-Telegram-Secret`.
**User Types:** Telegram Bot (backend-to-backend).
**Position in Code:** `app/api/admin.py` (or a dedicated user endpoint file, e.g., `app/api/users.py` if it exists).

**Request Body:**
```json
{
  "telegram_id": 123456789
}
```

**Response:**
```json
{
  "success": true,
  "user_id": 5,
  "pro_status": false
}
```

---

## 2. Exam & Questions

### GET `/api/exam/start`

**Description:** Initiates a new exam, practice, or quiz session for the authenticated user. Returns session details and the first question.

**Permissions:** Authenticated via `X-Telegram-Secret`.
**User Types:** Telegram Bot.
**Position in Code:** `app/api/exam.py`

**Query Parameters:**
- `mode` (string, required): The type of session. Can be `exam`, `practice`, or `quiz`.
- `course_id` (integer, optional): Required if `mode` is `exam`. Specifies the course for the exam.
- `topic_id` (integer, optional): Required if `mode` is `practice` or `quiz`. Specifies the topic for the session.

**Example Request:**
`GET /api/exam/start?mode=exam&course_id=3`
`GET /api/exam/start?mode=practice&topic_id=12`

**Response:**
```json
{
  "session_id": "sess_abc123",
  "total_questions": 25,
  "next_question": {
    "question_id": 456,
    "text": "What is the capital of France?",
    "options": ["A. Berlin", "B. Paris", "C. Rome", "D. Madrid"],
    "image_url": "https://example.com/question_image.png"
  }
}
```

### GET `/api/exam/next/{session_id}`

**Description:** Retrieves the next question in an ongoing exam session. Includes question text and an image URL if available and applicable to the exam mode.

**Permissions:** Authenticated via `X-Telegram-Secret`.
**User Types:** Telegram Bot.
**Position in Code:** `app/api/exam.py`

**Path Parameters:**
- `session_id` (string, required): The unique identifier for the current exam session.

**Response:**
```json
{
  "question_id": 457,
  "text": "Which of these is a prime number?",
  "options": ["A. 4", "B. 6", "C. 7", "D. 9"],
  "image_url": null
}
```

### POST `/api/exam/answer`

**Description:** Submits a user's answer for a specific question within an active session.

**Permissions:** Authenticated via `X-Telegram-Secret`.
**User Types:** Telegram Bot.
**Position in Code:** `app/api/exam.py`

**Request Body:**
```json
{
  "session_id": "sess_abc123",
  "question_id": 456,
  "answer": "B"
}
```

**Response:**
```json
{
  "success": true,
  "is_correct": true,
  "correct_answer": "B",
  "feedback": "Correct! Paris is the capital of France."
}
```

---

## 3. AI Endpoints

### POST `/api/ai/explain`

**Description:** Requests a detailed, step-by-step AI explanation for a given question, optionally considering the user's provided answer.

**Permissions:** Authenticated via `X-Telegram-Secret`.
**User Types:** Telegram Bot.
**Position in Code:** `app/api/ai.py`

**Request Body:**
```json
{
  "telegram_id": 123456789,
  "question_id": 456,
  "user_answer": "A"
}
```

**Response:**
```json
{
  "success": true,
  "explanation": "Binary search works by repeatedly dividing the search interval in half...",
  "key_points": [
    "O(log n) time complexity",
    "Requires sorted array",
    "Divide and conquer algorithm"
  ],
  "weak_topic_suggestion": "Review Searching Algorithms"
}
```

### POST `/api/ai/chat`

**Description:** Initiates or continues a multi-turn conversational tutoring session with the AI.

**Permissions:** Authenticated via `X-Telegram-Secret`.
**User Types:** Telegram Bot.
**Position in Code:** `app/api/ai.py`

**Request Body:**
```json
{
  "telegram_id": 123456789,
  "message": "Can you explain why my answer was wrong?"
}
```

**Response:**
```json
{
  "success": true,
  "ai_response": "Let's break down your answer. What was your reasoning for choosing A?"
}
```
**Note:** This endpoint is part of Phase 1.5 development.

### POST `/api/ai/study-plan`

**Description:** Generates a personalized study plan for the user based on their performance and identified weak topics.

**Permissions:** Authenticated via `X-Telegram-Secret`.
**User Types:** Telegram Bot.
**Position in Code:** `app/api/ai.py`

**Request Body:**
```json
{
  "telegram_id": 123456789
}
```

**Response:**
```json
{
  "success": true,
  "study_plan": {
    "title": "Personalized Study Plan: Data Structures",
    "duration_days": 7,
    "topics": [
      {"name": "Linked Lists", "resources": ["Article X", "Video Y"]},
      {"name": "Trees", "resources": ["Book Z", "Practice Set A"]}
    ]
  }
}
```
**Note:** This endpoint is part of Phase 2 development.

---

## 4. Results & History

### GET `/api/results/{telegram_id}`

**Description:** Retrieves a summary of a user's overall exam results and identified weak topics.

**Permissions:** Authenticated via `X-Telegram-Secret`.
**User Types:** Telegram Bot.
**Position in Code:** `app/api/results.py`

**Path Parameters:**
- `telegram_id` (integer, required): The Telegram ID of the user whose results are being requested.

**Response:**
```json
{
  "success": true,
  "total_exams_taken": 10,
  "average_score": 75.5,
  "weak_topics": ["Algebra", "Data Structures"],
  "recent_sessions": [
    {"session_id": "sess_xyz", "score": 80, "date": "2026-03-24T10:00:00Z"},
    {"session_id": "sess_uvw", "score": 65, "date": "2026-03-23T15:30:00Z"}
  ]
}
```

### GET `/api/results/session/{session_id}`

**Description:** Provides detailed results for a specific exam or practice session.

**Permissions:** Authenticated via `X-Telegram-Secret`.
**User Types:** Telegram Bot.
**Position in Code:** `app/api/results.py`

**Path Parameters:**
- `session_id` (string, required): The unique identifier for the session.

**Response:**
```json
{
  "success": true,
  "session_id": "sess_abc123",
  "mode": "exam",
  "score": 70,
  "total_questions": 10,
  "correct_answers": 7,
  "incorrect_answers": 3,
  "questions_details": [
    {
      "question_id": 456,
      "user_answer": "B",
      "correct_answer": "B",
      "is_correct": true,
      "topic": "Geography"
    },
    {
      "question_id": 457,
      "user_answer": "A",
      "correct_answer": "C",
      "is_correct": false,
      "topic": "Mathematics"
    }
  ]
}
```

---

## General Notes

-   All API responses generally follow a consistent structure: `{ "success": bool, "data": {...}, "error": "..." }` when applicable.
-   Rate limiting is enforced per `telegram_id` to prevent abuse and ensure fair usage.
-   A Swagger UI will be available at `/docs` when the application is running locally, providing an interactive way to explore and test endpoints.
