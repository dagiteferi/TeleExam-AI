from redis.asyncio import Redis
from app.core.config import settings


redis_client: Redis | None = None

async def get_redis_client() -> Redis:
    """Returns the Redis client instance."""
    if redis_client is None:
        raise ConnectionError("Redis client not initialized.")
    return redis_client

async def init_redis():
    """Initializes the Redis client."""
    global redis_client
    redis_client = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        decode_responses=True  
    )
    await redis_client.ping()
    print("Redis client initialized and connected.")

async def close_redis():
    """Closes the Redis client connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
        print("Redis client connection closed.")




SESSION_KEY_PREFIX = "teleexam:session:"
def get_session_key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


ACTIVE_SESSION_KEY_PREFIX = "teleexam:user:{user_id}:active_session:"
def get_active_session_key(user_id: int, mode: str) -> str:
    return f"{ACTIVE_SESSION_KEY_PREFIX.format(user_id=user_id)}{mode}"

QTOKEN_KEY_PREFIX = "teleexam:qtoken:"
def get_qtoken_key(user_id: int, session_id: str, question_id: int) -> str:
    return f"{QTOKEN_KEY_PREFIX}{user_id}:{session_id}:{question_id}"


IDEMPOTENCY_KEY_PREFIX = "teleexam:idempotency:"
def get_idempotency_key(idempotency_key: str) -> str:
    return f"{IDEMPOTENCY_KEY_PREFIX}{idempotency_key}"


BEHAVIOR_KEY_PREFIX = "teleexam:behavior:"
def get_behavior_key(user_id: int) -> str:
    return f"{BEHAVIOR_KEY_PREFIX}{user_id}"


RATE_LIMIT_KEY_PREFIX = "teleexam:rl:"
def get_rate_limit_key(user_id: int, route: str) -> str:
    return f"{RATE_LIMIT_KEY_PREFIX}user:{user_id}:{route}"


FLAG_KEY_PREFIX = "teleexam:flag:"
def get_flag_key(user_id: int) -> str:
    return f"{FLAG_KEY_PREFIX}{user_id}"


QUESTION_SERVED_TIME_KEY_PREFIX = "teleexam:rt:"
def get_question_served_time_key(session_id: str, current_index: int) -> str:
    return f"{QUESTION_SERVED_TIME_KEY_PREFIX}{session_id}:{current_index}"


SUBMIT_SNAPSHOT_KEY_PREFIX = "teleexam:submit_snapshot:"
def get_submit_snapshot_key(session_id: str) -> str:
    return f"{SUBMIT_SNAPSHOT_KEY_PREFIX}{session_id}"
