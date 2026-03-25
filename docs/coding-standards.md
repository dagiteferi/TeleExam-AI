# TeleExam AI - Coding Standards

We write **clean, readable, secure, and fast** code. Our philosophy prioritizes self-documenting code over excessive comments.

### 1. General Principles
- **Clarity over Cleverness:** Code should be easy to understand, even if it means being slightly more verbose.
- **Single Responsibility:** Functions and classes should have a single, well-defined purpose.
- **Minimal Comments:** Comments should explain *why* something is done, not *what* is done. Strive for self-documenting code.
- **Fail Fast and Loud:** Errors should be detected and reported as early as possible to prevent cascading failures.
- **Type Hints Everywhere:** Utilize Python's type hinting for improved readability, maintainability, and static analysis.

### 2. Python Style
- **Python Version:** Target Python 3.11+ for modern features and performance.
- **Formatting & Linting:** Use `Black` for code formatting and `Ruff` for linting to ensure consistent style and catch common errors.
- **Line Length:** Adhere to a maximum line length of 100 characters.
- **String Quotes:** Prefer double quotes for strings (`"string"`).
- **F-strings:** Use f-strings for string formatting.

### 3. Naming Conventions
- **Variables & Functions:** Use `snake_case` (e.g., `user_name`, `get_user_data`).
- **Classes:** Use `PascalCase` (e.g., `UserService`, `ExamSession`).
- **Constants:** Use `UPPER_CASE` (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`).
- **Private Methods:** Prefix with a single underscore (`_leading_underscore`) to indicate internal use.
- **Abbreviations:** Avoid abbreviations unless they are extremely common and universally understood (e.g., `id`, `db`, `ai`).

**Example:**
```python
# Good
user_service = UserService()

def get_next_question(session_id: str) -> Question:
    # ...
    pass

# Bad
us = UserSvc()

def gnq(sid):
    # ...
    pass
```

### 4. Error Handling

Effective error handling is crucial for application stability and user experience.
- **Custom Exceptions:** Create custom exceptions only when specific business logic errors need to be distinguished.
- **HTTP Exceptions:** For API errors, leverage FastAPI's `HTTPException` to return standard HTTP error responses.
- **No Silent Swallowing:** Never catch and ignore exceptions silently; always log or re-raise them.
- **Clear Error Messages:** Return clear, concise, and safe error messages to the client, avoiding exposure of internal system details.

### 5. Logging

Logging should provide sufficient information for debugging and monitoring without being overly verbose or exposing sensitive data.
- **Logging Library:** Use `structlog` or Python's standard `logging` module for structured and consistent log output.
- **Purposeful Logging:** Log only important actions, events, or errors. Avoid excessive debug logging in production environments.
- **Sensitive Data:** Never log sensitive user data or secrets. `telegram_id` is generally acceptable for logging as it's a public identifier.

### 6. Security

Security is paramount. All code must be written with security best practices in mind.
- **No Hardcoded Secrets:** Never hardcode API keys, database credentials, or other sensitive information directly in the codebase. Use environment variables or a secure secrets management system.
- **Input Validation:** Always validate all incoming input using Pydantic models to ensure data integrity and prevent injection attacks.
- **Supabase RLS:** Utilize Supabase's Row Level Security (RLS) to enforce authorization at the database level, ensuring users can only access their own data. Never trust client-side data for authorization decisions.
- **Rate Limiting:** Implement rate limiting on all AI endpoints and other resource-intensive operations to prevent abuse and denial-of-service attacks.

### 7. Performance

Optimize for performance where it matters, but avoid premature optimization.
- **Asynchronous Programming:** Use `async`/`await` where I/O-bound operations (e.g., database calls, external API requests) can benefit from concurrency.
- **Minimal LangGraph Calls:** Keep the number of LangGraph invocations and LLM calls to a minimum, as they are often the most expensive operations.
- **Caching:** Implement caching for heavy or frequently accessed operations and data when performance bottlenecks are identified.

### 8. Git & PR Rules

Consistent Git practices facilitate collaboration and maintain a clean project history.
- **Branch Naming:** Use descriptive branch names following a convention:
    - `feature/explain-endpoint`
    - `fix/rate-limit`
    - `refactor/ai-state`
    - `docs/api-update`
- **Commit Messages:** Follow Conventional Commits specification (e.g., `feat: Add new user registration endpoint`, `fix: Resolve issue with exam session creation`).
- **Pull Request (PR) Requirements:**
    - All PRs must pass automated checks (Black formatting, Ruff linting, and all unit/integration tests).
    - Each PR should represent one logical change or feature.
    - Avoid committing commented-out code to the main branch.

### 9. Code Organization

Maintain a clear and logical structure for the codebase.
- **Business Logic:** All core business logic should reside within the `services/` directory.
- **API Routes:** API endpoint definitions (FastAPI routers) should be placed in the `api/` directory.
- **AI Agent:** The primary LangGraph agent implementation should be encapsulated within `services/ai_service.py`.
- **`main.py`:** Keep `main.py` clean, primarily for application initialization, middleware setup, and router inclusion.

Follow these rules strictly. Clean, readable, secure, and minimal code is the standard we uphold.
